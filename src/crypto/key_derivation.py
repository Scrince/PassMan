from __future__ import annotations

from argon2.low_level import Type, hash_secret_raw


DEFAULT_KDF_PARAMS = {
    "type": "argon2id",
    "time_cost": 3,
    "memory_cost": 65536,
    "parallelism": 4,
    "hash_len": 32,
}

KDF_BOUNDS = {
    "time_cost": (1, 10),
    "memory_cost": (8192, 262144),
    "parallelism": (1, 8),
    "hash_len": (32, 32),
}


class KDFParameterError(ValueError):
    """The vault asks for unsupported key derivation settings."""


def derive_key(password: str, salt: bytes, params: dict[str, int | str] | None = None) -> bytes:
    if not password:
        raise ValueError("Password cannot be empty.")
    active = dict(DEFAULT_KDF_PARAMS)
    if params:
        active.update(params)
    if active.get("type") != "argon2id":
        raise KDFParameterError("Unsupported key derivation function.")
    for name, (minimum, maximum) in KDF_BOUNDS.items():
        try:
            value = int(active[name])
        except (KeyError, TypeError, ValueError) as exc:
            raise KDFParameterError(f"Invalid {name} value.") from exc
        if value < minimum or value > maximum:
            raise KDFParameterError(f"{name} is outside the supported range.")
        active[name] = value
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=active["time_cost"],
        memory_cost=active["memory_cost"],
        parallelism=active["parallelism"],
        hash_len=active["hash_len"],
        type=Type.ID,
    )
