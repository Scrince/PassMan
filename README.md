# PassMan

PassMan is a local desktop password manager built with Python and PyQt6. It stores entries in an encrypted `vault.dat` file, protected by a master password and designed to stay offline-first.

Current application version: `1.0.7`

The application version is controlled from `src/version.py`.

Release history is tracked in `CHANGELOG.md`.

## Features

- Encrypted local vault using AES-256-GCM
- Authenticated vault metadata with transparent migration from the previous vault format
- Argon2id key derivation for the master password
- Website, wallet, drive, and custom entry types
- Custom fields per entry
- Private notes per entry
- Search by entry name, type, field name, field value, notes, or timestamps
- Sort by name, created date, or modified date
- Project Keys mode for C/S/E/A GPG `.key` files plus a project public `.asc` half
- Authenticator mode for TOTP/HOTP codes with `otpauth://` import
- Seed mode with YellowSphere ARC V3 `.arc` import and password-protected export (password, keyfile, combined, and unprotected imports)
- Password generator with configurable length and character sets
- Clipboard copy with automatic clear timer
- Auto-lock timer
- Theme selection
- Encrypted backup and restore workflow
- Move the active vault and its backup to another folder from Settings
- Release signatures and checksums for packaged builds

Seed exports use the YellowSphere ARC V3 password-protected format. The `.arc` file contains only the mnemonic; PassMan wallet passphrases, labels, and notes are not included.

## Security Model

PassMan encrypts vault contents before writing them to disk.

- Encryption: `AES-256-GCM`
- KDF: `Argon2id`
- Default KDF parameters: `time_cost=3`, `memory_cost=65536`, `parallelism=4`, `hash_len=32`
- Vault file: `vault.dat`
- Automatic backup file: `vault.dat.bak`

The master password is not stored. If the master password is lost, the vault cannot be recovered unless another usable backup exists.

New vault saves use format version 2, which authenticates the complete parsed
header along with the encrypted contents. Existing version 1 vaults remain
readable and are migrated after a successful unlock; the prior bytes are kept
as `vault.dat.bak` during that migration.

## Vault Location

When no existing vault is found, PassMan lets you choose a folder for a new
vault. It creates both `vault.dat` and `vault.dat.bak` in that folder and
remembers the chosen folder for later launches. The remembered location is an
application setting stored outside the vault. The paths below are the initial
locations PassMan uses when no folder has been chosen yet.
The folder can also be changed later from **Settings → Move Vault**. PassMan
copies and verifies the vault and backup at the destination before switching
the saved location and removing the original files.

When running from source, the initial location is the project root.

When running as a frozen Linux build, PassMan stores the vault under:

```text
$XDG_DATA_HOME/PassMan/vault.dat
```

If `XDG_DATA_HOME` is not set, the default is:

```text
~/.local/share/PassMan/vault.dat
```

On macOS packaged builds:

```text
~/Library/Application Support/PassMan/vault.dat
```

On Windows packaged builds:

```text
%LOCALAPPDATA%\PassMan\vault.dat
```

On Windows, if `vault.dat` or `vault.dat.bak` is present beside the executable,
PassMan uses that directory for the vault and its automatic backup before
checking `%LOCALAPPDATA%\PassMan`. If neither file is beside the executable,
the location above remains the default.

If no `vault.dat` exists at the remembered or initial location on startup,
PassMan offers to load an existing `vault.dat` or `vault.dat.bak` from another
folder. When an existing vault is selected, its folder is remembered and future
saves and automatic backups stay there. If you choose to create a new vault,
PassMan opens a folder picker; canceling it exits without creating a vault.

## Run From Source

Requirements:

- Python 3.12 or newer is recommended; Python 3.14 is validated in the current development environment
- `pip`
- A desktop environment capable of running PyQt6

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

## Build

PassMan uses PyInstaller. Run packaging **on the target OS** (no cross-compile from Windows to Linux/macOS).

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python build.py                    # auto-detects host platform
```

Platform-specific examples:

```bash
# Linux (on a Linux machine) → tar.gz + .deb under dist/ and release/v*/
python build.py --platform linux

# macOS native arch → .app + .dmg
python build.py --platform macos

# macOS Apple Silicon / Intel / universal2
python build.py --platform macos --arch arm64
python build.py --platform macos --arch x86_64
python build.py --platform macos --arch universal2

# Windows → standalone .exe plus setup installer (Inno Setup 6 or newer)
python build.py --platform windows

# PyInstaller only (skip archive, disk-image, and installer packaging)
python build.py --skip-package
```

Full prerequisites, library notes, signing, and troubleshooting: `docs/Build.txt`.

Build outputs are ignored. Signed release artifacts for the listed Windows
releases and the v1.0.2, v1.0.6, and v1.0.7 macOS/Linux releases are retained
in the repo; other generated release artifacts are ignored:

```text
build/
dist/
release/ (except the signed v1.0.0, v1.0.1, v1.0.2, v1.0.3, v1.0.4, and v1.0.5 Windows
          artifacts; v1.0.2 macOS, Linux, and Ubuntu artifacts; and v1.0.6/v1.0.7 macOS and Linux artifacts)
.venv/
.venv-*/
```

## Release Artifacts

The v1.0.7 Windows x64 release includes:

```text
release/v1.0.7/windows/PassMan.exe
release/v1.0.7/windows/PassMan.exe.asc
release/v1.0.7/windows/PassMan-Setup-1.0.7.exe
release/v1.0.7/windows/PassMan-Setup-1.0.7.exe.asc
release/v1.0.7/windows/SBOM.cdx.json
release/v1.0.7/windows/SBOM.cdx.json.asc
release/v1.0.7/windows/SHA256SUMS
release/v1.0.7/windows/SHA256SUMS.asc
```

The v1.0.7 macOS release contains Apple Silicon, Intel, and universal disk
images. The v1.0.7 Linux release contains x64 tar.gz and Debian packages built
in Ubuntu 24.04 LTS. All three platform folders include signed packages, a
CycloneDX SBOM, and signed SHA-256 manifests. See `docs/WindowsRelease.txt`,
`docs/MacOSRelease-v1.0.7.txt`, and `docs/LinuxRelease-v1.0.7.txt` for
verification details.

The release includes an SBOM (Software Bill of Materials), a machine-readable
inventory of the software components and dependency versions used for the
build. The CycloneDX file helps reviewers check the release's dependencies for
known security issues. It describes the build environment and contains no
vault contents, passwords, or other user data.

The previous Linux v1.0.2 release includes native x86-64 and ARM64 tarballs
and Debian packages:

```text
release/v1.0.2/linux/PassMan-linux-x64.tar.gz
release/v1.0.2/linux/PassMan-linux-x64.tar.gz.asc
release/v1.0.2/linux/PassMan-linux-x64.deb
release/v1.0.2/linux/PassMan-linux-x64.deb.asc
release/v1.0.2/linux/PassMan-linux-arm64.tar.gz
release/v1.0.2/linux/PassMan-linux-arm64.tar.gz.asc
release/v1.0.2/linux/PassMan-linux-arm64.deb
release/v1.0.2/linux/PassMan-linux-arm64.deb.asc
release/v1.0.2/linux/SHA256SUMS
release/v1.0.2/linux/SHA256SUMS.asc
```

The Ubuntu 24.04 LTS v1.0.2 release is built in Ubuntu Noble containers for
x86-64 and ARM64. It has separately named tarballs and Debian packages so the
Ubuntu-targeted builds are distinct from the generic Debian Linux builds:

```text
release/v1.0.2/linux/ubuntu-24.04/PassMan-Ubuntu-24.04-x64.tar.gz
release/v1.0.2/linux/ubuntu-24.04/PassMan-Ubuntu-24.04-x64.tar.gz.asc
release/v1.0.2/linux/ubuntu-24.04/PassMan-Ubuntu-24.04-x64.deb
release/v1.0.2/linux/ubuntu-24.04/PassMan-Ubuntu-24.04-x64.deb.asc
release/v1.0.2/linux/ubuntu-24.04/PassMan-Ubuntu-24.04-arm64.tar.gz
release/v1.0.2/linux/ubuntu-24.04/PassMan-Ubuntu-24.04-arm64.tar.gz.asc
release/v1.0.2/linux/ubuntu-24.04/PassMan-Ubuntu-24.04-arm64.deb
release/v1.0.2/linux/ubuntu-24.04/PassMan-Ubuntu-24.04-arm64.deb.asc
release/v1.0.2/linux/ubuntu-24.04/SHA256SUMS
release/v1.0.2/linux/ubuntu-24.04/SHA256SUMS.asc
```

The previous macOS v1.0.2 release includes Apple Silicon, Intel, and universal2
disk images:

```text
release/v1.0.2/macos/PassMan-macOS-arm64.dmg
release/v1.0.2/macos/PassMan-macOS-arm64.dmg.asc
release/v1.0.2/macos/PassMan-macOS-x64.dmg
release/v1.0.2/macos/PassMan-macOS-x64.dmg.asc
release/v1.0.2/macos/PassMan-macOS-universal.dmg
release/v1.0.2/macos/PassMan-macOS-universal.dmg.asc
release/v1.0.2/macos/SHA256SUMS
release/v1.0.2/macos/SHA256SUMS.asc
```

The previous v1.0.0 cross-platform artifacts remain available:

```text
release/v1.0.0/windows/PassMan.exe
release/v1.0.0/windows/PassMan-Setup-1.0.0.exe
release/v1.0.0/macos/PassMan-macOS-x64.dmg
release/v1.0.0/macos/PassMan-macOS-arm64.dmg
release/v1.0.0/macos/PassMan-macOS-universal.dmg
release/v1.0.0/linux/PassMan-linux-x64.tar.gz
release/v1.0.0/linux/PassMan-linux-x64.deb
```

The macOS universal2 DMG contains both `x86_64` and `arm64` application slices. The v1.0.2 Linux release includes `amd64` and `arm64`; the earlier v1.0.0 Linux release is `amd64`.

Release artifacts are organized by version and operating system. New release
suites use one top-level platform folder each: `windows/`, `macos/`, and
`linux/`. Ubuntu-specific Linux packages belong under
`linux/ubuntu-<version>/`. v1.0.7 is the current release for Windows, macOS,
and Linux. v1.0.5 and v1.0.1 are previous Windows releases, and v1.0.0
contains earlier packages for all three operating systems.
Each packaged application and each platform checksum manifest has an adjacent
`.asc` detached signature. The checksum manifests list hashes for the packages;
they do not list hashes of the `.asc` files. The aggregate manifest at
`docs/SHA256SUMS` covers the release packages and has its own detached signature.

```text
release/v1.0.5/
  windows/  PassMan.exe and PassMan-Setup-1.0.5.exe
release/v1.0.7/
  macos/    Intel, Apple Silicon, and universal DMGs
  linux/    x64 tar.gz and Debian packages
  windows/  PassMan.exe and PassMan-Setup-1.0.7.exe
release/v1.0.6/
  macos/    Intel, Apple Silicon, and universal DMGs
  linux/    x64 tar.gz and Debian packages
release/v1.0.4/
  windows/  PassMan.exe and PassMan-Setup-1.0.4.exe
release/v1.0.3/
  windows/  PassMan.exe and PassMan-Setup-1.0.3.exe
release/v1.0.2/
  windows/  PassMan.exe and PassMan-Setup-1.0.2.exe
  macos/    Intel, Apple Silicon, and universal2 DMGs
  linux/    Generic Linux x86-64 and ARM64 packages
    ubuntu-24.04/ Ubuntu 24.04 LTS packages
docs/
  PassMan_Release_Signing_2026_pubkey.asc
  PassMan_Local_Code_Signing_2026.cer
  SHA256SUMS             Aggregate checksum manifest for release packages
  SHA256SUMS.asc         Detached signature for the aggregate manifest
  LinuxRelease.txt       Generic Linux package verification notes
  UbuntuRelease.txt      Ubuntu 24.04 package verification notes
  MacOSRelease.txt       macOS DMG verification notes
  MacOSRelease-v1.0.7.txt Current macOS release verification notes
  LinuxRelease-v1.0.7.txt Current Linux release verification notes
  WindowsRelease.txt     Windows executable verification notes
  Build.txt              Packaging and re-signing procedure
```

## Verify Releases

Every packaged application (Linux tar.gz/deb, macOS DMGs, Windows exe and
setup installer) ships with a detached OpenPGP signature (`.asc`) from the
PassMan release-signing key and is listed in a per-OS `SHA256SUMS` plus the
aggregate `docs/SHA256SUMS`.

Public key:

```text
docs/PassMan_Release_Signing_2026_pubkey.asc
```

Import the public key:

```bash
gpg --import docs/PassMan_Release_Signing_2026_pubkey.asc
```

Verify the aggregate manifest, then an OS folder:

```bash
gpg --verify docs/SHA256SUMS.asc docs/SHA256SUMS

cd release/v1.0.5/windows
shasum -a 256 -c SHA256SUMS
```

Verify a detached package signature:

```bash
gpg --verify PassMan-linux-x64.tar.gz.asc PassMan-linux-x64.tar.gz
gpg --verify PassMan-macOS-universal.dmg.asc PassMan-macOS-universal.dmg
gpg --verify release/v1.0.5/windows/PassMan.exe.asc release/v1.0.5/windows/PassMan.exe
gpg --verify release/v1.0.5/windows/PassMan-Setup-1.0.5.exe.asc release/v1.0.5/windows/PassMan-Setup-1.0.5.exe
gpg --verify release/v1.0.2/windows/PassMan-Setup-1.0.2.exe.asc release/v1.0.2/windows/PassMan-Setup-1.0.2.exe
```

How to re-sign after a rebuild is documented in `docs/Build.txt` (Release
signing). Platform notes: `docs/LinuxRelease.txt`, `docs/UbuntuRelease.txt`,
`docs/MacOSRelease.txt`, and `docs/OpSec.txt`.

Windows release artifact details, checksum, and verification commands are in
`docs/WindowsRelease.txt`.

## Local Code-Signing Certificate

PassMan includes a public self-signed code-signing certificate for local Windows Authenticode verification experiments:

```text
docs/PassMan_Local_Code_Signing_2026.cer
```

Certificate summary:

```text
Subject: CN=PassMan Local Code Signing
Thumbprint: 3BB73D97DCE4216AF3DB571442D8DC7A773FBC71
Algorithm: RSA 3072-bit, SHA-256
Enhanced key usage: Code Signing
Valid: 2026-07-16 to 9999-12-30 (practical non-expiry)
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
  models/                 Vault, entry, and project-key data models
  utils/                  File paths, clipboard handling, themes
  assets/                 App icons and platform-specific icon assets
build.py                  Cross-platform PyInstaller packaging script
scripts/generate_release_sbom.py  CycloneDX build-environment inventory
requirements.txt          Python dependencies
PassMan.spec              Portable PyInstaller spec (macOS .app + onedir)
installer/PassMan.iss     Windows setup installer definition
docs/Build.txt            Linux/macOS/Windows build instructions
```

## Git Hygiene

The repository is configured to ignore:

- Virtual environments
- Python caches
- PyInstaller build output
- Release artifacts except the explicitly listed v1.0.2 platform packages and manifests, v1.0.3/v1.0.4/v1.0.5 Windows artifacts, and v1.0.6/v1.0.7 macOS/Linux artifacts
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
