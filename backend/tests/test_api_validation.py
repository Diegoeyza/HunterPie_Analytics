"""API boundary validation: 422s, 409s, strict id parsing."""
import os

from fastapi.testclient import TestClient

from app import api
from tests.test_api import _TEST_DBS, make_client, seed_two_hunts


def teardown_function():
    api.app.dependency_overrides.clear()
    while _TEST_DBS:
        path = _TEST_DBS.pop()
        if os.path.exists(path):
            os.remove(path)


def test_garbage_player_ids_is_422():
    client, _ = make_client(seed_two_hunts)
    for bad in ("abc", "1,,x", "1.5", "--1"):
        r = client.get("/api/hunts", params={"player_ids": bad})
        assert r.status_code == 422, bad
    # empty/blank stays unfiltered
    assert client.get("/api/hunts", params={"player_ids": ""}).status_code == 200


def test_out_of_range_params_are_422():
    client, _ = make_client(seed_two_hunts)
    assert client.get("/api/hunts", params={"limit": 0}).status_code == 422
    assert client.get("/api/hunts",
                      params={"limit": 99999}).status_code == 422
    assert client.get("/api/progress", params={"window": 0}).status_code == 422
    assert client.get("/api/compare", params={"window": 999}).status_code == 422
    assert client.get("/api/quests/detail",
                      params={"key": "quest:1", "players": 99}).status_code == 422
    assert client.get("/api/high-scores",
                      params={"sort_by": "bogus"}).status_code == 422
    assert client.get("/api/leaderboard",
                      params={"min_hunts": 0}).status_code == 422


def test_patch_bodies_validated():
    client, _ = make_client(seed_two_hunts)
    hunt_id = client.get("/api/hunts").json()["hunts"][0]["id"]
    # missing body / wrong shape -> 422, not 500
    assert client.patch(f"/api/hunts/{hunt_id}/ignore").status_code == 422
    ok = client.patch(f"/api/hunts/{hunt_id}/ignore", json={"ignored": True})
    assert ok.status_code == 200 and ok.json()["ignored"] is True


def test_import_missing_dir_is_404():
    client, _ = make_client()
    os.environ["HUNT_EXPORTS"] = "/tmp/definitely-not-a-dir-xyz"
    try:
        assert client.post("/api/import").status_code == 404
    finally:
        del os.environ["HUNT_EXPORTS"]


def test_import_cancel_without_job_is_404():
    client, _ = make_client()
    # Explicit bogus ids: no dependence on cross-test job registry state.
    assert client.get("/api/import/status",
                      params={"job_id": "nope"}).status_code == 404
    assert client.post("/api/import/cancel",
                       params={"job_id": "nope"}).status_code == 404
