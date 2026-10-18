# Security

## Reporting a vulnerability

Open a private security advisory on GitHub
(https://github.com/Diegoeyza/HunterPie_Analytics/security/advisories/new) or
email the maintainer listed in the repository profile. Please do not open a
public issue for security problems.

Include: affected version (release tag), a description, and steps to reproduce.

## Scope

In scope:

- The FastAPI backend (`backend/`) and the desktop launcher (`packaging/`).
- The statically-exported dashboard (`dashboard/`).
- The REFramework Lua mod (`reframework/hunt_dumper.lua`).

Out of scope:

- HunterPie and its fork, and REFramework themselves — report those upstream.
- Issues that require the attacker to already control the local machine or the
  game install directory.

## Design notes

- The local server binds to `127.0.0.1` only and does not leave the machine.
- The app performs no network egress and no arbitrary code execution.
- Hunt export JSON is parsed defensively; malformed files are skipped with a
  warning rather than crashing the import.
