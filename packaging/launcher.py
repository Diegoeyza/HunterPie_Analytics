"""Desktop entry point for the packaged HunterPie Analytics app.

Starts the FastAPI server on a loopback-only port and shows the dashboard in a
native window (pywebview -> WebView2). No terminal, no browser tab, and no
external network access: everything is served from 127.0.0.1 and the SQLite DB
lives under the user's local app data.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

APP_TITLE = "HunterPie Analytics"


def _resource_root() -> Path:
    """Root of bundled read-only resources (out/, data/, lua)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # Source run: packaging/ -> repo root.
    return Path(__file__).resolve().parent.parent


def _free_port() -> int:
    """Ask the OS for an unused loopback port (avoids fixed-port clashes)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _configure_env() -> None:
    """Point the app at bundled UI assets and a writable per-user DB.

    Must run before ``app.api`` is imported — it reads these at import time.
    """
    from app.paths import user_data_dir

    root = _resource_root()
    os.environ.setdefault("DASHBOARD_DIR", str(root / "dashboard" / "out"))
    os.environ.setdefault("HUNTS_DB", str(user_data_dir() / "hunts.db"))


def _wait_healthy(port: int, timeout: float = 30.0) -> None:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:  # noqa: S310
                if resp.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("the local API did not start in time")


def _serve(port: int) -> None:
    import uvicorn

    from app.api import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main() -> int:
    _configure_env()
    port = _free_port()
    threading.Thread(target=_serve, args=(port,), daemon=True).start()
    _wait_healthy(port)

    import webview

    webview.create_window(
        APP_TITLE,
        f"http://127.0.0.1:{port}/",
        width=1360,
        height=880,
        min_size=(900, 600),
    )
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
