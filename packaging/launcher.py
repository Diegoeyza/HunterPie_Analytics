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

# Source run: make backend/ importable. The PyInstaller spec does this via
# pathex; a plain `python packaging/launcher.py` only gets packaging/ on
# sys.path, which would break `from app...` imports.
if not getattr(sys, "frozen", False):
    _backend = Path(__file__).resolve().parent.parent / "backend"
    if str(_backend) not in sys.path:
        sys.path.insert(0, str(_backend))


def _ensure_streams() -> None:
    """Give the server thread real std streams in windowed builds.

    PyInstaller's windowed bootloader leaves sys.stdout/sys.stderr as None.
    uvicorn's logging formatters call isatty() on the stream at startup,
    which kills the server thread and surfaces only as the misleading
    "the local API did not start in time" from _wait_healthy.
    """
    for _name in ("stdout", "stderr"):
        if getattr(sys, _name, None) is None:
            setattr(sys, _name, open(os.devnull, "w", encoding="utf-8"))


_ensure_streams()


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


def _preferred_port() -> int:
    """Stable loopback port, falling back to a free one when it is taken.

    The origin (host:port) is what partitions localStorage, and the dashboard
    keeps its UI preferences plus the acknowledged release note there. A
    random port made every launch a fresh origin, so the "what's new" dialog
    reopened each time (and tab/scope/filter choices were lost). ``HPA_PORT``
    overrides the default for users who need a specific port.
    """
    try:
        preferred = int(os.environ.get("HPA_PORT", "47600"))
    except ValueError:
        return _free_port()
    # Retry briefly: right after an in-place update the previous instance may
    # still be releasing the port, and a fallback would reset the origin.
    for _ in range(10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # Linux refuses to bind a port that still has TIME_WAIT connections
            # (killing the previous instance leaves some). uvicorn binds with
            # SO_REUSEADDR too, so probe the same way; Windows allows rebinding
            # TIME_WAIT ports by default, and SO_REUSEADDR there would let the
            # probe succeed while another instance is actually listening.
            if os.name != "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", preferred))
                return preferred
            except OSError:
                pass
        time.sleep(0.2)
    return _free_port()


def _configure_env() -> None:
    """Point the app at bundled UI assets and a writable per-user DB.

    Must run before ``app.api`` is imported — it reads these at import time.
    """
    from app.paths import user_data_dir

    root = _resource_root()
    os.environ.setdefault("DASHBOARD_DIR", str(root / "dashboard" / "out"))
    os.environ.setdefault("HUNTS_DB", str(user_data_dir() / "hunts.db"))
    # Marks the packaged app: the in-app updater may quit the process (so the
    # installer can replace it) only when this is set.
    os.environ.setdefault("HPA_APP", "1")


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
    port = _preferred_port()
    threading.Thread(target=_serve, args=(port,), daemon=True).start()
    _wait_healthy(port)
    url = f"http://127.0.0.1:{port}/"

    # Linux has no bundled WebView2: the GTK backend needs the system's
    # GObject introspection + WebKit2GTK, and a PyInstaller build cannot
    # reliably carry those. Fall back to the user's browser when the native
    # window is unavailable (or when HPA_NO_WINDOW=1 is set). Windows keeps
    # the WebView2 window it always had.
    if os.environ.get("HPA_NO_WINDOW") == "1":
        return _serve_browser(url)
    try:
        import webview
    except Exception as exc:  # noqa: BLE001 - any import failure is a fallback
        return _serve_browser(url, exc)
    try:
        webview.create_window(
            APP_TITLE,
            url,
            width=1360,
            height=880,
            min_size=(900, 600),
        )
        webview.start()
    except Exception as exc:  # noqa: BLE001 - GTK/WebKit missing at runtime
        return _serve_browser(url, exc)
    return 0


def _serve_browser(url: str, reason: Exception | None = None) -> int:
    """Keep the API alive with the dashboard in the default browser."""
    import webbrowser

    if reason is not None:
        print(f"Native window unavailable ({reason}); opening your browser.")
    webbrowser.open(url)
    print(f"HunterPie Analytics is running at {url}")
    print("Close this window or press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
