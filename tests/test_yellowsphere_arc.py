from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
import unicodedata
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crypto.yellowsphere_arc import (  # noqa: E402
    ArcImportError,
    ArcExportError,
    export_arc_bytes,
    import_arc_bytes,
    import_arc_file,
)


MNEMONIC_12 = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
MNEMONIC_24 = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon art"
PASSWORD = "pässphrase"
KEY_BYTES = bytes((index * 17 + 11) & 0xFF for index in range(64))


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hkdf(data: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA512(), length=length, salt=salt, info=info).derive(data)


def password_key(password: str, salt: bytes, iterations: int = 1_000_000) -> bytes:
    normalized = unicodedata.normalize("NFKD", password).encode("utf-8")
    password_hash = hashes.Hash(hashes.SHA512())
    password_hash.update(normalized)
    return PBKDF2HMAC(
        algorithm=hashes.SHA512(), length=32, salt=salt, iterations=iterations
    ).derive(password_hash.finalize())


def make_arc(mode: str, *, password: str = PASSWORD, key_bytes: bytes = KEY_BYTES, mnemonic: str = MNEMONIC_12) -> bytes:
    salt = bytes(range(32))
    nonce = bytes(range(12))
    credential_mode = mode
    if mode == "password":
        key = password_key(password, salt)
        kdf = {"name": "PBKDF2", "hash": "SHA-512", "iterations": 1_000_000, "salt_b64": b64(salt)}
    else:
        keyfile_secret = "arc-keyfile-v1:" + b64(key_bytes)
        if mode == "keyfile":
            credential = keyfile_secret
        else:
            normalized_password = unicodedata.normalize("NFKD", password).encode("utf-8")
            combined = hkdf(
                key_bytes + normalized_password,
                salt,
                b"yellowsphere-arc-v3-combined-key",
                64,
            )
            credential = "arc-combined-v1:" + b64(combined)
        key = hkdf(
            credential.encode("utf-8"),
            salt,
            b"YellowSphere ARC v3 AES-256-GCM key",
            32,
        )
        kdf = {"name": "HKDF", "hash": "SHA-512", "salt_b64": b64(salt)}
    metadata = {
        "magic": "YELLOWSPHERE-ARC",
        "format": "yellowsphere-encrypted-seed-v3",
        "version": 3,
        "created_at": "2026-06-30T18:57:01.892Z",
        "credential_mode": credential_mode,
        "kdf": kdf,
        "cipher": {"name": "AES-256-GCM", "nonce_b64": b64(nonce)},
        "padding": {"name": "ZERO", "length": 512},
    }
    payload = json.dumps(
        {"mnemonic": mnemonic, "word_count": len(mnemonic.split()), "created_at": metadata["created_at"]},
        separators=(",", ":"),
    ).encode("utf-8")
    plaintext = payload.ljust(512, b"\0")
    ciphertext = AESGCM(key).encrypt(
        nonce,
        plaintext,
        json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
    )
    return json.dumps({**metadata, "ciphertext_b64": b64(ciphertext)}).encode("utf-8")


def make_encrypted_keyfile(password: str, key_bytes: bytes) -> bytes:
    salt = bytes(range(16))
    nonce = bytes(range(12))
    key = password_key(password, salt)
    metadata = {
        "magic": "YELLOWSPHERE-KEYFILE-ENC",
        "format": "yellowsphere-keyfile-enc-v1",
    }
    ciphertext = AESGCM(key).encrypt(nonce, key_bytes, json.dumps(metadata, separators=(",", ":")).encode())
    return json.dumps({
        **metadata,
        "version": 2,
        "kdf": {"algo": "PBKDF2-SHA512", "iterations": 1_000_000, "salt_b64": b64(salt), "prehash": "SHA-512"},
        "cipher": {"name": "AES-256-GCM", "nonce_b64": b64(nonce)},
        "ciphertext_b64": b64(ciphertext),
    }).encode("utf-8")


class YellowSphereArcImportTests(unittest.TestCase):
    def test_exports_password_protected_armored_v3_and_round_trips(self) -> None:
        exported = export_arc_bytes(MNEMONIC_12, PASSWORD)
        self.assertTrue(exported.startswith(b"YELLOWSPHERE-ARC-V2\n"))
        self.assertEqual(import_arc_bytes(exported, password=PASSWORD), MNEMONIC_12)
        with self.assertRaises(ArcImportError):
            import_arc_bytes(exported, password="wrong password")

    def test_export_rejects_invalid_phrase_length_and_empty_password(self) -> None:
        with self.assertRaises(ArcExportError):
            export_arc_bytes("abandon abandon", PASSWORD)
        with self.assertRaises(ArcExportError):
            export_arc_bytes(MNEMONIC_12, "")

    def test_imports_unprotected_armored_seed(self) -> None:
        bundle = {
            "magic": "YELLOWSPHERE-ARC",
            "format": "yellowsphere-plain-seed-v1",
            "version": 1,
            "mnemonic": MNEMONIC_12,
            "word_count": 12,
            "encrypted": False,
        }
        armored = b"YELLOWSPHERE-ARC-V2\n" + base64.b64encode(json.dumps(bundle).encode()) + b"\n"
        self.assertEqual(import_arc_bytes(armored), MNEMONIC_12)

    def test_imports_password_keyfile_and_combined_arc_v3(self) -> None:
        for mode in ("password", "keyfile", "both"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "YellowSphere_Keyfile.key"
                path.write_text(json.dumps({
                    "magic": "YELLOWSPHERE-KEYFILE",
                    "format": "yellowsphere-keyfile-v1",
                    "version": 1,
                    "key_b64": b64(KEY_BYTES),
                }), encoding="utf-8")
                phrase = MNEMONIC_24 if mode == "keyfile" else MNEMONIC_12
                result = import_arc_bytes(
                    make_arc(mode, mnemonic=phrase),
                    password=PASSWORD if mode in {"password", "both"} else None,
                    keyfile_path=path if mode in {"keyfile", "both"} else None,
                )
                self.assertEqual(result, phrase)

    def test_imports_arc_with_encrypted_keyfile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            keyfile_path = Path(directory) / "YellowSphere_Keyfile.enc.key"
            keyfile_path.write_bytes(make_encrypted_keyfile(PASSWORD, KEY_BYTES))
            self.assertEqual(
                import_arc_bytes(make_arc("both"), password=PASSWORD, keyfile_path=keyfile_path),
                MNEMONIC_12,
            )

    def test_imports_file_and_rejects_bad_password_or_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seed.arc"
            bundle = make_arc("password")
            path.write_bytes(bundle)
            self.assertEqual(import_arc_file(path, password=PASSWORD), MNEMONIC_12)
            with self.assertRaises(ArcImportError):
                import_arc_file(path, password="wrong password")

            changed = json.loads(bundle)
            changed["created_at"] = "2000-01-01T00:00:00.000Z"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(ArcImportError):
                import_arc_file(path, password=PASSWORD)

    def test_rejects_unsupported_arc_version_and_invalid_word_count(self) -> None:
        with self.assertRaises(ArcImportError):
            import_arc_bytes(b'{"magic":"YELLOWSPHERE-ARC","format":"yellowsphere-encrypted-seed-v2"}')
        plain = {
            "magic": "YELLOWSPHERE-ARC",
            "format": "yellowsphere-plain-seed-v1",
            "version": 1,
            "mnemonic": "not a complete phrase",
            "word_count": 5,
            "encrypted": False,
        }
        with self.assertRaises(ArcImportError):
            import_arc_bytes(json.dumps(plain).encode())


if __name__ == "__main__":
    unittest.main(verbosity=2)
