# PassMan Security Policy

## Purpose and authority

PassMan stores credentials, authenticator seeds, recovery material, wallet
phrases, and OpenPGP key files. A security report should identify the violated
trust boundary and the attacker capability needed to cross it. See
[`THREAT_MODEL.md`](THREAT_MODEL.md) for assets, data flows, and residual risks;
[`docs/Encryption.txt`](docs/Encryption.txt) for the byte level vault format;
and [`docs/OpSec.txt`](docs/OpSec.txt) for operating practice.

This policy describes the repository implementation and its disclosure
process. It is not an independent audit or a guarantee that every package or
dependency is free of defects.

## Supported versions

Security fixes target the latest stable version listed on the
[PassMan releases page](https://github.com/Scrince/PassMan/releases). An older
version may receive a fix only when maintainers explicitly announce one.
The source tree currently identifies itself as 1.0.8 in `src/version.py`;
confirm the installed binary's version and corresponding release notes when
reporting a package-specific defect. A source checkout, local build, and
published binary can have different build histories.

## Confidential reporting

Use [GitHub private vulnerability reporting](https://github.com/Scrince/PassMan/security/advisories/new)
for a suspected vulnerability. If that channel is unavailable, use the
[maintainer's GitHub profile](https://github.com/Scrince) to arrange a private
channel before sending exploit details. Do not place an unpatched exploit in
a public issue, discussion, pull request, review, or release comment.

Provide a reproducible report using **synthetic** data:

1. Affected PassMan version, platform, package type, Python version for a
   source run, and whether the build is official, local, or modified.
2. Attacker starting position: stolen encrypted file, ability to edit a file,
   access to an unlocked desktop, malicious import file, compromised build
   input, or another explicit capability.
3. Exact input shape and steps, including relevant vault version, field names,
   byte lengths, encoding, and the operation that crosses the boundary.
4. Expected security invariant, observed result, and impact on confidentiality,
   integrity, or availability. State whether exploitation requires user
   approval or an unlocked vault.
5. A safe proof of concept and proposed mitigation, if available. Redact
   paths or logs that reveal usernames, account inventory, machine identity,
   or secrets.

Never attach a real `vault.dat`, `vault.dat.bak`, Apple Passwords CSV, private
`.key` file, ARC keyfile, mnemonic, TOTP secret, recovery code, master password,
decrypted JSON, release private key, or clipboard capture. An encrypted vault
is still material for offline guessing. A private issue attachment is not a
secret storage system.

Maintainers should acknowledge and triage a private report, reproduce it with
synthetic data, identify affected versions and trust boundaries, prepare a
fix and focused regression coverage where appropriate, verify the final
release bytes, and coordinate disclosure after users have an update path.
No fixed response or remediation deadline is promised here. Reporters should
avoid public disclosure while a coordinated fix is being prepared, while
retaining control of their own disclosure decisions.

## What constitutes a security issue

Examples include:

- Decryption that accepts a modified v2 ciphertext or parsed header without
  the correct master password, or nonce/KDF handling that enables a practical
  confidentiality or integrity break.
- A failed unlock or malformed vault that silently drops authenticated
  records and later saves the reduced model, or leaves decrypted state active.
- Import reconciliation that changes or deletes a manually created record
  without explicit user action, or mutates the vault after rejecting input.
- An export or backup operation that unexpectedly writes plaintext secrets,
  exposes private key bytes in diagnostics, or places a real vault or private
  release signing key into a package.
- A signature or checksum workflow that permits a substituted executable to
  be presented as authenticated by the release key.
- Code execution or unauthorized file modification caused by a crafted vault,
  CSV, ARC, or key file.

An encrypted vault being guessable with a weak master password, a clipboard
manager retaining a copied secret, or malware reading an unlocked process is
within the documented residual risk unless a separate implementation defect
amplifies it. Availability failures and data loss are still worth reporting;
explain whether the input is malicious, accidental, or both.

## Security properties and limits

### Vault at rest

Current writes use vault format version 2. Argon2id derives a 32 byte key
from the UTF-8 master password and a fresh 16 byte salt. AES-256-GCM encrypts
the model under a fresh 12 byte nonce. The complete parsed header is encoded
as canonical JSON and authenticated as additional data. The 16 byte GCM tag
is appended to ciphertext before Base64 encoding. Exact parameters, parsing,
legacy v1 handling, and write order are in `docs/Encryption.txt`.

This authenticates file content, not its age or provenance. A valid older
vault can be replayed, a file can be deleted, and a party knowing the master
password can create a valid replacement. Backups retain old secrets and may
remain decryptable with an old master password after a password change. New
saves do not erase older filesystem copies or snapshots.

Vault writes use same-directory temporary files and replacement. PassMan
attempts restrictive permissions and directory synchronization, but the host
filesystem determines actual ACLs, persistence, snapshots, and access by
other processes. Store vaults and backups on appropriately encrypted media.

### Unlocked session

PassMan is an offline-first local application, not a secure enclave. While
unlocked, Python and Qt objects contain plaintext. Search can match secret
values, and views may display them. Clipboard copy exports plaintext to the
desktop. Its default clear timer is 30 seconds and can be disabled; clearing
does not erase clipboard history or a prior read by another process. The
default auto-lock interval is 300 seconds and can be disabled. Locking drops
model and password references; it does not promise memory zeroization,
resistance to screen capture, or protection from malware running as the user.

Source builds can expose decrypted Developer JSON when debug tools are enabled.
Frozen builds do not expose that panel. Do not use debug tools with a real
vault while screen sharing or collecting diagnostics.

### Import and export

Apple Passwords CSV files are plaintext. Import previews changes and, after
confirmation, manages records bearing the Apple import marker. A later CSV
can update or delete previously imported records that are absent. A
well-formed but incomplete export can therefore cause a legitimate deletion
preview. Inspect it and retain a verified encrypted backup before bulk
imports. OTPAuth URI values contain authenticator secrets and need the same
care as passwords. Passkeys are not imported as usable credentials from CSV.

YellowSphere ARC V3 exports produced by PassMan encrypt the mnemonic under
the selected password. ARC import also accepts supported keyfile modes and an
unprotected plain seed format. A raw project `.key` export writes the stored
bytes to a separate file; filesystem permissions do not encrypt those bytes.
Treat each selected import or export path as a boundary crossing.

### Package provenance

The release workflow signs final packages, SBOMs, and checksum manifests with
detached OpenPGP signatures. Verify the signature of the file you will run,
then compare its checksum with a **signed** manifest. The current primary
release key fingerprint is:

```text
7858 E51C 98AD 2541 5098 9EF3 1F4D F0EB 1C80 C710
```

Compare this fingerprint through a channel already trusted. Importing a key
from the same untrusted location as a package, without an independent
fingerprint check, does not establish origin. The core commands are:

```bash
gpg --show-keys docs/PassMan_Release_Signing_2026_pubkey.asc
gpg --import docs/PassMan_Release_Signing_2026_pubkey.asc
gpg --verify path/to/package.asc path/to/package
gpg --verify path/to/SHA256SUMS.asc path/to/SHA256SUMS
```

Run the checksum command from the directory named by the platform guide;
manifest paths are relative. See `docs/Build.txt` and the applicable release
guide for exact filenames. A SHA-256 match alone does not authenticate a
manifest supplied by an attacker.

The documented macOS builds use ad hoc code signing and are not Apple
Developer ID notarized. The Windows guide describes a local self-signed
Authenticode certificate, which does not establish a publicly trusted
publisher. Linux `.deb` files are not in a signed APT repository. OpenPGP
verification is the common release integrity check across these formats;
it does not make a compromised build trustworthy.

## Operational response

| Event | Immediate action | Follow through |
| --- | --- | --- |
| Vault file copied, password believed secret | Preserve evidence and identify copied generations. | Assess master password strength and exposure; rotate high value account credentials if risk warrants. Replace compromised backups deliberately. |
| Master password exposed | Lock the vault and stop using the affected host until it is trusted. | Rotate stored account credentials, recovery methods, TOTP seeds, and wallet material according to impact. Re-encrypting the current vault alone does not revoke old backups. |
| Plain CSV, seed, or private key export exposed | Remove accessible copies and stop further distribution. | Rotate affected account or key material; inspect sync, backup, snapshots, and clipboard history. Deleting one visible file is not evidence of erasure. |
| Suspicious package or signature failure | Do not execute it. Preserve the exact bytes and verification output. | Check the independently established key fingerprint, report privately, and use a verified build. |
| Release signing private key exposed | Stop signing with that key. | Generate a new key, announce rotation through a trusted channel, re-sign current artifacts, and retire the compromised trust anchor. |

Do not copy decrypted data into an issue or support message. Share sanitized
hashes, metadata, and synthetic reproduction material unless a confidential
forensic arrangement has been made.

## Change control

Changes to `src/crypto/`, `src/models/vault_model.py`, file paths, backup and
restore, CSV/ARC/key parsing, clipboard handling, build scripts, or signing
procedures require review against `THREAT_MODEL.md`, `docs/Encryption.txt`,
and `docs/OpSec.txt`. Preserve compatibility unless a versioned migration is
explicitly designed. Use synthetic fixtures and focused negative cases; verify
the final packaged bytes and signatures after every rebuild. Keep private
signing material, real vaults, local keyrings, and virtual environments out
of version control and release archives.
