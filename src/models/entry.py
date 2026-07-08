from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Entry:
    name: str
    type: str
    fields: dict[str, Any] = field(default_factory=dict)
    field_types: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "fields": dict(self.fields),
            "field_types": dict(self.field_types),
            "notes": self.notes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entry":
        now = utc_now_iso()
        created_at = str(data.get("created_at") or now)
        raw_fields = data.get("fields", {})
        fields = dict(raw_fields) if isinstance(raw_fields, dict) else {}
        raw_field_types = data.get("field_types", {})
        field_types = _field_types_from_dict(raw_field_types, fields)
        return cls(
            id=str(data.get("id") or uuid4().hex),
            name=str(data.get("name", "Untitled")),
            type=str(data.get("type", "Custom")),
            fields=fields,
            field_types=field_types,
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
        haystack = [self.name, self.type, self.created_at, self.modified_at, self.notes]
        haystack.extend(str(key) for key in self.fields.keys())
        haystack.extend(str(value) for value in self.fields.values())
        return any(query in item.lower() for item in haystack)


def normalize_field_type(value: object) -> str:
    field_type = str(value or "text").lower()
    if field_type not in {"text", "password", "notes"}:
        return "text"
    return field_type


def _field_types_from_dict(raw_field_types: object, fields: dict[str, Any]) -> dict[str, str]:
    if not isinstance(raw_field_types, dict):
        return {}
    return {
        str(name): normalize_field_type(raw_field_types.get(name))
        for name in fields
        if name in raw_field_types
    }
