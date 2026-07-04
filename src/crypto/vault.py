from __future__ import annotations

import base64
import json
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .encryption import ALGORITHM, DecryptionError, decrypt_json_bytes, encrypt_json_bytes, new_nonce
from .key_derivation import DEFAULT_KDF_PARAMS, derive_key
from models.vault_model import VaultModel


VAULT_VERSION = 1


class VaultError(Exception):
    """Common parent for problems that come from vault handling."""


class InvalidPasswordError(VaultError):
    """The password did not unlock this vault."""


class VaultFormatError(VaultError):
    """The vault file is missing pieces or is not shaped like a PassMan vault."""


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)


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
        return self.path.exists() or self.load_path.exists()

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
            shutil.copy2(self.path, corrupt_path)
        shutil.copy2(self.backup_path, self.path)

    def restore_from_file(self, backup_path: Path) -> None:
        if self._password is None:
            raise VaultError("Vault is locked.")
        if not backup_path.exists():
            raise VaultFormatError("Backup vault file does not exist.")
        if backup_path.resolve() == self.path.resolve():
            raise VaultError("Cannot restore the active vault file over itself.")
        restoring_internal_backup = backup_path.resolve() == self.backup_path.resolve()
        backup_vault = Vault(backup_path)
        backup_vault.unlock(self._password)
        if self.path.exists() and not restoring_internal_backup:
            shutil.copy2(self.path, self.backup_path)
        shutil.copy2(backup_path, self.path)
        self.unlock(self._password)

    def create(self, password: str) -> None:
        self.model = VaultModel()
        self._password = password
        self.save()

    def unlock(self, password: str) -> None:
        if not self.load_path.exists():
            raise VaultFormatError("Vault file does not exist.")
        try:
            raw = json.loads(self.load_path.read_text(encoding="utf-8"))
            header = raw.get("header", {})
            payload = raw.get("payload")
            if not isinstance(header, dict) or not isinstance(payload, str):
                raise VaultFormatError("Vault file is missing header or payload.")
            salt = _unb64(str(header["salt"]))
            nonce = _unb64(str(header["nonce"]))
            kdf = dict(header["kdf"])
            ciphertext = _unb64(payload)
            key = derive_key(password, salt, kdf)
            plaintext = decrypt_json_bytes(ciphertext, key, nonce)
            data = json.loads(plaintext.decode("utf-8"))
        except DecryptionError as exc:
            raise InvalidPasswordError("Incorrect password or corrupted vault.") from exc
        except VaultFormatError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise VaultFormatError("Vault file is malformed.") from exc
        self.model = VaultModel.from_json_dict(data)
        self._password = password
        self.load_path = self.path

    def lock(self) -> None:
        self._password = None
        self.model = VaultModel()

    def save(self) -> None:
        if self._password is None:
            raise VaultError("Vault is locked.")
        self._write_encrypted(self.model, self._password)

    def change_password(self, old_password: str, new_password: str) -> None:
        self.unlock(old_password)
        self._write_encrypted(self.model, new_password)
        self._password = new_password

    def _write_encrypted(self, model: VaultModel, password: str) -> None:
        salt = os.urandom(16)
        nonce = new_nonce()
        kdf = dict(DEFAULT_KDF_PARAMS)
        key = derive_key(password, salt, kdf)
        plaintext = json.dumps(model.to_json_dict(), indent=2, sort_keys=True).encode("utf-8")
        ciphertext = encrypt_json_bytes(plaintext, key, nonce)
        document: dict[str, Any] = {
            "header": {
                "version": VAULT_VERSION,
                "algorithm": ALGORITHM,
                "salt": _b64(salt),
                "nonce": _b64(nonce),
                "kdf": kdf,
            },
            "payload": _b64(ciphertext),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(document, indent=2, sort_keys=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as tmp:
            tmp.write(serialized)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_name = tmp.name
        temp_path = Path(temp_name)
        had_existing_vault = self.path.exists()
        try:
            if had_existing_vault:
                shutil.copy2(self.path, self.backup_path)
            temp_path.replace(self.path)
            if not had_existing_vault:
                shutil.copy2(self.path, self.backup_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
