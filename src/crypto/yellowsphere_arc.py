from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import json
import os
import unicodedata
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


ARMOR_HEADER = "YELLOWSPHERE-ARC-V2"
ARC_MAGIC = "YELLOWSPHERE-ARC"
MAX_ARC_BYTES = 1_048_576


class ArcImportError(ValueError):
    """An unsupported, malformed, or undecryptable YellowSphere ARC file."""


class ArcExportError(ValueError):
    """A seed phrase or password cannot be written as a YellowSphere ARC file."""


def export_arc_bytes(mnemonic: str, password: str) -> bytes:
    """Serialize a mnemonic as a password-protected YellowSphere ARC V3 file."""
    words = [word.lower() for word in str(mnemonic or "").split() if word]
    if len(words) not in (12, 24):
        raise ArcExportError("Only 12-word and 24-word seed phrases can be exported.")
    if not password:
        raise ArcExportError("Choose a non-empty password for the .arc file.")

    created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    salt = os.urandom(32)
    nonce = os.urandom(12)
    kdf = {
        "name": "PBKDF2",
        "hash": "SHA-512",
        "iterations": 1_000_000,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
    }
    bundle: dict[str, Any] = {
        "magic": ARC_MAGIC,
        "format": "yellowsphere-encrypted-seed-v3",
        "version": 3,
        "created_at": created_at,
        "credential_mode": "password",
        "kdf": kdf,
        "cipher": {
            "name": "AES-256-GCM",
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        },
        "padding": {"name": "ZERO", "length": 512},
    }

    password_bytes = unicodedata.normalize("NFKD", password).encode("utf-8")
    # ARC's one-pass prehash is a format step; PBKDF2 below is the password KDF.
    password_hash = hashes.Hash(hashes.SHA512())
    password_hash.update(password_bytes)
    key = PBKDF2HMAC(
        algorithm=hashes.SHA512(),
        length=32,
        salt=salt,
        iterations=1_000_000,
    ).derive(password_hash.finalize())
    payload = json.dumps(
        {"mnemonic": " ".join(words), "word_count": len(words), "created_at": created_at},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) > 512:
        raise ArcExportError("The seed phrase is too large for the YellowSphere ARC format.")
    plaintext = payload.ljust(512, b"\0")
    aad = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    bundle["ciphertext_b64"] = base64.b64encode(ciphertext).decode("ascii")
    serialized = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"{ARMOR_HEADER}\n".encode("ascii") + base64.b64encode(serialized) + b"\n"


def export_arc_file(path: Path, mnemonic: str, password: str) -> None:
    """Write a password-protected YellowSphere ARC V3 file to path."""
    try:
        path.write_bytes(export_arc_bytes(mnemonic, password))
    except OSError as exc:
        raise ArcExportError(f"Could not write the selected .arc file: {exc}") from exc


def _decode_b64(value: Any, label: str, *, exact_length: int | None = None) -> bytes:
    if not isinstance(value, str):
        raise ArcImportError(f"The ARC file has an invalid {label}.")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError, binascii.Error) as exc:
        raise ArcImportError(f"The ARC file has an invalid {label}.") from exc
    if exact_length is not None and len(decoded) != exact_length:
        raise ArcImportError(f"The ARC file has an invalid {label}.")
    return decoded


def _parse_bundle(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ArcImportError("The selected file is not a valid YellowSphere ARC file.") from exc
    stripped = text.strip()
    if stripped.startswith(ARMOR_HEADER):
        encoded = "".join(stripped.splitlines()[1:])
        decoded = _decode_b64(encoded, "armored data")
        try:
            bundle = json.loads(decoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArcImportError("The YellowSphere ARC armor is malformed.") from exc
    else:
        try:
            bundle = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ArcImportError("The selected file is not a supported YellowSphere ARC file.") from exc
    if not isinstance(bundle, dict) or bundle.get("magic") != ARC_MAGIC:
        raise ArcImportError("The selected file is not a supported YellowSphere ARC file.")
    return bundle


def arc_credential_mode(data: bytes) -> str | None:
    """Return None for a plain ARC or its protected credential mode."""
    bundle = _parse_bundle(data)
    if bundle.get("format") == "yellowsphere-plain-seed-v1" and bundle.get("encrypted") is False:
        return None
    if bundle.get("format") != "yellowsphere-encrypted-seed-v3" or bundle.get("version") != 3:
        raise ArcImportError("This .arc version is not supported. Import a YellowSphere ARC V3 backup.")
    mode = bundle.get("credential_mode")
    if mode not in {"password", "keyfile", "both"}:
        raise ArcImportError("The YellowSphere ARC file has an invalid credential mode.")
    return mode


def _read_keyfile(path: Path, password: str | None = None) -> bytes:
    try:
        if path.stat().st_size > MAX_ARC_BYTES:
            raise ArcImportError("The selected keyfile is too large.")
        data = path.read_bytes()
    except ArcImportError:
        raise
    except OSError as exc:
        raise ArcImportError(f"Could not read keyfile: {exc}") from exc
    try:
        text = data.decode("utf-8-sig").strip()
    except UnicodeDecodeError as exc:
        raise ArcImportError("The selected keyfile is not valid text.") from exc
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        obj = None
    if isinstance(obj, dict):
        if obj.get("magic") == "YELLOWSPHERE-KEYFILE-ENC" and obj.get("format") == "yellowsphere-keyfile-enc-v1":
            if obj.get("version") != 2:
                raise ArcImportError("This encrypted YellowSphere keyfile version is not supported.")
            if not password:
                raise ArcImportError("The encrypted keyfile requires the ARC password.")
            kdf = obj.get("kdf")
            cipher = obj.get("cipher")
            if not isinstance(kdf, dict) or not isinstance(cipher, dict):
                raise ArcImportError("The encrypted YellowSphere keyfile is malformed.")
            iterations = kdf.get("iterations")
            if (
                kdf.get("algo") != "PBKDF2-SHA512"
                or kdf.get("prehash") != "SHA-512"
                or iterations not in {200_000, 1_000_000}
                or cipher.get("name") != "AES-256-GCM"
            ):
                raise ArcImportError("The encrypted YellowSphere keyfile uses an unsupported format.")
            salt = _decode_b64(kdf.get("salt_b64"), "keyfile salt", exact_length=16)
            nonce = _decode_b64(cipher.get("nonce_b64"), "keyfile nonce", exact_length=12)
            ciphertext = _decode_b64(obj.get("ciphertext_b64"), "keyfile ciphertext")
            password_bytes = unicodedata.normalize("NFKD", password).encode("utf-8")
            # Preserve the ARC keyfile format's prehash; PBKDF2 below does the stretching.
            password_hash = hashes.Hash(hashes.SHA512())
            password_hash.update(password_bytes)
            key = PBKDF2HMAC(
                algorithm=hashes.SHA512(), length=32, salt=salt, iterations=iterations
            ).derive(password_hash.finalize())
            aad = json.dumps(
                {"magic": obj["magic"], "format": obj["format"]}, separators=(",", ":")
            ).encode("utf-8")
            try:
                key = AESGCM(key).decrypt(nonce, ciphertext, aad)
            except Exception as exc:
                raise ArcImportError("Unable to decrypt the YellowSphere keyfile. Check the password.") from exc
            if len(key) < 32:
                raise ArcImportError("The YellowSphere keyfile contains too little key material.")
            return key
        key_value = obj.get("key_b64")
        if obj.get("magic") == "KEYFILE" and isinstance(obj.get("key"), str):
            key_value = obj["key"]
        if obj.get("magic") == "YELLOWSPHERE-KEYFILE" and obj.get("format") == "yellowsphere-keyfile-v1":
            pass
        elif obj.get("magic") != "KEYFILE" or not isinstance(obj.get("key"), str):
            if obj.get("magic") != "YELLOWSPHERE-KEYFILE" or obj.get("format") != "yellowsphere-keyfile-v1":
                raise ArcImportError("The selected file is not a supported raw YellowSphere keyfile.")
        if not isinstance(key_value, str):
            raise ArcImportError("The YellowSphere keyfile does not contain key material.")
        key = _decode_b64(key_value, "keyfile key")
    else:
        key = _decode_b64("".join(text.split()), "keyfile key")
    if len(key) < 32:
        raise ArcImportError("The keyfile must contain at least 256 bits of key material.")
    return key


def _credential(bundle: dict[str, Any], password: str | None, keyfile_path: Path | None, salt: bytes) -> tuple[bytes, bool]:
    mode = bundle.get("credential_mode")
    if mode == "password":
        if password is None:
            raise ArcImportError("A password is required to import this .arc file.")
        normalized = unicodedata.normalize("NFKD", password).encode("utf-8")
        # This format prehash is followed by PBKDF2-HMAC-SHA512 (1,000,000 rounds).
        password_hash = hashes.Hash(hashes.SHA512())
        password_hash.update(normalized)
        material = password_hash.finalize()
        return (
            PBKDF2HMAC(algorithm=hashes.SHA512(), length=32, salt=salt, iterations=1_000_000).derive(material),
            False,
        )
    if mode not in {"keyfile", "both"}:
        raise ArcImportError("This YellowSphere ARC credential mode is not supported.")
    if keyfile_path is None:
        raise ArcImportError("A keyfile is required to import this .arc file.")
    keyfile_bytes = _read_keyfile(keyfile_path, password=password)
    if mode == "keyfile":
        credential = "arc-keyfile-v1:" + base64.b64encode(keyfile_bytes).decode("ascii")
    else:
        if password is None:
            raise ArcImportError("A password is required with this .arc keyfile.")
        normalized_password = unicodedata.normalize("NFKD", password).encode("utf-8")
        combined_input = keyfile_bytes + normalized_password
        combined_hkdf = HKDF(
            algorithm=hashes.SHA512(),
            length=64,
            salt=salt,
            info=b"yellowsphere-arc-v3-combined-key",
        )
        combined_secret = combined_hkdf.derive(combined_input)
        credential = "arc-combined-v1:" + base64.b64encode(combined_secret).decode("ascii")
    hkdf = HKDF(
        algorithm=hashes.SHA512(),
        length=32,
        salt=salt,
        info=b"YellowSphere ARC v3 AES-256-GCM key",
    )
    return hkdf.derive(credential.encode("utf-8")), True


def import_arc_bytes(
    data: bytes,
    *,
    password: str | None = None,
    keyfile_path: Path | None = None,
) -> str:
    """Read a YellowSphere ARC V3 or unprotected ARC seed and return its mnemonic."""
    if len(data) > MAX_ARC_BYTES:
        raise ArcImportError("The selected file is too large to be a seed backup.")
    bundle = _parse_bundle(data)
    bundle_format = bundle.get("format")
    if bundle_format == "yellowsphere-plain-seed-v1" and bundle.get("encrypted") is False:
        payload: Any = bundle
    elif bundle_format == "yellowsphere-encrypted-seed-v3" and bundle.get("version") == 3:
        kdf = bundle.get("kdf")
        cipher = bundle.get("cipher")
        padding = bundle.get("padding")
        if not isinstance(kdf, dict) or not isinstance(cipher, dict) or not isinstance(padding, dict):
            raise ArcImportError("The YellowSphere ARC file is missing encryption metadata.")
        mode = bundle.get("credential_mode")
        uses_hkdf = mode in {"keyfile", "both"}
        expected_kdf = "HKDF" if uses_hkdf else "PBKDF2"
        if kdf.get("name") != expected_kdf or kdf.get("hash") != "SHA-512":
            raise ArcImportError("The YellowSphere ARC file uses an unsupported key derivation method.")
        if not uses_hkdf and kdf.get("iterations") != 1_000_000:
            raise ArcImportError("The YellowSphere ARC file uses an unsupported key derivation method.")
        if cipher.get("name") != "AES-256-GCM" or padding.get("name") != "ZERO" or padding.get("length") != 512:
            raise ArcImportError("The YellowSphere ARC file uses an unsupported encryption format.")
        salt = _decode_b64(kdf.get("salt_b64"), "salt", exact_length=32)
        nonce = _decode_b64(cipher.get("nonce_b64"), "nonce", exact_length=12)
        ciphertext = _decode_b64(bundle.get("ciphertext_b64"), "ciphertext")
        if len(ciphertext) != 528:
            raise ArcImportError("The YellowSphere ARC ciphertext has an invalid length.")
        key, _ = _credential(bundle, password, keyfile_path, salt)
        # Web Crypto authenticates every bundle property except the ciphertext.
        metadata = {name: value for name, value in bundle.items() if name != "ciphertext_b64"}
        aad = json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        except Exception as exc:
            raise ArcImportError("Unable to decrypt the .arc file. Check its password and keyfile.") from exc
        if len(plaintext) != 512:
            raise ArcImportError("The decrypted YellowSphere ARC payload has an invalid length.")
        payload_bytes = plaintext.rstrip(b"\0")
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArcImportError("The decrypted YellowSphere ARC payload is malformed.") from exc
    else:
        raise ArcImportError("This .arc version is not supported. Import a YellowSphere ARC V3 backup.")

    if not isinstance(payload, dict) or not isinstance(payload.get("mnemonic"), str):
        raise ArcImportError("The .arc file does not contain a seed phrase.")
    words = [word.lower() for word in payload["mnemonic"].split()]
    if len(words) not in (12, 24) or payload.get("word_count", len(words)) != len(words):
        raise ArcImportError("The .arc file does not contain a valid 12- or 24-word seed phrase.")
    return " ".join(words)


def import_arc_file(
    path: Path,
    *,
    password: str | None = None,
    keyfile_path: Path | None = None,
) -> str:
    try:
        if path.stat().st_size > MAX_ARC_BYTES:
            raise ArcImportError("The selected file is too large to be a seed backup.")
        data = path.read_bytes()
    except ArcImportError:
        raise
    except OSError as exc:
        raise ArcImportError(f"Could not read the selected .arc file: {exc}") from exc
    return import_arc_bytes(data, password=password, keyfile_path=keyfile_path)
