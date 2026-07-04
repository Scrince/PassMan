from __future__ import annotations

from argon2.low_level import Type, hash_secret_raw


DEFAULT_KDF_PARAMS = {
    "type": "argon2id",
    "time_cost": 3,
    "memory_cost": 65536,
    "parallelism": 4,
    "hash_len": 32,
}


def derive_key(password: str, salt: bytes, params: dict[str, int | str] | None = None) -> bytes:
    if not password:
        raise ValueError("Password cannot be empty.")
    active = dict(DEFAULT_KDF_PARAMS)
    if params:
        active.update(params)
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=int(active["time_cost"]),
        memory_cost=int(active["memory_cost"]),
        parallelism=int(active["parallelism"]),
        hash_len=int(active["hash_len"]),
        type=Type.ID,
    )
