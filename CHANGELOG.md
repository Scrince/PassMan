# Changelog

All notable changes to PassMan are documented in this file.

This project follows a simple versioned changelog. Dates use `YYYY-MM-DD`.

## Unreleased

### Added

- Added startup recovery flow for missing default vaults. When `vault.dat` is not present in the usual application location, PassMan can load an existing `vault.dat` or `vault.dat.bak` from another folder and continue saving to that selected location.
- Added OS-specific release artifact folders under `release/v1.0.0/`.

### Changed

- Updated the Windows release executable after the external-vault loading change.
- Refreshed Windows release checksums and detached GPG signatures.

## 1.0.0 - 2026-07-03

### Added

- Initial PassMan desktop password manager release.
- Added encrypted local vault storage using AES-256-GCM.
- Added Argon2id key derivation for the master password.
- Added website, wallet, drive, and custom entry types.
- Added custom fields and private notes for entries.
- Added search and sorting for vault entries.
- Added password generator with configurable character sets and length.
- Added clipboard copy with automatic clearing.
- Added auto-lock timer.
- Added theme selection.
- Added encrypted backup and restore workflow.
- Added release signatures, SHA-256 manifests, and release-signing public key.
- Added Windows, macOS, and Linux release artifacts.
