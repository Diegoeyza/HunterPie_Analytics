"""Single source of truth for the app version + release coordinates.

Bump ``APP_VERSION`` together with the other version carriers:
  - installer/HunterPieAnalytics.iss   (#define AppVersion)
  - packaging/version_info.txt
  - packaging/msix/AppxManifest.xml
The in-app updater (``app.updater``) compares this against the latest GitHub
release; the dashboard shows it in Settings.
"""
from __future__ import annotations

APP_VERSION = "1.0.6"
GITHUB_REPO = "Diegoeyza/HunterPie_Analytics"
RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"
