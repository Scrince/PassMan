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
- `uv` (see [uv installation](https://docs.astral.sh/uv/getting-started/installation/))
- A desktop environment capable of running PyQt6

```bash
uv sync --locked
uv run python src/main.py
```

Contributors should use `uv sync --locked --extra build --extra dev` and follow
the checks in [CONTRIBUTING.md](CONTRIBUTING.md). Release maintainers should
follow [docs/ReleaseProcess.md](docs/ReleaseProcess.md).

## Build

PassMan uses PyInstaller. Run packaging **on the target OS** (no cross-compile from Windows to Linux/macOS).

```bash
uv sync --locked --extra build
uv run python build.py             # auto-detects host platform
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

Generated build outputs and local release files are ignored. Published
installers and verification assets are attached to the
[GitHub Releases page](https://github.com/Scrince/PassMan/releases).

## Release Artifacts

The v1.0.7 release set is available from the GitHub Releases page:

```text
Windows: x64 executable, installer, SBOM, signatures, and checksums
macOS: Apple Silicon, Intel, and universal DMGs, SBOM, signatures, and checksums
Linux: Ubuntu 24.04 x64 tarball and Debian package, SBOM, signatures, and checksums
```

Each platform has a signed `SHA256SUMS` manifest and CycloneDX SBOM. The
release page prefixes manifest and SBOM filenames with the platform name so
all assets have unique names. The aggregate `docs/SHA256SUMS` and its detached
signature are kept in the source tree. SBOMs list build dependencies and
contain no vault contents or user data.

See `docs/WindowsRelease.txt`, `docs/MacOSRelease-v1.0.7.txt`, and
`docs/LinuxRelease-v1.0.7.txt` for artifact details and verification commands.
The macOS applications are ad-hoc signed and are not notarized; Gatekeeper may
warn when opening downloaded builds.

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

To verify the aggregate manifest, download the release packages and SBOMs into
their original `release/v1.0.7/<platform>/` paths first. For individual
prebuilt downloads, use the platform-prefixed checksum manifest attached to
the GitHub release. Its SBOM asset must be renamed from
`<platform>-SBOM.cdx.json` to `SBOM.cdx.json` before checking the manifest.

```bash
gpg --verify docs/SHA256SUMS.asc docs/SHA256SUMS
shasum -a 256 -c docs/SHA256SUMS
```

Verify a detached package signature:

```bash
gpg --verify PassMan-linux-x64.tar.gz.asc PassMan-linux-x64.tar.gz
gpg --verify PassMan-macOS-universal.dmg.asc PassMan-macOS-universal.dmg
gpg --verify PassMan.exe.asc PassMan.exe
gpg --verify PassMan-Setup-1.0.7.exe.asc PassMan-Setup-1.0.7.exe
```

How to re-sign after a rebuild is documented in `docs/Build.txt` (Release
signing). Current platform notes: `docs/WindowsRelease.txt`,
`docs/LinuxRelease-v1.0.7.txt`, `docs/MacOSRelease-v1.0.7.txt`, and
`docs/OpSec.txt`.

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
pyproject.toml             Project, build, dependency, and entry-point metadata
LICENSE                    MIT license
SECURITY.md                Vulnerability reporting policy
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
- Local release artifacts (published release downloads remain on GitHub Releases)
- Local vault files
- macOS AppleDouble metadata
- Private GPG key material

Before committing, check what will be included:

```bash
git add --dry-run .
git status --ignored
```

## License

PassMan is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Security Reporting

Please report security vulnerabilities through [GitHub's private vulnerability reporting](https://github.com/Scrince/PassMan/security/advisories/new). Do not post vulnerability details in a public issue. See [SECURITY.md](SECURITY.md) for the reporting policy.
