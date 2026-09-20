"""Endpoint latency bench: seed N hunts, time key read endpoints.

Usage: ../.venv/bin/python bench.py --hunts 1000
"""
from __future__ import annotations

import argparse
import random
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import api
from app.db import init_db, make_session
from app.seed import ensure_reference_data, fake_hunt


def build_db(n: int) -> str:
    fd, path = tempfile.mkstemp(prefix="bench-", suffix=".db")
    import os
    os.close(fd)
    init_db(path)
    session = make_session(path)
    ensure_reference_data(session)
    rng = random.Random(42)
    t0 = time.perf_counter()
    for i in range(n):
        from app.ingest import upsert_hunt
        upsert_hunt(session, fake_hunt(i, rng))
    session.close()
    print(f"seeded {n} hunts in {time.perf_counter() - t0:.1f}s -> {path}")
    return path


def bench(client: TestClient, path: str, params: dict | None = None,
          reps: int = 3) -> float:
    best = float("inf")
    for _ in range(reps):
        t0 = time.perf_counter()
        r = client.get(path, params=params or {})
        assert r.status_code == 200, (path, r.status_code, r.text[:200])
        best = min(best, time.perf_counter() - t0)
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hunts", type=int, default=1000)
    args = ap.parse_args()

    db = build_db(args.hunts)

    def _override():
        s = make_session(db)
        try:
            yield s
        finally:
            s.close()

    api.app.dependency_overrides[api.get_db] = _override
    client = TestClient(api.app)

    targets = [
        ("/api/health", {}),
        ("/api/filter-options", {}),
        ("/api/hunts", {}),
        ("/api/progress", {}),
        ("/api/weapons", {}),
        ("/api/quests", {}),
        ("/api/records", {}),
        ("/api/high-scores", {}),
        ("/api/leaderboard", {}),
        ("/api/activity", {}),
        ("/api/synergy", {}),
        ("/api/progress/improvement", {}),
    ]
    print(f"{'endpoint':32s} {'best-of-3':>10s}")
    for path, params in targets:
        print(f"{path:32s} {bench(client, path, params) * 1000:9.0f}ms")
    Path(db).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
