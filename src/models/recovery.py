from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .entry import utc_now_iso


@dataclass(slots=True)
class RecoveryEntry:
    """Account recovery codes / word lists (GitHub, BitLocker, etc.)."""

    name: str
    service: str = ""
    codes: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "service": self.service,
            "codes": self.codes,
            "notes": self.notes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecoveryEntry":
        now = utc_now_iso()
        created_at = str(data.get("created_at") or now)
        return cls(
            id=str(data.get("id") or uuid4().hex),
            name=str(data.get("name") or "Recovery codes"),
            service=str(data.get("service") or ""),
            codes=str(data.get("codes") or ""),
            notes=str(data.get("notes") or ""),
            created_at=created_at,
            modified_at=str(data.get("modified_at") or created_at),
        )

    def mark_modified(self) -> None:
        self.modified_at = utc_now_iso()

    def display_title(self) -> str:
        if self.service and self.name:
            return f"{self.service} — {self.name}"
        return self.service or self.name or "Recovery codes"

    def code_line_count(self) -> int:
        lines = [line.strip() for line in self.codes.splitlines() if line.strip()]
        if lines:
            return len(lines)
        text = self.codes.strip()
        return 1 if text else 0

    def matches(self, text: str) -> bool:
        query = text.strip().lower()
        if not query:
            return True
        haystack = [
            self.name,
            self.service,
            self.codes,
            self.notes,
            self.created_at,
            self.modified_at,
            self.display_title(),
        ]
        return any(query in item.lower() for item in haystack if item)
