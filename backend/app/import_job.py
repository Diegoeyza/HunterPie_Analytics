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
import logging
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from .db import get_engine, init_db
from .import_hunt import (
    DEFAULT_GAME_VERSION,
    DEFAULT_HUNTERPIE_VERSION,
    import_doc,
    load_monster_names,
)
from .models import ImportedFile

log = logging.getLogger(__name__)


class JobBusyError(RuntimeError):
    """An import job is already running (mapped to HTTP 409)."""


MAX_KEPT_JOBS = 20


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ImportJob:
    """Mutable progress snapshot for one import run (guarded by _JOBS_LOCK)."""

    def __init__(self, job_id: str, force: bool, total: int):
        self.job_id = job_id
        self.state = "running"  # running | done | error | cancelled
        self.force = force
        self.total = total
        self.scanned = 0
        self.imported = 0
        self.duplicates = 0
        self.skipped_manifest = 0
        self.imported_ids: list[int] = []
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.error: str | None = None
        self.cancel_requested = False

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
            "warnings": list(self.warnings),
            "error": self.error,
        }


_JOBS: dict[str, ImportJob] = {}
_JOBS_LOCK = threading.Lock()
_LAST_JOB_ID: str | None = None
_RUNNING_JOB_ID: str | None = None


def any_running() -> ImportJob | None:
    """The currently running job, if any (single-flight guard)."""
    with _JOBS_LOCK:
        if _RUNNING_JOB_ID is None:
            return None
        return _JOBS.get(_RUNNING_JOB_ID)


def _evict_old_jobs() -> None:
    """Keep the registry bounded: retain running + newest finished."""
    with _JOBS_LOCK:
        if len(_JOBS) <= MAX_KEPT_JOBS:
            return
        finished = sorted(
            (j for j in _JOBS.values() if j.state != "running"),
            key=lambda j: j.job_id)
        for job in finished[:len(_JOBS) - MAX_KEPT_JOBS]:
            del _JOBS[job.job_id]


def cancel_job(job_id: str | None = None) -> ImportJob | None:
    """Ask a running job to stop after the current file."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id) if job_id else _JOBS.get(_LAST_JOB_ID or "")
        if job is None or job.state != "running":
            return None
        job.cancel_requested = True
        return job


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
    """True when the file is unchanged since it was fully processed.

    Pass a pre-taken stat (os.stat_result) to avoid a TOCTOU re-stat;
    run_import stats each file exactly once and threads it through.
    """
    row = manifest.get(path.name)
    if row is None:
        return False
    st = stat or path.stat()
    return row.size == st.st_size and row.mtime_ns == st.st_mtime_ns


def record_file(session, path: Path, hunts_created: int,
                st=None, warnings: list[str] | None = None) -> None:
    """Upsert the manifest row after a file is fully processed."""
    st = st or path.stat()
    payload = json.dumps(warnings or [])
    row = session.get(ImportedFile, path.name)
    if row is None:
        row = ImportedFile(filename=path.name, size=st.st_size,
                           mtime_ns=st.st_mtime_ns,
                           hunts_created=hunts_created,
                           warnings_json=payload,
                           imported_at=_utcnow())
        session.add(row)
    else:
        row.size = st.st_size
        row.mtime_ns = st.st_mtime_ns
        row.hunts_created = hunts_created
        row.warnings_json = payload
        row.imported_at = _utcnow()
    session.commit()


def run_import(db_path: str | Path, src: str | Path, force: bool = False,
               progress=None, should_stop=None) -> dict:
    """Import all *.json in src into the DB at db_path.

    progress(snapshot: dict) is called after every file (and once at
    start) with the running counts; used by the background job to feed
    the status endpoint. should_stop() is polled between files for
    cancellation. Returns the final result dict.
    """
    db_path = Path(db_path)
    src = Path(src)
    init_db(db_path)
    maker = sessionmaker(bind=get_engine(db_path), future=True)

    files = sorted(src.glob("*.json"))
    names = load_monster_names(None)
    cache: dict = {}  # reference-row lookup cache shared across the job
    result = {"scanned": 0, "imported": 0, "imported_ids": [],
              "duplicates": 0, "skipped_manifest": 0, "errors": [],
              "warnings": []}
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
        if should_stop is not None and should_stop():
            result["cancelled"] = True
            break
        result["scanned"] += 1
        try:
            st = path.stat()
        except OSError as e:
            result["errors"].append({"file": path.name, "error": str(e)})
            if progress:
                progress({**result, "total": len(files)})
            continue
        if not force and manifest_hit(manifest, path, st):
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
            except (ValueError, KeyError, SQLAlchemyError) as e:
                session.rollback()
                log.warning("import failed for %s: %s", path.name, e)
                result["errors"].append({"file": path.name, "error": str(e)})
                continue
            new_ids = [hunt.id for hunt, created, _ in outcomes if created]
            file_warnings = [w for _, _, ws in outcomes for w in ws]
            result["imported"] += len(new_ids)
            result["imported_ids"].extend(new_ids)
            result["duplicates"] += sum(1 for _, created, _ in outcomes
                                        if not created)
            if file_warnings:
                result["warnings"].append({"file": path.name,
                                           "warnings": file_warnings})
            # Fully processed (even with zero hunts) -> manifest it.
            record_file(session, path, len(new_ids), st, file_warnings)
        finally:
            session.close()
        if progress:
            progress({**result, "total": len(files)})
    return result


def start_import_job(db_path: str | Path, src: str | Path,
                     force: bool = False) -> ImportJob:
    """Spawn a daemon thread running the import; returns the live job.

    Single-flight: raises JobBusyError when another job is running.
    Daemon threads die with the process, but every committed hunt row is
    dedup-safe on re-import, so at most the in-flight file is retried.
    """
    global _LAST_JOB_ID, _RUNNING_JOB_ID
    with _JOBS_LOCK:
        running = _JOBS.get(_RUNNING_JOB_ID) if _RUNNING_JOB_ID else None
        if running is not None and running.state == "running":
            raise JobBusyError(
                f"import job {running.job_id} already running "
                f"({running.scanned}/{running.total} files)")
    total = len(list(Path(src).glob("*.json")))
    job = ImportJob(job_id=uuid.uuid4().hex[:12], force=force, total=total)
    with _JOBS_LOCK:
        _JOBS[job.job_id] = job
        _LAST_JOB_ID = job.job_id
        _RUNNING_JOB_ID = job.job_id
    _evict_old_jobs()

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
                    job.warnings = list(snap.get("warnings", []))
            final = run_import(db_path, src, force=force, progress=_progress,
                               should_stop=lambda: job.cancel_requested)
            with _JOBS_LOCK:
                job.imported_ids = list(final["imported_ids"])
                job.errors = list(final["errors"])
                job.warnings = list(final.get("warnings", []))
                job.state = ("cancelled" if final.get("cancelled")
                             or job.cancel_requested else "done")
        except Exception as e:  # never leave the poller hanging
            log.exception("import job %s failed", job.job_id)
            with _JOBS_LOCK:
                job.error = str(e)
                job.state = "error"
        finally:
            with _JOBS_LOCK:
                global _RUNNING_JOB_ID
                if _RUNNING_JOB_ID == job.job_id:
                    _RUNNING_JOB_ID = None

    thread = threading.Thread(target=_run, name=f"import-{job.job_id}",
                              daemon=True)
    thread.start()
    return job
