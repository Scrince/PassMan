from __future__ import annotations

import base64
import json
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .encryption import (
    ALGORITHM,
    DecryptionError,
    decrypt_json_bytes,
    encrypt_json_bytes,
    header_associated_data,
    new_nonce,
)
from .key_derivation import DEFAULT_KDF_PARAMS, derive_key, sanitize_kdf_params
from models.vault_model import VaultModel


VAULT_VERSION = 2
LEGACY_VAULT_VERSION = 1
VAULT_SALT_SIZE = 16


class VaultError(Exception):
    pass


class InvalidPasswordError(VaultError):
    pass


class VaultFormatError(VaultError):
    pass


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)


def _secure_chmod(path: Path, mode: int = 0o600) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile("wb", dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
        _secure_chmod(temporary_path)
        os.replace(temporary_path, path)
        _secure_chmod(path)
        _fsync_directory(path.parent)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with source.open("rb") as source_file, NamedTemporaryFile(
            "wb", dir=destination.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            shutil.copyfileobj(source_file, temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        _secure_chmod(temporary_path)
        os.replace(temporary_path, destination)
        _secure_chmod(destination)
        _fsync_directory(destination.parent)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


class Vault:
    def __init__(self, path: Path, load_path: Path | None = None) -> None:
        self.path = path
        self.load_path = load_path or path
        self.model = VaultModel()
        self._password: str | None = None

    @property
    def is_unlocked(self) -> bool:
        return self._password is not None

    def exists(self) -> bool:
        return self.path.exists() or self.load_path.exists() or self.backup_path.exists()

    @property
    def backup_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.bak")

    def backup_exists(self) -> bool:
        return self.backup_path.exists()

    def restore_backup(self) -> None:
        if not self.backup_path.exists():
            raise VaultFormatError("Backup vault file does not exist.")
        if self.path.exists():
            corrupt_path = self.path.with_name(f"{self.path.name}.corrupt")
            _atomic_copy(self.path, corrupt_path)
        _atomic_copy(self.backup_path, self.path)

    def restore_from_file(self, backup_path: Path) -> None:
        if self._password is None:
            raise VaultError("Vault is locked.")
        if not backup_path.exists():
            raise VaultFormatError("Backup vault file does not exist.")
        if backup_path.resolve() == self.path.resolve():
            raise VaultError("Cannot restore the active vault file over itself.")
        restoring_internal_backup = backup_path.resolve() == self.backup_path.resolve()
        backup_vault = Vault(backup_path)
        backup_vault.unlock(self._password, migrate=False)
        if self.path.exists() and not restoring_internal_backup:
            _atomic_copy(self.path, self.backup_path)
        _atomic_copy(backup_path, self.path)
        self.unlock(self._password)

    def copy_to(self, destination: Path) -> None:
        """Copy and verify the unlocked vault and its backup at a new path.

        The current files remain untouched. The caller can update the saved
        location and remove the originals only after this operation succeeds.
        """
        if self._password is None:
            raise VaultError("Vault must be unlocked before it can be moved.")
        destination = Path(destination)
        destination_backup = destination.with_name(f"{destination.name}.bak")
        if not destination.parent.is_dir():
            raise VaultError("The destination folder does not exist.")
        if destination.resolve() == self.path.resolve():
            raise VaultError("The destination is already the active vault location.")
        if destination.exists() or destination_backup.exists():
            raise FileExistsError("The destination already contains a vault or backup.")

        source_check = Vault(self.path)
        source_check.unlock(self._password, migrate=False)
        if source_check.model.to_json_dict() != self.model.to_json_dict():
            raise VaultError("The active vault changed on disk. Save or reload it before moving.")

        backup_source = self.path
        if self.backup_path.exists():
            try:
                Vault(self.backup_path).unlock(self._password, migrate=False)
                backup_source = self.backup_path
            except (VaultError, OSError):
                # Keep the destination recoverable even when the old backup is bad.
                backup_source = self.path

        created_main = False
        created_backup = False
        try:
            _atomic_copy(self.path, destination)
            created_main = True
            _atomic_copy(backup_source, destination_backup)
            created_backup = True
            copied = Vault(destination)
            copied.unlock(self._password, migrate=False)
            if copied.model.to_json_dict() != self.model.to_json_dict():
                raise VaultFormatError("The copied vault did not match the active vault.")
            Vault(destination_backup).unlock(self._password, migrate=False)
        except Exception:
            if created_main:
                destination.unlink(missing_ok=True)
            if created_backup:
                destination_backup.unlink(missing_ok=True)
            raise

    def create(self, password: str) -> None:
        if not password:
            raise VaultError("Password cannot be empty.")
        self.model = VaultModel()
        self._password = password
        self.save()

    def unlock(self, password: str, *, migrate: bool = True) -> None:
        if not self.load_path.exists():
            raise VaultFormatError("Vault file does not exist.")
        try:
            raw = json.loads(self.load_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise VaultFormatError("Vault file must contain a JSON object.")
            header = raw.get("header", {})
            payload = raw.get("payload")
            if not isinstance(header, dict) or not isinstance(payload, str):
                raise VaultFormatError("Vault file is missing header or payload.")
            version = header.get("version")
            if type(version) is not int or version not in {LEGACY_VAULT_VERSION, VAULT_VERSION}:
                raise VaultFormatError("Vault version is unsupported.")
            if header.get("algorithm") != ALGORITHM:
                raise VaultFormatError("Vault encryption algorithm is unsupported.")
            salt = _unb64(str(header["salt"]))
            if len(salt) != VAULT_SALT_SIZE:
                raise VaultFormatError("Vault file has an invalid salt.")
            nonce = _unb64(str(header["nonce"]))
            raw_kdf = header.get("kdf")
            kdf = sanitize_kdf_params(raw_kdf if isinstance(raw_kdf, dict) else None)
            ciphertext = _unb64(payload)
            key = derive_key(password, salt, kdf)
            associated_data = header_associated_data(header) if version == VAULT_VERSION else None
            plaintext = decrypt_json_bytes(ciphertext, key, nonce, associated_data)
            data = json.loads(plaintext.decode("utf-8"))
            if not isinstance(data, dict):
                raise VaultFormatError("Vault payload must contain a JSON object.")
            model = VaultModel.from_json_dict(data)
        except DecryptionError as exc:
            raise InvalidPasswordError("Incorrect password or corrupted vault.") from exc
        except VaultFormatError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise VaultFormatError("Vault file is malformed.") from exc
        previous_load_path = self.load_path
        self.model = model
        self._password = password
        if version == LEGACY_VAULT_VERSION and migrate:
            try:
                self._write_encrypted(
                    model,
                    password,
                    preserve_loaded_file=previous_load_path.resolve() != self.path.resolve(),
                )
            except Exception:
                self.model = VaultModel()
                self._password = None
                raise
        self.load_path = self.path

    def lock(self) -> None:
        self._password = None
        self.model = VaultModel()

    def save(self) -> None:
        if self._password is None:
            raise VaultError("Vault is locked.")
        self._write_encrypted(self.model, self._password)

    def change_password(self, old_password: str, new_password: str) -> None:
        """
        Re-key the vault using the current in-memory model.

        Does not call unlock() (which would reload from disk and discard unsaved edits).
        """
        if self._password is None:
            raise VaultError("Vault is locked.")
        if not old_password or old_password != self._password:
            raise InvalidPasswordError("Incorrect password or corrupted vault.")
        if not new_password:
            raise VaultError("Password cannot be empty.")
        # Keep live model; only re-encrypt with the new master password.
        self._write_encrypted(self.model, new_password)
        self._password = new_password

    def _write_encrypted(
        self,
        model: VaultModel,
        password: str,
        *,
        preserve_loaded_file: bool = False,
    ) -> None:
        salt = os.urandom(16)
        nonce = new_nonce()
        kdf = sanitize_kdf_params(DEFAULT_KDF_PARAMS)
        key = derive_key(password, salt, kdf)
        plaintext = json.dumps(model.to_json_dict(), indent=2, sort_keys=True).encode("utf-8")
        document: dict[str, Any] = {
            "header": {
                "version": VAULT_VERSION,
                "algorithm": ALGORITHM,
                "salt": _b64(salt),
                "nonce": _b64(nonce),
                "kdf": kdf,
            },
        }
        ciphertext = encrypt_json_bytes(
            plaintext,
            key,
            nonce,
            header_associated_data(document["header"]),
        )
        document["payload"] = _b64(ciphertext)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _secure_chmod(self.path.parent, 0o700)
        serialized = json.dumps(document, indent=2, sort_keys=True)
        encoded = serialized.encode("utf-8")
        had_existing_vault = self.path.exists()
        if had_existing_vault and not preserve_loaded_file:
            _atomic_copy(self.path, self.backup_path)
        _atomic_write(self.path, encoded)
        if not had_existing_vault or preserve_loaded_file:
            _atomic_copy(self.path, self.backup_path)
