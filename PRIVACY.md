# Privacy

HunterPie Analytics runs entirely on your own computer.

## What it does *not* do

- It does **not** connect to the internet. There is no telemetry, no analytics,
  no crash reporting, no auto-update, and no remote logging. The app is the
  only network endpoint and it listens on `127.0.0.1` (loopback) only.
- It does **not** send your hunt data anywhere.
- It does **not** modify any game files.

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
