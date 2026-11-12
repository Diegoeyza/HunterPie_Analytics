"""Open a URL in the user's browser without leaking bundled libraries.

PyInstaller's Linux bootloader points ``LD_LIBRARY_PATH`` at the app's
``_internal`` folder so the frozen interpreter and its libs win. Child
processes inherit it, and ``xdg-open`` is a shell script: a distro ``/bin/sh``
(bash on Fedora/Arch) then loads the older bundled ``libreadline`` and dies
with ``undefined symbol: rl_trim_arg_from_keyseq`` before the browser opens.

The bootloader keeps the pre-launch value in ``LD_LIBRARY_PATH_ORIG``; use
that for the opener so it sees the same libraries as any other app.
"""
from __future__ import annotations

import os
import subprocess
import sys
import webbrowser

_DEVNULL = subprocess.DEVNULL


def _child_env() -> dict[str, str]:
    """Environment for the browser launcher: PyInstaller's path removed."""
    env = dict(os.environ)
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original:
        env["LD_LIBRARY_PATH"] = original
    else:
        env.pop("LD_LIBRARY_PATH", None)
    return env


def open_url(url: str) -> bool:
    """Open *url* in the default browser; True when a launcher was started."""
    if sys.platform.startswith("linux"):
        env = _child_env()
        for cmd in (("xdg-open", url), ("gio", "open", url)):
            try:
                subprocess.Popen(  # noqa: S603 - fixed, user-visible local URL
                    cmd, env=env, stdout=_DEVNULL, stderr=_DEVNULL,
                    start_new_session=True)
                return True
            except OSError:
                continue
    try:
        return webbrowser.open(url)
    except Exception:  # noqa: BLE001 - opening a page must never crash the app
        return False
