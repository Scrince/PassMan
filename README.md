# PassMan

PassMan is a local desktop password manager built with Python and PyQt6. It stores entries in an encrypted `vault.dat` file, protected by a master password and designed to stay offline-first.

Current application version: `1.0.0`

The application version is controlled from `src/version.py`.

Release history is tracked in `CHANGELOG.md`.

## Features

- Encrypted local vault using AES-256-GCM
- Argon2id key derivation for the master password
- Website, wallet, drive, and custom entry types
- Custom fields per entry
- Private notes per entry
- Search by entry name, type, field name, field value, notes, or timestamps
- Sort by name, created date, or modified date
- Password generator with configurable length and character sets
- Clipboard copy with automatic clear timer
- Auto-lock timer
- Theme selection
- Encrypted backup and restore workflow
- Release signatures and checksums for packaged builds

## Security Model

PassMan encrypts vault contents before writing them to disk.

- Encryption: `AES-256-GCM`
- KDF: `Argon2id`
- Default KDF parameters: `time_cost=3`, `memory_cost=65536`, `parallelism=4`, `hash_len=32`
- Vault file: `vault.dat`
- Automatic backup file: `vault.dat.bak`

The master password is not stored. If the master password is lost, the vault cannot be recovered unless another usable backup exists.

## Vault Location

When running from source, the vault is stored in the project root.

When running as a frozen Linux build, PassMan stores the vault under:

```text
$XDG_DATA_HOME/PassMan/vault.dat
```

If `XDG_DATA_HOME` is not set, the default is:

```text
~/.local/share/PassMan/vault.dat
```

On macOS and Windows packaged builds, the app uses the executable folder.

If no `vault.dat` exists at the usual location on startup, PassMan offers to load an existing
`vault.dat` or `vault.dat.bak` from another folder. When an existing vault is selected, future
saves and automatic backups stay in that selected location. If no existing vault is selected,
PassMan creates a new `vault.dat` and `vault.dat.bak` at the usual location.

## Run From Source

Requirements:

- Python 3.12 or newer recommended
- `pip`
- A desktop environment capable of running PyQt6

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

## Build

PassMan uses PyInstaller for packaging.

```bash
python build.py
```

The current `build.py` script packages the default Windows-style single-file build. macOS and Linux release builds were produced with PyInstaller commands tailored for each platform and are emitted under `dist/`.

Generated build and release outputs are intentionally ignored by git:

```text
build/
dist/
release/
.venv/
.venv-*/
```

## Release Artifacts

The prepared release set includes:

```text
release/v1.0.0/windows/PassMan.exe
release/v1.0.0/macos/PassMan-macOS-x64.dmg
release/v1.0.0/macos/PassMan-macOS-arm64.dmg
release/v1.0.0/macos/PassMan-macOS-universal.dmg
release/v1.0.0/linux/PassMan-linux-x64.tar.gz
release/v1.0.0/linux/PassMan-linux-x64.deb
```

The macOS universal build contains both `x86_64` and `arm64` slices. The Linux build is `linux/amd64`.

Final release artifacts are organized by version and operating system:

```text
release/v1.0.0/
  windows/               Windows executable, signature, and checksum manifest
  macos/                 Intel, Apple Silicon, and universal DMGs with signatures
  linux/                 tar.gz and deb packages with signatures
docs/
  PassMan_Release_Signing_2026_pubkey.asc
  PassMan_Local_Code_Signing_2026.cer
  SHA256SUMS             Aggregate checksum manifest for all release artifacts
  SHA256SUMS.asc         Detached signature for the aggregate checksum manifest
```

## Verify Releases

Release artifacts are signed with detached GPG signatures and listed in `SHA256SUMS`.

Public key:

```text
docs/PassMan_Release_Signing_2026_pubkey.asc
```

Import the public key:

```bash
gpg --import docs/PassMan_Release_Signing_2026_pubkey.asc
```

Verify checksums from the OS-specific release folder:

```bash
cd release/v1.0.0/linux
shasum -a 256 -c SHA256SUMS
```

Verify a detached signature:

```bash
gpg --verify PassMan-linux-x64.tar.gz.asc PassMan-linux-x64.tar.gz
```

The aggregate checksum file and detached signature are kept under `docs/`:

```bash
gpg --verify docs/SHA256SUMS.asc docs/SHA256SUMS
```

## Local Code-Signing Certificate

PassMan includes a public self-signed code-signing certificate for local Windows Authenticode verification experiments:

```text
docs/PassMan_Local_Code_Signing_2026.cer
```

Certificate summary:

```text
Subject: CN=PassMan Local Code Signing
Thumbprint: 554A90C89385DD8C72D2341FF28BE155F3FC511A
Algorithm: RSA 3072-bit, SHA-256
Enhanced key usage: Code Signing
Valid: 2026-07-04 to 2028-07-04
```

This certificate is self-signed and local-only. It is not a replacement for a publicly trusted Windows publisher certificate.

## Release Signing Key

PassMan uses a repo-local GPG home, matching the release-signing layout used by the companion YellowSphere project:

```text
.gnupg-release/
```

Current release signing identity:

```text
PassMan Release Signing (2026) <release@passman.local>
Fingerprint: 7858 E51C 98AD 2541 5098  9EF3 1F4D F0EB 1C80 C710
Key ID: 1F4DF0EB1C80C710
```

Private key material is explicitly ignored and must not be committed:

```text
.gnupg-release/private-keys-v1.d/*.key
```

## Project Layout

```text
src/
  main.py                 App entry point
  crypto/                 Encryption, KDF, vault read/write logic
  gui/                    PyQt6 windows and widgets
  models/                 Vault and entry data models
  utils/                  File paths, clipboard handling, themes
  assets/                 App icons and platform-specific icon assets
build.py                  Convenience PyInstaller build script
requirements.txt          Python dependencies
PassMan.spec              PyInstaller spec
```

## Git Hygiene

The repository is configured to ignore:

- Virtual environments
- Python caches
- PyInstaller build output
- Release artifacts
- Local vault files
- macOS AppleDouble metadata
- Private GPG key material

Before committing, check what will be included:

```bash
git add --dry-run .
git status --ignored
```

## License

No license file is currently included. Add one before publishing if you want to define reuse, distribution, or contribution terms.
