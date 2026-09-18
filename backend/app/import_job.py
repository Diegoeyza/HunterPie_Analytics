"""Background HuntExports imports with a skip manifest.

The dashboard Import button used to synchronously re-read, re-parse and
re-process every export file on each click (parse cost grows with every
hunt). Now:

- `imported_files` manifest (filename + size + mtime_ns): unchanged files
  are skipped with a cheap stat, never parsed. Manifest wins over the
  hunts table — deleting a hunt from the dashboard does NOT re-add it —
  unless force=True (the "Full recheck" button).
- The scan runs on a background thread; the frontend polls
  GET /api/import/status for progress.

Files that parse but register no hunts (nothing targeted) ARE recorded in
the manifest — re-parsing them could never produce a different result.
Files that fail to parse, or whose hunt transaction raises, are NOT
recorded and get retried next run.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .db import init_db, make_engine
from .import_hunt import (
    DEFAULT_GAME_VERSION,
    DEFAULT_HUNTERPIE_VERSION,
    import_doc,
    load_monster_names,
)
from .models import ImportedFile


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ImportJob:
    """Mutable progress snapshot for one import run (guarded by _JOBS_LOCK)."""

    def __init__(self, job_id: str, force: bool, total: int):
        self.job_id = job_id
        self.state = "running"  # running | done | error
        self.force = force
        self.total = total
        self.scanned = 0
        self.imported = 0
        self.duplicates = 0
        self.skipped_manifest = 0
        self.imported_ids: list[int] = []
        self.errors: list[dict] = []
        self.error: str | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "state": self.state,
            "force": self.force,
            "total": self.total,
            "scanned": self.scanned,
            "imported": self.imported,
            "duplicates": self.duplicates,
            "skipped_manifest": self.skipped_manifest,
            "imported_ids": list(self.imported_ids),
            "errors": list(self.errors),
            "error": self.error,
        }


_JOBS: dict[str, ImportJob] = {}
_JOBS_LOCK = threading.Lock()
_LAST_JOB_ID: str | None = None


def get_job(job_id: str | None = None) -> ImportJob | None:
    """Fetch a job by id, or the most recently started job when omitted."""
    with _JOBS_LOCK:
        if job_id is None:
            job_id = _LAST_JOB_ID
        return _JOBS.get(job_id) if job_id else None


def load_manifest(session) -> dict[str, ImportedFile]:
    """filename -> ImportedFile row for all previously processed files."""
    return {r.filename: r for r in session.execute(select(ImportedFile)).scalars()}


def manifest_hit(manifest: dict[str, ImportedFile], path: Path,
                 stat: object = None) -> bool:
    """True when the file is unchanged since it was fully processed."""
    row = manifest.get(path.name)
    if row is None:
        return False
    st = stat or path.stat()
    return row.size == st.st_size and row.mtime_ns == st.st_mtime_ns


def record_file(session, path: Path, hunts_created: int) -> None:
    """Upsert the manifest row after a file is fully processed."""
    st = path.stat()
    row = session.get(ImportedFile, path.name)
    if row is None:
        row = ImportedFile(filename=path.name, size=st.st_size,
                           mtime_ns=st.st_mtime_ns,
                           hunts_created=hunts_created,
                           imported_at=_utcnow())
        session.add(row)
    else:
        row.size = st.st_size
        row.mtime_ns = st.st_mtime_ns
        row.hunts_created = hunts_created
        row.imported_at = _utcnow()
    session.commit()


def run_import(db_path: str | Path, src: str | Path, force: bool = False,
               progress=None) -> dict:
    """Import all *.json in src into the DB at db_path.

    progress(snapshot: dict) is called after every file (and once at
    start) with the running counts; used by the background job to feed
    the status endpoint. Returns the final result dict.
    """
    db_path = Path(db_path)
    src = Path(src)
    init_db(db_path)
    maker = sessionmaker(bind=make_engine(db_path), future=True)

    files = sorted(src.glob("*.json"))
    names = load_monster_names(None)
    cache: dict = {}  # reference-row lookup cache shared across the job
    result = {"scanned": 0, "imported": 0, "imported_ids": [],
              "duplicates": 0, "skipped_manifest": 0, "errors": []}
    if progress:
        progress({**result, "total": len(files)})

    manifest: dict[str, ImportedFile] = {}
    if not force:
        session = maker()
        try:
            manifest = load_manifest(session)
        finally:
            session.close()

    for path in files:
        result["scanned"] += 1
        if not force and manifest_hit(manifest, path):
            result["skipped_manifest"] += 1
            if progress:
                progress({**result, "total": len(files)})
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as e:
            result["errors"].append({"file": path.name, "error": str(e)})
            if progress:
                progress({**result, "total": len(files)})
            continue
        session = maker()
        try:
            try:
                outcomes = import_doc(session, doc, names,
                                      DEFAULT_HUNTERPIE_VERSION,
                                      DEFAULT_GAME_VERSION, cache=cache)
            except (ValueError, KeyError) as e:
                session.rollback()
                result["errors"].append({"file": path.name, "error": str(e)})
                continue
            new_ids = [hunt.id for hunt, created, _ in outcomes if created]
            result["imported"] += len(new_ids)
            result["imported_ids"].extend(new_ids)
            result["duplicates"] += sum(1 for _, created, _ in outcomes
                                        if not created)
            # Fully processed (even with zero hunts) -> manifest it.
            record_file(session, path, len(new_ids))
        finally:
            session.close()
        if progress:
            progress({**result, "total": len(files)})
    return result


def start_import_job(db_path: str | Path, src: str | Path,
                     force: bool = False) -> ImportJob:
    """Spawn a daemon thread running the import; returns the live job."""
    total = len(list(Path(src).glob("*.json")))
    job = ImportJob(job_id=uuid.uuid4().hex[:12], force=force, total=total)
    with _JOBS_LOCK:
        _JOBS[job.job_id] = job
        global _LAST_JOB_ID
        _LAST_JOB_ID = job.job_id

    def _run():
        try:
            def _progress(snap: dict):
                with _JOBS_LOCK:
                    job.scanned = snap["scanned"]
                    job.imported = snap["imported"]
                    job.duplicates = snap["duplicates"]
                    job.skipped_manifest = snap["skipped_manifest"]
                    job.imported_ids = list(snap["imported_ids"])
                    job.errors = list(snap["errors"])
            final = run_import(db_path, src, force=force, progress=_progress)
            with _JOBS_LOCK:
                job.imported_ids = list(final["imported_ids"])
                job.errors = list(final["errors"])
                job.state = "done"
        except Exception as e:  # never leave the poller hanging
            with _JOBS_LOCK:
                job.error = str(e)
                job.state = "error"

    thread = threading.Thread(target=_run, name=f"import-{job.job_id}",
                              daemon=True)
    thread.start()
    return job
