# PassMan Threat Model

## Scope and method

This model describes the Python/PyQt6 application at version 1.0.8. It is an
implementation analysis, not a certification or a claim of formal verification.
The controlling code is in `src/`; `docs/Encryption.txt` specifies the vault
format, and `docs/OpSec.txt` specifies operator practice. When prose and code
disagree, inspect the code and treat the discrepancy as a defect to resolve.

The principal security objective is **confidentiality and integrity of vault
contents while the vault is locked and its file is stolen or modified**. The
secondary objectives are recoverability after interrupted writes, predictable
ownership of imported records, and authentication of distributed packages.
An unlocked desktop process, its UI, the operating system clipboard, and any
plaintext import or export file are separate security domains. Vault encryption
does not extend to them.

### Assets and sensitivity

| Asset | Where it exists | Impact of disclosure or modification |
| --- | --- | --- |
| Master password | UI input and Python process memory while unlocked | Decrypts every available vault generation using that password. |
| Vault encryption key and plaintext model | Process memory during derivation, unlock, editing, and save | Exposes or alters all records, including stored private keys and seeds. |
| `vault.dat`, `vault.dat.bak`, manual backups | User selected vault directory and backup destinations | Enables offline password guessing, rollback, deletion, and availability attacks. |
| Account credentials and notes | Encrypted vault; plaintext in an unlocked process, UI, and optionally clipboard | Account takeover or recovery bypass. |
| TOTP/HOTP secrets, recovery codes, seed phrases | Encrypted vault; plaintext in the unlocked process | Second factor impersonation, recovery, or wallet loss. A displayed one time code is also sensitive. |
| Project `.key` bytes | Base64 inside encrypted vault; plaintext when viewed or exported | OpenPGP private key compromise if the imported file contains private material. Base64 is an encoding, not protection. |
| Apple Passwords CSV and selected ARC/keyfiles | External files controlled by the user | Plain CSV exposes passwords and OTP URI secrets. ARC protection depends on its mode and credentials; a plain ARC import is accepted. |
| Clipboard and visible UI | Desktop session outside the vault file boundary | Immediate observation or retention by another process, history service, screen capture, or person. |
| Release private key, public key, manifests, packages | Signing environment and distribution channel | A stolen signing key permits convincing malicious releases; a substituted public key defeats naive verification. |

### Adversary capabilities

**A1: offline file access.** The attacker can copy encrypted vaults, backups,
filesystem snapshots, or package files, and can spend arbitrary time guessing
master passwords. The attacker cannot observe a live unlock or control the
trusted host.

**A2: writable storage.** The attacker can replace, delete, truncate, or replay
vault files and import files. They do not know the master password or release
signing key. This capability includes a malicious removable drive or a
misconfigured sync client.

**A3: local desktop observation.** The attacker can read clipboard contents,
record a screen, observe accessibility state, or inspect temporary files while
the vault is unlocked. This model does not claim to withstand A3.

**A4: process or build compromise.** The attacker can execute code as the user,
modify dependencies or build inputs, replace the application, or obtain the
release private key. A4 crosses the application's trust boundary and defeats
its at rest guarantee. The response is host cleanup, account rotation, and,
where appropriate, signing key rotation.

These capabilities are independent. In particular, resistance to A1 does not
imply resistance to A3 or A4.

## Trust boundaries and data flows

1. **Disk to parser.** `Vault.unlock()` reads an entire UTF-8 JSON document from
   `load_path`; the outer JSON, Base64 fields, KDF header, and decrypted model
   are untrusted until validation completes. The file is not streamed and no
   global vault size limit is imposed before reading it.
2. **Password to key.** The master password is encoded as UTF-8 without Unicode
   normalization. Argon2id derives a 32 byte key from a 16 byte salt. New writes
   use time cost 3, memory cost 65,536 KiB, and parallelism 4. On read, time is
   clamped to 1–10, memory to 8,192–262,144 KiB, and parallelism to 1–8; the
   algorithm and output length are forced to Argon2id and 32 bytes. Clamping
   limits a crafted header's requested cost but is not a file size or CPU time
   quota.
3. **Ciphertext to process.** Version 2 uses AES-256-GCM with a fresh 12 byte
   `os.urandom()` nonce and the canonical JSON serialization of the complete
   parsed header as additional authenticated data. `AESGCM.encrypt()` returns
   `ciphertext || 16-byte tag`. A failed tag rejects the unlock; an incorrect
   password and corruption share the same user facing error. Version 1 is read
   without header additional data, then normally migrates to version 2 after
   successful unlock.
4. **Process to disk.** `Vault.save()` serializes the complete model to UTF-8
   JSON, encrypts it with a new salt and nonce, copies the previous active file
   to `vault.dat.bak` when one exists, writes through a temporary file in the
   destination directory, flushes and `fsync`s it, and uses `os.replace()`.
   Directory `fsync` and `chmod` are attempted, but their failures are ignored
   by the relevant helpers. Filesystem encryption, ACLs, snapshots, and sync
   retention remain host responsibilities. The selected vault directory is
   remembered in a Qt application setting outside the encrypted file; that
   location is metadata even while the vault is locked.
5. **Process to desktop.** Entry cards, notes, authenticators, seed views,
   project key views, and debug tools can present decrypted material. Copy
   writes plaintext to `QApplication.clipboard()`; the default clear interval
   is 30 seconds, configurable from 0 to 600 seconds. Clearing occurs only if
   the clipboard still equals the value PassMan copied. Other clipboard
   consumers can retain it. Auto-lock defaults to 300 seconds, configurable
   from 0 to 3,600 seconds; lock drops model and password references but does
   not zero Python, Qt, allocator, GPU, swap, or clipboard history memory.
6. **External file to vault.** Apple Passwords CSV is read as UTF-8 with an
   optional BOM and parsed before the confirmation prompt. The importer checks
   row shape and recognized columns, parses OTPAuth URIs, computes a preview on
   copies, and reconciles only records with `import_source="apple_passwords"`.
   A confirmed import can add, update, and delete previously imported records
   missing from the next CSV. Manually created records lack that marker and are
   outside this reconciliation. The marker is an ownership convention inside
   authenticated vault plaintext, not a separate authorization mechanism.
7. **External seed/key material.** ARC import accepts an unprotected plain seed
   format and protected ARC V3 variants. ARC V3 password export normalizes the
   password with NFKD, hashes it with SHA-512, derives an AES key using
   PBKDF2-HMAC-SHA-512 with 1,000,000 iterations and a 32 byte random salt,
   pads the payload to 512 bytes, and authenticates bundle metadata with
   AES-GCM. ARC import and keyfile reads cap individual files at 1 MiB. Project
   `.key` export writes original private bytes to a separate file; restrictive
   permissions are attempted by `write_private_file()`, but the destination
   remains plaintext key material.
8. **Build to user.** Packages, SBOMs, platform manifests, and the aggregate
   `docs/SHA256SUMS` have detached OpenPGP signatures. The signing key is
   separate from the application vault; its private component must never enter
   packages or source history. A checksum establishes equality to a manifest.
   Authenticity requires a valid signature and a public key fingerprint
   established independently of the untrusted download channel.

### Vault bytes and authentication boundary

The on disk object has exactly the conceptual shape below; JSON formatting is
not part of the authenticated header representation:

```text
outer = {"header": {...}, "payload": base64(ciphertext || tag)}
header = {version: 2, algorithm: "AES-256-GCM", salt: base64(16 bytes),
          nonce: base64(12 bytes), kdf: {type, time_cost, memory_cost,
                                      parallelism, hash_len}}
key = Argon2id(UTF8(master_password), salt, effective_kdf_parameters, 32 bytes)
aad = UTF8(json.dumps(parsed_header, sort_keys=True,
                      separators=(",", ":")))
plaintext = UTF8(json.dumps(model.to_json_dict(), indent=2, sort_keys=True))
payload = base64(AESGCM(key).encrypt(nonce, plaintext, aad))
```

The payload length exposes the approximate plaintext length: there is no
vault padding, compression, or length hiding. JSON whitespace and object key
order outside the parsed header can change without changing the authenticated
header value. Version 2 authenticates parsed header values and plaintext; it
does **not** establish freshness. Replacing a valid vault with an older valid
vault encrypted under the same password is a rollback, not a tag forgery.
Deleting the active file or substituting an unrelated valid file is also an
availability or selection problem, not something AEAD can prevent.

`VaultModel.from_json_dict()` rejects non-list collections and non-object
records. Older files may omit newer collections, which then default to empty.
The unlocked model includes account entries, project keys, authenticators,
recovery records, seed records, and settings. All are protected by the same
vault key and have the same locked versus unlocked boundary.

## Threat analysis

The table distinguishes a mitigation from the residual condition it leaves.
It does not assign numerical likelihood to environments the project cannot
observe.

| ID | Attack path and prerequisite | Implemented control | Residual condition / operator action |
| --- | --- | --- | --- |
| T01 | A1 copies any generation of `vault.dat` or backup and guesses passwords offline. | Argon2id per file salt and AES-GCM tag provide a password check and protect contents when the password is strong. | A weak or reused password remains guessable; backup proliferation gives more targets. Use a high entropy unique master password. |
| T02 | A2 edits ciphertext, tag, parsed v2 header, or model bytes. | GCM authentication rejects modified encrypted data and v2 header values before the model is accepted. | Error messages cannot distinguish a wrong password from ciphertext corruption. Retain independently stored backups. |
| T03 | A2 replays an older valid encrypted file or backup. | No application level monotonic counter, trusted clock, or remote witness exists. | Rollback can restore deleted secrets or stale passwords. Compare backup provenance and account state after restore. |
| T04 | A2 deletes, truncates, or fills storage during a save. | Temporary same-directory writes, `fsync`, replacement, and an automatic prior-file backup reduce partial-write loss. | No multi-file transaction covers active and backup together; power loss, filesystem behavior, or external writers can still cause loss. Keep an independent verified backup. |
| T05 | A2 supplies an oversized or hostile vault/CSV file. | Vault shape and Base64 checks, KDF cost bounds, CSV row checks, and ARC's 1 MiB limit constrain several paths. | Vault and CSV reads have no global size ceiling; parsing, allocation, and KDF work can cause denial of service. Import only files from known sources. |
| T06 | A3 observes the master password, unlocked process, screen, clipboard, or copied code. | Password input masking, optional field masking, clipboard timer, and auto-lock reduce casual exposure time. | No process isolation or memory zeroization exists. A local observer or malware can capture secrets before clearing or lock. |
| T07 | An Apple CSV is stored in downloads, cloud sync, snapshots, or support material. | Import is local and writes selected values into the encrypted vault. | The CSV itself is plaintext and may include OTPAuth secrets. Delete it and consider retained copies and snapshots. |
| T08 | A user confirms a later Apple CSV lacking previously imported rows. | The confirmation previews add/update/delete counts; reconciliation is restricted to Apple-marked password and authenticator records. | An incomplete but well-formed export can cause intentional deletion of managed records. Review counts and keep a backup before bulk imports. |
| T09 | A hostile OTPAuth URI, `.arc`, or `.key` file is selected. | Parsers validate recognized formats; malformed OTPAuth aborts the Apple import; ARC enforces size and cryptographic checks for protected bundles. | Parser and optional local GPG tooling remain part of the trusted code base. Plain ARC import is intentionally unencrypted. File origin remains material. |
| T10 | A private `.key` or seed is exported to an unsafe destination. | Key export attempts private file permissions; ARC V3 export encrypts its mnemonic payload. | Key export is raw material. ARC protection depends on its selected credential mode and secret strength. Backups, indexing, and cloud sync may retain output. |
| T11 | A package, checksum manifest, or signing public key is substituted. | Detached signatures and SHA-256 manifests permit verification of exact package bytes. | A key obtained from the same compromised channel is not an independent trust anchor. Compare the primary fingerprint `7858 E51C 98AD 2541 5098 9EF3 1F4D F0EB 1C80 C710` through a trusted channel. |
| T12 | A build host, dependency, PyInstaller input, or release private key is compromised. | Pinned dependencies, CI, CodeQL, SBOMs, packaging checks, and release signatures support review and traceability. | Signing a malicious build makes its signature valid. A self-signed Windows certificate and ad hoc macOS signature do not confer public publisher trust. Rebuild from reviewed source and rotate compromised keys. |
| T13 | Another user or process reads a vault directory or moved backup. | PassMan attempts restrictive POSIX permissions on vault files and directory, and verifies copies during a vault move. | Permission attempts may fail without aborting; Windows and external filesystem ACLs vary. Disk encryption and host access control remain required. |
| T14 | Master password is changed while older backups remain. | The current model is re-encrypted under the new password. | Old backups remain encrypted under their old passwords and are still offline guessing targets. Inventory and retire them deliberately. |
| T15 | Another process reads local application settings while the vault is locked. | Vault contents remain encrypted; the setting stores the chosen directory rather than the master password. | A path can disclose usernames, storage volume names, or organizational context. Protect local profile metadata as well as vault files. |

## Implementation evidence map

| Boundary | Primary implementation | Focused verification |
| --- | --- | --- |
| Vault envelope, migration, save, restore, move | [`src/crypto/vault.py`](src/crypto/vault.py), [`src/crypto/encryption.py`](src/crypto/encryption.py), [`src/crypto/key_derivation.py`](src/crypto/key_derivation.py) | [`tests/test_vault_release.py`](tests/test_vault_release.py), [`tests/test_secure_files.py`](tests/test_secure_files.py) |
| Decrypted record schema and settings | [`src/models/vault_model.py`](src/models/vault_model.py) | [`tests/test_vault_model.py`](tests/test_vault_model.py) |
| Apple CSV parse and managed record reconciliation | [`src/utils/apple_passwords_import.py`](src/utils/apple_passwords_import.py), [`src/gui/main_window.py`](src/gui/main_window.py) | [`tests/test_apple_passwords_import.py`](tests/test_apple_passwords_import.py) |
| Clipboard and desktop state | [`src/utils/clipboard.py`](src/utils/clipboard.py), [`src/gui/main_window.py`](src/gui/main_window.py) | [`tests/test_settings_accessibility.py`](tests/test_settings_accessibility.py) |
| Seed bundle format and export | [`src/crypto/yellowsphere_arc.py`](src/crypto/yellowsphere_arc.py) | [`tests/test_yellowsphere_arc.py`](tests/test_yellowsphere_arc.py) |
| Release package provenance | [`build.py`](build.py), [`docs/Build.txt`](docs/Build.txt), [`docs/ReleaseProcess.md`](docs/ReleaseProcess.md) | Platform release guides and final artifact signatures |

## Security invariants to preserve in code review

1. Every v2 save derives a 32 byte key from a fresh 16 byte salt and uses a
   fresh 12 byte nonce. The parsed complete v2 header is passed as GCM AAD on
   both encryption and decryption. Any migration of that representation must
   be versioned and tested with existing files.
2. Unlock does not publish a model to UI code before the ciphertext tag and
   record structure have been accepted. A failed unlock must not leave the
   attempted plaintext model active.
3. A backup candidate is authenticated with the current password before a
   user initiated restore replaces the active file. A vault move verifies the
   copied active file and backup before changing the remembered location.
4. Apple import must parse the complete selected CSV before mutation, show
   predicted deletions, and restrict automatic deletion to records carrying
   the Apple import marker. A partially exported CSV is still a valid input
   that requires explicit user scrutiny.
5. Secret exports and clipboard actions must be treated as boundary crossings,
   not as ordinary view operations. Never print plaintext vault JSON or secret
   fixtures into logs, test output, CI artifacts, issue reports, or releases.
6. Release signatures must cover the final package bytes after code signing
   and packaging. Updating a package or manifest invalidates its detached
   signature and requires regeneration and verification.

The current automated tests exercise vault compatibility, tampering,
persistence, import reconciliation, file permissions, and ARC parsing. They
do not establish resistance to a compromised operating system, exhaustive
parser safety, reproducible builds, or absence of side channels.

## Review triggers

Revisit this model whenever code changes vault schema, cryptography, KDF
parameters, file placement, backup ordering, Apple reconciliation, OTP or ARC
parsing, key export, clipboard behavior, auto-lock, build inputs, signing,
or release distribution. For each change, identify the exact data crossing a
trust boundary, the validation performed before state mutation, and the
failure state after any interrupted write or rejected input.
