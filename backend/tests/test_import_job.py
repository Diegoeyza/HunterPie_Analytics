"""Import job manager: single-flight, cancel, manifest, warnings."""
import json
import tempfile
from pathlib import Path

from sqlalchemy import select

from app import import_job
from app.db import init_db, make_session
from app.models import ImportedFile


def _doc(hash_="JOB1", player="Isi", day=6):
    return {
        "game_type": 2,
        "started_at": f"2026-09-{day:02d}T03:33:06.0749492Z",
        "finished_at": f"2026-09-{day:02d}T03:36:02.3393534Z",
        "uploaded_at": f"2026-09-{day:02d}T03:36:02.3393534Z",
        "hash": hash_,
        "quest": {"id": 543, "type": 0, "deaths": 0, "max_deaths": 3,
                  "level": 1, "stars": 6},
        "players": [{
            "name": player, "weapon": 5, "is_hunterpie_user": True,
            "damages": [
                {"damage": 100.0, "dealt_at": f"2026-09-{day:02d}T03:33:30.0Z"},
                {"damage": 200.0, "dealt_at": f"2026-09-{day:02d}T03:34:30.0Z"},
            ],
            "abnormalities": [],
        }],
        "monsters": [{
            "id": 31, "variant": 0, "max_health": 20000, "crown": 0,
            "hunt_started_at": f"2026-09-{day:02d}T03:33:06.0749492Z",
            "hunt_finished_at": f"2026-09-{day:02d}T03:36:02.3393534Z",
            "hunt_type": 0,
            "enrage": {"activations": []},
            "health_steps": [
                {"time": f"2026-09-{day:02d}T03:33:30.0Z", "percentage": 1.0},
                {"time": f"2026-09-{day:02d}T03:36:00.0Z", "percentage": 0.1},
            ],
        }],
    }


def _setup(nfiles=2):
    tmp = Path(tempfile.mkdtemp(prefix="jobtest-"))
    db = tmp / "t.db"
    src = tmp / "exports"
    src.mkdir()
    for i in range(nfiles):
        (src / f"hunt{i}.json").write_text(
            json.dumps(_doc(f"JOB{i}", day=6 + i)))
    init_db(db)
    return tmp, db, src


def test_run_import_twice_second_skips_manifest():
    tmp, db, src = _setup()
    first = import_job.run_import(db, src)
    assert first["imported"] == 2 and first["errors"] == []
    second = import_job.run_import(db, src)
    assert second["imported"] == 0
    assert second["skipped_manifest"] == 2


def test_manifest_records_warnings():
    tmp, db, src = _setup(nfiles=1)
    import_job.run_import(db, src)
    s = make_session(db)
    try:
        row = s.execute(select(ImportedFile)).scalar_one()
        assert json.loads(row.warnings_json or "[]") == []
    finally:
        s.close()


def test_single_flight_guard():
    job = import_job.ImportJob("fake-running", False, 1)
    import_job._JOBS["fake-running"] = job
    import_job._RUNNING_JOB_ID = "fake-running"
    try:
        try:
            import_job.start_import_job("/tmp/nowhere.db", "/tmp/nowhere")
            raise AssertionError("expected JobBusyError")
        except import_job.JobBusyError as e:
            assert "fake-running" in str(e)
    finally:
        del import_job._JOBS["fake-running"]
        import_job._RUNNING_JOB_ID = None


def test_cancel_before_start():
    tmp, db, src = _setup()
    out = import_job.run_import(db, src, should_stop=lambda: True)
    assert out.get("cancelled") is True
    assert out["scanned"] == 0


def test_cancel_job_marks_flag():
    import_job._JOBS["fake-cancel"] = import_job.ImportJob("fake-cancel", False, 1)
    try:
        job = import_job.cancel_job("fake-cancel")
        assert job is not None and job.cancel_requested is True
        assert import_job.cancel_job("missing") is None
    finally:
        del import_job._JOBS["fake-cancel"]


def test_job_registry_bounded():
    for i in range(import_job.MAX_KEPT_JOBS + 5):
        j = import_job.ImportJob(f"old-{i}", False, 0)
        j.state = "done"
        import_job._JOBS[j.job_id] = j
    try:
        import_job._evict_old_jobs()
        assert len(import_job._JOBS) <= import_job.MAX_KEPT_JOBS
    finally:
        for i in range(import_job.MAX_KEPT_JOBS + 5):
            import_job._JOBS.pop(f"old-{i}", None)
