from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: E402

from crypto import vault as vault_module  # noqa: E402
from crypto.encryption import ALGORITHM, new_nonce  # noqa: E402
from crypto.key_derivation import derive_key  # noqa: E402
from crypto.vault import InvalidPasswordError, Vault, VAULT_VERSION  # noqa: E402


PASSWORD = "test master password"
TEST_KDF = {
    "type": "argon2id",
    "time_cost": 1,
    "memory_cost": 8192,
    "parallelism": 1,
    "hash_len": 32,
}


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def write_legacy_vault(path: Path) -> None:
    salt, nonce = os.urandom(16), new_nonce()
    key = derive_key(PASSWORD, salt, TEST_KDF)
    plaintext = json.dumps({"entries": [], "settings": {}}).encode("utf-8")
    header = {
        "version": 1,
        "algorithm": ALGORITHM,
        "salt": b64(salt),
        "nonce": b64(nonce),
        "kdf": TEST_KDF,
    }
    document = {"header": header, "payload": b64(AESGCM(key).encrypt(nonce, plaintext, None))}
    path.write_text(json.dumps(document), encoding="utf-8")


class VaultReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.kdf_patch = patch.dict(vault_module.DEFAULT_KDF_PARAMS, TEST_KDF)
        self.kdf_patch.start()
        self.addCleanup(self.kdf_patch.stop)

    def test_new_vault_uses_v2_header_aad_and_rejects_tampering(self) -> None:
        path = self.folder / "vault.dat"
        vault = Vault(path)
        vault.create(PASSWORD)
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["header"]["version"], VAULT_VERSION)
        Vault(path).unlock(PASSWORD)
        with self.assertRaises(InvalidPasswordError):
            Vault(path).unlock("wrong password")

        document["header"]["added_metadata"] = "tampered"
        path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(InvalidPasswordError):
            Vault(path).unlock(PASSWORD)

    def test_legacy_v1_unlock_migrates_to_v2_and_keeps_v1_backup(self) -> None:
        path = self.folder / "vault.dat"
        write_legacy_vault(path)
        Vault(path).unlock(PASSWORD)
        self.assertEqual(json.loads(path.read_text())["header"]["version"], 2)
        self.assertEqual(json.loads(path.with_name("vault.dat.bak").read_text())["header"]["version"], 1)
        Vault(path.with_name("vault.dat.bak")).unlock(PASSWORD, migrate=False)

    def test_failed_backup_stage_does_not_replace_active_vault(self) -> None:
        path = self.folder / "vault.dat"
        vault = Vault(path)
        vault.create(PASSWORD)
        original = path.read_bytes()
        with patch("crypto.vault._atomic_copy", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                vault.save()
        self.assertEqual(path.read_bytes(), original)
        Vault(path).unlock(PASSWORD)

    def test_copy_to_verifies_both_files_without_overwriting_existing_data(self) -> None:
        source = self.folder / "vault.dat"
        destination = self.folder / "new" / "vault.dat"
        destination.parent.mkdir()
        vault = Vault(source)
        vault.create(PASSWORD)
        vault.copy_to(destination)
        Vault(destination).unlock(PASSWORD)
        Vault(destination.with_name("vault.dat.bak")).unlock(PASSWORD)
        self.assertEqual(vault.path, source)
        destination.write_bytes(b"preserve this")
        with self.assertRaises(FileExistsError):
            vault.copy_to(destination)
        self.assertEqual(destination.read_bytes(), b"preserve this")


if __name__ == "__main__":
    unittest.main(verbosity=2)
