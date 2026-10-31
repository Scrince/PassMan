from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ALGORITHM = "AES-256-GCM"
NONCE_SIZE = 12


class DecryptionError(Exception):
    pass


def header_associated_data(header: Mapping[str, Any]) -> bytes:
    """Return the canonical AEAD data for a vault header."""
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")


def new_nonce() -> bytes:
    return os.urandom(NONCE_SIZE)


def encrypt_json_bytes(
    plaintext: bytes,
    key: bytes,
    nonce: bytes,
    associated_data: bytes | None = None,
) -> bytes:
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key.")
    return AESGCM(key).encrypt(nonce, plaintext, associated_data)


def decrypt_json_bytes(
    ciphertext: bytes,
    key: bytes,
    nonce: bytes,
    associated_data: bytes | None = None,
) -> bytes:
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, associated_data)
    except InvalidTag as exc:
        raise DecryptionError("Incorrect password or corrupted vault.") from exc
