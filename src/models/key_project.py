from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .entry import utc_now_iso


# OpenPGP key usage / capability flags commonly shown as C/S/E/A.
GPG_ROLE_CODES = ("C", "S", "E", "A")
GPG_ROLE_LABELS: dict[str, str] = {
    "C": "Certify",
    "S": "Sign",
    "E": "Encrypt",
    "A": "Authenticate",
}


def normalize_role(role: str) -> str:
    code = str(role or "").strip().upper()
    if code in GPG_ROLE_LABELS:
        return code
    for key, label in GPG_ROLE_LABELS.items():
        if code == label.upper():
            return key
    return "S"


def role_display(role: str) -> str:
    code = normalize_role(role)
    return f"{code} — {GPG_ROLE_LABELS[code]}"


def encode_key_file(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def decode_key_file(payload: str) -> bytes:
    text = str(payload or "").strip()
    if not text:
        return b""
    return base64.b64decode(text.encode("ascii"), validate=True)


@dataclass(slots=True)
class GpgKey:
    """One C/S/E/A key stored as a .key file under a project.

    The public half is not stored per key — it lives on KeyProject.public_asc.
    """

    role: str = "S"
    label: str = ""
    fingerprint: str = ""
    key_id: str = ""
    key_filename: str = ""
    key_data_b64: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.role = normalize_role(self.role)

    @property
    def has_key_file(self) -> bool:
        return bool(str(self.key_data_b64 or "").strip())

    @property
    def key_size_bytes(self) -> int:
        if not self.has_key_file:
            return 0
        try:
            return len(decode_key_file(self.key_data_b64))
        except Exception:
            return 0

    def set_key_file(self, filename: str, raw: bytes) -> None:
        self.key_filename = filename or "key.key"
        self.key_data_b64 = encode_key_file(raw)
        self.mark_modified()

    def clear_key_file(self) -> None:
        self.key_filename = ""
        self.key_data_b64 = ""
        self.mark_modified()

    def key_file_bytes(self) -> bytes:
        return decode_key_file(self.key_data_b64)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": normalize_role(self.role),
            "label": self.label,
            "fingerprint": self.fingerprint,
            "key_id": self.key_id,
            "key_filename": self.key_filename,
            "key_data_b64": self.key_data_b64,
            "notes": self.notes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GpgKey":
        now = utc_now_iso()
        created_at = str(data.get("created_at") or now)

        key_filename = str(data.get("key_filename", "") or "")
        key_data_b64 = str(data.get("key_data_b64", "") or "")

        # Migrate older builds that stored private key material as private_asc text.
        if not key_data_b64:
            legacy = data.get("private_asc")
            if isinstance(legacy, str) and legacy.strip():
                key_data_b64 = encode_key_file(legacy.encode("utf-8"))
                if not key_filename:
                    key_filename = f"{normalize_role(str(data.get('role', 'S'))).lower()}.key"

        return cls(
            id=str(data.get("id") or uuid4().hex),
            role=normalize_role(str(data.get("role", "S"))),
            label=str(data.get("label", "")),
            fingerprint=str(data.get("fingerprint", "")),
            key_id=str(data.get("key_id", "")),
            key_filename=key_filename,
            key_data_b64=key_data_b64,
            notes=str(data.get("notes", "")),
            created_at=created_at,
            modified_at=str(data.get("modified_at") or created_at),
        )

    def mark_modified(self) -> None:
        self.modified_at = utc_now_iso()

    def matches(self, text: str) -> bool:
        query = text.strip().lower()
        if not query:
            return True
        role = normalize_role(self.role)
        haystack = [
            role,
            GPG_ROLE_LABELS.get(role, ""),
            role_display(role),
            self.label,
            self.fingerprint,
            self.key_id,
            self.key_filename,
            self.notes,
            self.created_at,
            self.modified_at,
            ".key" if self.has_key_file else "",
        ]
        return any(query in item.lower() for item in haystack if item)


@dataclass(slots=True)
class KeyProject:
    """A project that groups C/S/E/A .key files and one public .asc half."""

    name: str
    description: str = ""
    public_asc: str = ""
    notes: str = ""
    keys: list[GpgKey] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "public_asc": self.public_asc,
            "notes": self.notes,
            "keys": [key.to_dict() for key in self.keys],
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KeyProject":
        now = utc_now_iso()
        created_at = str(data.get("created_at") or now)
        raw_keys = data.get("keys", [])
        keys = [GpgKey.from_dict(item) for item in raw_keys if isinstance(item, dict)]
        return cls(
            id=str(data.get("id") or uuid4().hex),
            name=str(data.get("name", "Untitled Project")),
            description=str(data.get("description", "")),
            public_asc=str(data.get("public_asc", "")),
            notes=str(data.get("notes", "")),
            keys=keys,
            created_at=created_at,
            modified_at=str(data.get("modified_at") or created_at),
        )

    def mark_modified(self) -> None:
        self.modified_at = utc_now_iso()

    def roles_present(self) -> list[str]:
        present: list[str] = []
        for code in GPG_ROLE_CODES:
            if any(normalize_role(key.role) == code for key in self.keys):
                present.append(code)
        return present

    def matches(self, text: str) -> bool:
        query = text.strip().lower()
        if not query:
            return True
        haystack = [
            self.name,
            self.description,
            self.public_asc,
            self.notes,
            self.created_at,
            self.modified_at,
            " ".join(self.roles_present()),
            " ".join(GPG_ROLE_LABELS[code] for code in self.roles_present()),
            ".asc" if self.public_asc.strip() else "",
        ]
        if any(query in item.lower() for item in haystack if item):
            return True
        return any(key.matches(query) for key in self.keys)
