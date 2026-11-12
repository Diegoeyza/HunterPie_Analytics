HunterPie Analytics for Linux
=============================

Monster Hunter Wilds hunt analytics — damage, HP, monster events, highlights,
progress and rankings — in a local dashboard. Everything runs on your machine;
nothing is uploaded.

This Linux build reads REFramework mod dumps (the game running through Proton).
The HunterPie companion is a Windows app and is NOT included, so buff uptime,
weapon classes, crowns/variants and quest-objective (is_target) data are missing
here. The "Only quest objectives" setting has no data to work with in a
mod-only capture, so it leaves hunts visible.

Requirements
------------
- x86_64 Linux, glibc 2.35+ (built on Ubuntu 22.04; runs on 22.04+, Debian 12+,
  Fedora 36+, SteamOS 3.5+)
- A web browser (the dashboard opens in it)
- Monster Hunter Wilds + REFramework for the capture mod

Quick start (no root)
---------------------
1. Extract this archive:
     tar -xzf HunterPieAnalytics-linux-*.tar.gz
     cd HunterPieAnalytics
2. Run it directly:
     ./HunterPieAnalytics
   or install a menu entry + `hunterpie-analytics` command:
     ./install.sh
     hunterpie-analytics
3. Install the capture mod (included):
     ./install-mod.sh
   This copies hunt_dumper.lua into every Steam copy of Wilds that already has
   REFramework. If REFramework is missing, install it first
   (https://github.com/praydog/REFramework) and re-run.
4. Play a quest, then open Settings -> Import in the dashboard (or wait for the
   automatic recheck) to load the dump.

The Steam libraries are detected automatically, including Flatpak and Snap
installs. A custom export folder can be added under Settings -> Hunt exports.

Data and updates
----------------
- Hunt history: ~/.local/share/HunterPieAnalytics/hunts.db
- Uninstalling (./install.sh --uninstall) keeps your hunt history.
- In-app update checks download nothing on Linux; the pill opens the release
  page in your browser. Re-run install.sh over the extracted new version to
  update (your data stays).

Uninstall
---------
  ./install.sh --uninstall
  rm -rf ~/.local/share/HunterPieAnalytics    # only if you also want the data gone

Troubleshooting
---------------
- Nothing captured: confirm the mod is enabled in the in-game REFramework menu
  (HuntDumper) and that <game>/reframework/data/HuntExports/ has JSON files.
- No window appeared: the dashboard should open in your default browser. If it
  did not, use the URL printed in the console (a free local port is chosen).
- Older distro (glibc < 2.35): run from source instead (see the project README).
