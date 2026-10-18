# Code signing

## Current status

The direct-download Windows binaries (the installer and the app `.exe`) are
**not code signed** at this time. As a result:

- Windows SmartScreen may show **"Windows protected your PC"** on first run.
  Choose *More info → Run anyway* if you trust the download source.
- Some antivirus engines flag unsigned PyInstaller bundles heuristically.
- Releases always publish `SHA256SUMS.txt` and GitHub build-provenance
  attestations, so you can verify integrity and origin regardless.

The **Microsoft Store** build is re-signed by Microsoft and shows **no
SmartScreen warning**. If you want a warning-free install, use the Store.

## Planned: SignPath Foundation

This project intends to use free open-source code signing from the
[SignPath Foundation](https://signpath.org/) once the project has enough
verifiable reputation to be accepted. When that is enabled, the policy below
applies.

> When enabled: **Free code signing provided by [SignPath.io](https://signpath.io/),
> certificate by [SignPath Foundation](https://signpath.org/).**

The REFramework Lua mod ships as plain text and is never signed. The HunterPie
analytics-export fork is built upstream and included in the installer as an
upstream open-source binary.

## Roles

This is a small project; roles may be held by the same person.

- **Authors** (commit access / merge without extra review):
  [@Diegoeyza](https://github.com/Diegoeyza)
- **Reviewers** (review contributions): [@Diegoeyza](https://github.com/Diegoeyza)
- **Approvers** (approve each signing request): [@Diegoeyza](https://github.com/Diegoeyza)

## Privacy

This program will not transfer any information to other networked systems
unless specifically requested by the user or the person installing or operating
it. See [PRIVACY.md](../PRIVACY.md).

## Verification

- Every release ships a `SHA256SUMS.txt`.
- Build provenance is attested via GitHub Actions artifact attestations
  (`gh attestation verify`).
- Once signing is enabled, verify a binary with `signtool verify /pa /v <file>`.

## Build integrity

Binaries are produced only by the workflows in `.github/workflows/` from source
in this repository.
