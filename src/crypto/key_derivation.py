from __future__ import annotations

from typing import Any

from argon2.low_level import Type, hash_secret_raw


DEFAULT_KDF_PARAMS = {
    "type": "argon2id",
    "time_cost": 3,
    "memory_cost": 65536,
    "parallelism": 4,
    "hash_len": 32,
}

# Bounds for vault-header KDF params (crafted vaults cannot OOM the process).
_KDF_TIME_MIN = 1
_KDF_TIME_MAX = 10
_KDF_MEMORY_MIN = 8_192  # KiB
_KDF_MEMORY_MAX = 1_048_576  # KiB (1 GiB)
_KDF_PARALLEL_MIN = 1
_KDF_PARALLEL_MAX = 8
_KDF_HASH_LEN = 32


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def sanitize_kdf_params(params: dict[str, Any] | None = None) -> dict[str, int | str]:
    """Allowlist and clamp KDF parameters from a vault header."""
    active: dict[str, int | str] = dict(DEFAULT_KDF_PARAMS)
    if params:
        if "time_cost" in params:
            active["time_cost"] = _clamp_int(
                params["time_cost"],
                int(DEFAULT_KDF_PARAMS["time_cost"]),
                _KDF_TIME_MIN,
                _KDF_TIME_MAX,
            )
        if "memory_cost" in params:
            active["memory_cost"] = _clamp_int(
                params["memory_cost"],
                int(DEFAULT_KDF_PARAMS["memory_cost"]),
                _KDF_MEMORY_MIN,
                _KDF_MEMORY_MAX,
            )
        if "parallelism" in params:
            active["parallelism"] = _clamp_int(
                params["parallelism"],
                int(DEFAULT_KDF_PARAMS["parallelism"]),
                _KDF_PARALLEL_MIN,
                _KDF_PARALLEL_MAX,
            )
    active["type"] = "argon2id"
    active["hash_len"] = _KDF_HASH_LEN
    return active


def derive_key(password: str, salt: bytes, params: dict[str, int | str] | None = None) -> bytes:
    if not password:
        raise ValueError("Password cannot be empty.")
    active = sanitize_kdf_params(params)
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=int(active["time_cost"]),
        memory_cost=int(active["memory_cost"]),
        parallelism=int(active["parallelism"]),
        hash_len=int(active["hash_len"]),
        type=Type.ID,
    )
