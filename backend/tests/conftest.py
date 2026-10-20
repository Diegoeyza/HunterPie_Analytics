"""Shared test setup: never touch the developer's real user settings."""
import pytest

from app import settings


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    monkeypatch.delenv("HUNTS_DB", raising=False)
    monkeypatch.setattr(settings, "user_data_dir", lambda: tmp_path)
