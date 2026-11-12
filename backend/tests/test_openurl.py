"""Browser launching must not leak PyInstaller's LD_LIBRARY_PATH.

A frozen Linux app sets LD_LIBRARY_PATH to its _internal folder; children
inherit it, and a distro /bin/sh (bash on Fedora/Arch) then loads the older
bundled libreadline and dies before the browser opens.
"""
import sys

import pytest

from app import openurl


def test_child_env_restores_pre_launch_library_path(monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/app/_internal")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/opt/lib")

    assert openurl._child_env()["LD_LIBRARY_PATH"] == "/opt/lib"


def test_child_env_drops_library_path_when_there_was_none(monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/app/_internal")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "")

    assert "LD_LIBRARY_PATH" not in openurl._child_env()


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="the xdg-open path is Linux-only")
def test_open_url_sanitizes_the_launcher_environment(monkeypatch):
    seen = {}

    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["env"] = kwargs["env"]
        return object()

    monkeypatch.setenv("LD_LIBRARY_PATH", "/app/_internal")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "")
    monkeypatch.setattr(openurl.subprocess, "Popen", fake_popen)

    assert openurl.open_url("http://127.0.0.1:47600/") is True
    assert seen["cmd"] == ("xdg-open", "http://127.0.0.1:47600/")
    assert "LD_LIBRARY_PATH" not in seen["env"]


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="the xdg-open path is Linux-only")
def test_open_url_falls_back_to_gio(monkeypatch):
    seen = []

    def fake_popen(cmd, **kwargs):
        seen.append(cmd)
        if cmd[0] == "xdg-open":
            raise FileNotFoundError
        return object()

    monkeypatch.setattr(openurl.subprocess, "Popen", fake_popen)

    assert openurl.open_url("http://127.0.0.1:47600/") is True
    assert [cmd[0] for cmd in seen] == ["xdg-open", "gio"]
