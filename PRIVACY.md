# Privacy

HunterPie Analytics runs entirely on your own computer.

## What it does *not* do

- It does **not** send your hunt data anywhere, and there is no telemetry,
  analytics, crash reporting or remote logging. The app's own network endpoint
  listens on `127.0.0.1` (loopback) only.
- It does **not** modify any game files.

## Network access (update check)

- On startup, and only while **Settings → Check for updates** is on (the
  default), the app asks GitHub for the latest release of
  [`Diegoeyza/HunterPie_Analytics`](https://github.com/Diegoeyza/HunterPie_Analytics)
  so it can offer to update itself in place.
- That request goes to `api.github.com`; the downloaded installer is checked
  against the release's published `SHA256SUMS.txt` before it runs.
- **Turn it off** in Settings to make zero network requests — the app then
  never contacts anything. No hunt data is ever included in the check.

## What it reads

- Hunt export JSON files written by the tools **you** installed:
  - the HunterPie analytics-export fork → `HuntExports/`
  - the REFramework HuntDumper mod → `reframework/data/HuntExports/`
- Monster name data bundled with the app.

## What it writes

- A SQLite database with your imported hunts, under your per-user app data:
  - Windows: `%LOCALAPPDATA%\HunterPieAnalytics\hunts.db`
- (The REFramework mod writes its JSON dumps into your game's
  `reframework/data/HuntExports/` folder; that is the mod, not this app.)

## Third-party components

- [HunterPie](https://github.com/HunterPie/HunterPie) and its analytics-export
  fork read game process memory to produce damage data. That behavior belongs
  to HunterPie, not to this dashboard.
- [REFramework](https://github.com/praydog/REFramework) is a game modding
  framework; the HuntDumper script runs inside it.

Uninstalling the app removes its files. Delete the `%LOCALAPPDATA%\HunterPieAnalytics`
folder to also remove your local database.
