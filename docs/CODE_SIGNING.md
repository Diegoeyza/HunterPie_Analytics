# Code signing policy

This project's Windows binaries are code signed as part of the release
pipeline. Releases are built from source by GitHub Actions and signed so users
can verify that a download really came from this repository.

**Free code signing provided by [SignPath.io](https://signpath.io/), certificate
by [SignPath Foundation](https://signpath.org/).**

## What gets signed

- `HunterPieAnalytics.exe` (the desktop launcher) and the DLLs in its onedir
  bundle.
- The `HunterPieAnalytics-Setup-*.exe` installer.

Artifacts published to the [Microsoft Store](https://apps.microsoft.com/) are
re-signed by Microsoft. The REFramework Lua mod ships as plain text and is not
signed. The HunterPie analytics-export fork is built upstream and included in
the installer as an upstream open-source binary.

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
- Verify a signed binary with `signtool verify /pa /v <file>`.

## Build integrity

Binaries are produced only by the workflows in `.github/workflows/` from source
in this repository. Every signing request is reviewed and approved by a project
approver before SignPath issues a signature.
