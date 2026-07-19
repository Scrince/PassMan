# Changelog

All notable changes to PassMan are documented in this file.

This project follows a simple versioned changelog. Dates use `YYYY-MM-DD`.

## Unreleased

### Added

- Added startup recovery flow for missing default vaults. When `vault.dat` is not present in the usual application location, PassMan can load an existing `vault.dat` or `vault.dat.bak` from another folder and continue saving to that selected location.
- Added OS-specific release artifact folders under `release/v1.0.0/`.
- Added **Project Keys** sidebar mode for storing project-associated GPG keys with C/S/E/A roles. Each role stores a `.key` file (Base64 in the vault); the only `.asc` is the project public key half. Search covers project names, roles, fingerprints, key IDs, `.key` filenames, and notes. Key storage is separate from password entries in the UI and stored under `key_projects` in the encrypted vault model.
- Added **Authenticator** sidebar mode for TOTP/HOTP secrets with live codes, copy, add/edit, and import of `otpauth://` URIs / secret lists. Stored under `authenticator_entries` in the encrypted vault model.
- Added **Recovery** sidebar mode for account recovery keys, backup codes, and word lists (e.g. GitHub, BitLocker). Stored under `recovery_entries` in the encrypted vault model.
- Added **Seed** sidebar mode for 12/24-word cryptocurrency wallet seed phrases, optional passphrases, and notes. Stored under `seed_entries` in the encrypted vault model.
- Seed UI uses a numbered word grid with password-bullet masking, Show/Hide seed controls, and Copy Seed always copies the full space-separated phrase.
- Seed multi-word paste no longer leaves stale words in later grid slots; full 12/24 pastes replace the whole grid. Seed phrases are stored lowercased.
- Clipboard text copied by PassMan is flushed when the main window locks or closes.
- Vault save failures in Vault / Project Keys / Authenticator / Recovery / Seed now show an error dialog and roll back the in-memory change where practical.

### Changed

- Updated the Windows release executable after the external-vault loading change.
- Refreshed Windows release checksums and detached GPG signatures.
- Expanded `build.py` into a cross-platform packaging entry point for Windows, Linux (tar.gz + .deb), and macOS (.app + .dmg). See `docs/Build.txt`.
- Made `PassMan.spec` portable (relative `src/assets/` paths; optional `PASSMAN_TARGET_ARCH`).
- Frozen macOS builds now store `vault.dat` under `~/Library/Application Support/PassMan` instead of beside the executable.

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
