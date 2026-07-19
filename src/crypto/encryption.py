from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ALGORITHM = "AES-256-GCM"
NONCE_SIZE = 12


class DecryptionError(Exception):
    pass
                                                                                


def new_nonce() -> bytes:
    return os.urandom(NONCE_SIZE)


def encrypt_json_bytes(plaintext: bytes, key: bytes, nonce: bytes) -> bytes:
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key.")
    return AESGCM(key).encrypt(nonce, plaintext, None)


def decrypt_json_bytes(ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise DecryptionError("Incorrect password or corrupted vault.") from exc
