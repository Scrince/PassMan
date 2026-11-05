# Changelog

All notable changes to PassMan are documented in this file.

This project follows a simple versioned changelog. Dates use `YYYY-MM-DD`.

## 1.1.0 - 2026-11-04

### Added

- Added **Change Vault** in Settings to lock the current vault and unlock another existing vault. PassMan remembers the exact file after a successful switch.

### Fixed

- Closing Settings without changing its controls no longer triggers an unnecessary encrypted vault save, reducing close time.

### Release

- Built the Windows x64 executable, installer, and CycloneDX SBOM locally with the Settings close-time fix. Authenticode-signed both executables and OpenPGP-signed the artifacts and checksum manifests.

## 1.0.8 - 2026-11-03

### Added

- Added import of password entries from Apple Passwords CSV exports, including titles, URLs, usernames, passwords, and notes.
- Added the **Import** action to the left sidebar for Apple Passwords CSV files.
- Added a review prompt showing additions, updates, unchanged records, and deletions before applying Apple Passwords imports.
- Apple Passwords imports track their own entries, update changed logins, and delete previously imported entries missing from a later CSV. Manually created entries remain untouched.
- Apple Passwords CSV imports also add, update, and reconcile valid `OTPAuth` codes in Authenticator mode. Malformed nonempty `OTPAuth` values stop the import before changes are applied.

### Fixed

- Preserved leading and trailing spaces in imported passwords and cleared stored passwords when the next complete CSV has an empty Password cell.
- Kept entry identity and custom fields when a unique Apple account changes its website URL path.
- Rejected malformed URLs and incomplete CSV rows before the import preview or vault changes.

### Release

- Built the Windows x64 executable, installer, and CycloneDX SBOM with locked dependencies; signed the executable and installer with the local Authenticode certificate and signed all release artifacts and manifests with OpenPGP.
- Published v1.0.8 packages, SBOMs, OpenPGP signatures, and checksum manifests on GitHub Releases; excluded vault data and private signing material from the source commit and release uploads.
- Built and signed macOS arm64, x86_64, and universal2 DMGs with a CycloneDX SBOM and verified package, platform, and aggregate checksum signatures.
- Built and signed the Ubuntu 24.04 Linux x64 standalone tarball and Debian package in Docker, with a CycloneDX SBOM and verified checksums.
- Corrected Debian package tar headers so the v1.0.8 package installs with `dpkg` on Ubuntu 24.04.

## 1.0.7 - 2026-10-30

### Fixed

- Vault loading now rejects malformed records instead of silently omitting them and losing them on a later save.
- Increased the Authenticator editor window and text field widths so full account names and email addresses are easier to read.

### Release

- Built and signed Windows x64 executable, installer, and SBOM, alongside the completed macOS and Ubuntu 24.04 Linux v1.0.7 packages.

## 1.0.6 - 2026-10-30

### Fixed

- Updated authenticator codes and TOTP countdowns every second while the Authenticator panel is visible.
- Stored generated PyInstaller specs under the ignored build directory so Linux and Windows CLI builds do not replace the portable macOS spec.

### Added

- Built and signed macOS arm64, x64, and universal DMGs plus Ubuntu 24.04 Linux x64 tar.gz and Debian packages.
- Added CycloneDX SBOMs, signed platform and aggregate checksum manifests, and platform verification notes for the macOS and Linux packages.
- Added a CycloneDX build-environment SBOM generator.

## 1.0.5 - 2026-10-24

### Security

- Bound every vault header field to AES-256-GCM authentication. Existing v1 vaults remain readable and migrate to v2 after a successful unlock, with the original preserved as the backup.
- Made vault and backup writes atomic so an interrupted backup stage cannot truncate the active vault.

### Added

- Added a Settings action to move the active vault and backup. PassMan copies and verifies both files before switching the remembered location and removing the originals.
- Added regression tests for encryption compatibility, migration, tampering, atomic writes, vault moves, and accessible settings controls, plus cross-platform CI.
- Built and signed the Windows x64 v1.0.5 executable, installer, and SBOM. Linux and macOS builds will be produced separately on their target machines.

## 1.0.4 - 2026-10-24

### Added

- Added a folder picker for new vault creation. PassMan stores `vault.dat` and `vault.dat.bak` in the chosen directory and remembers that directory for future launches.

### Security

- Retained the patched `cryptography` and PyInstaller versions and the release-output vault-data guard introduced for v1.0.3.
- Built the Windows x64 executable, installer, and CycloneDX SBOM for v1.0.4.

## 1.0.3 - 2026-10-24

### Security

- Updated `cryptography` to 50.0.2 to include the fix for CVE-2026-69247.
- Updated PyInstaller to 6.22.3 to include the fix for GHSA-9fxf-4qw3-ghmr.
- Added a release-build guard that refuses to write artifacts to an output directory containing runtime vault files.
- Kept the existing v1.0.2 release directory unchanged; v1.0.3 artifacts use their own versioned directory.
- Built and OpenPGP-signed the Windows x64 executable and installer with the updated dependencies. Linux/macOS packages require builds on their target operating systems.
- Added a CycloneDX SBOM for the Windows v1.0.3 build environment and packaging dependencies.

## 1.0.2 - 2026-10-22

### Added

- Added password-protected YellowSphere ARC V3 `.arc` export for seed phrases. ARC files include the mnemonic only; the PassMan wallet passphrase, label, and notes are not exported.
- Added ARC export round-trip and input validation tests.
- Built and OpenPGP-signed the v1.0.2 Windows x64 executable and installer; added their checksums to signed Windows and aggregate manifests.

### Changed

- Renamed the Seed panel's `.arc` import button to **Import**.
- Updated the Windows release version to 1.0.2.

## 1.0.1 - 2026-10-22

### Added

- Added startup recovery flow for missing default vaults. When `vault.dat` is not present in the usual application location, PassMan can load an existing `vault.dat` or `vault.dat.bak` from another folder and continue saving to that selected location.
- Added OS-specific release artifact folders under `release/v1.0.0/`.
- Added **Project Keys** sidebar mode for storing project-associated GPG keys with C/S/E/A roles. Each role stores a `.key` file (Base64 in the vault); the only `.asc` is the project public key half. Search covers project names, roles, fingerprints, key IDs, `.key` filenames, and notes. Key storage is separate from password entries in the UI and stored under `key_projects` in the encrypted vault model.
- Added **Authenticator** sidebar mode for TOTP/HOTP secrets with live codes, copy, add/edit, and import of `otpauth://` URIs / secret lists. Stored under `authenticator_entries` in the encrypted vault model.
- Added **Recovery** sidebar mode for account recovery keys, backup codes, and word lists (e.g. GitHub, BitLocker). Stored under `recovery_entries` in the encrypted vault model.
- Added **Seed** sidebar mode for 12/24-word cryptocurrency wallet seed phrases, optional passphrases, and notes. Stored under `seed_entries` in the encrypted vault model.
- Added import of YellowSphere ARC V3 `.arc` seed backups, including password, keyfile, combined protection, and unprotected files.
- Added tests for ARC V3 credential modes, encrypted keyfiles, armored plaintext files, and tamper rejection.
- Built and OpenPGP-signed the v1.0.1 Windows x64 executable and installer; added their checksums to signed Windows and aggregate manifests.
- Seed UI uses a numbered word grid with password-bullet masking, Show/Hide seed controls, and Copy Seed always copies the full space-separated phrase.
- Seed multi-word paste no longer leaves stale words in later grid slots; full 12/24 pastes replace the whole grid. Seed phrases are stored lowercased.
- Clipboard text copied by PassMan is flushed when the main window locks or closes.
- Vault save failures in Vault / Project Keys / Authenticator / Recovery / Seed now show an error dialog and roll back the in-memory change where practical.

### Changed

- Rebuilt the Windows release executable with the seed-paste and vault filesystem error fixes.
- Refreshed Windows release checksums and detached GPG signatures.
- Verified the Windows package signature and all per-platform and aggregate release checksums and signatures on 2026-10-17.
- Reject seed phrase pastes with unsupported word counts instead of silently truncating them.
- Handle filesystem errors during backup, restore, startup recovery, and vault creation with UI errors instead of uncaught exceptions.
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
