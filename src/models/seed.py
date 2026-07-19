from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .entry import utc_now_iso

ALLOWED_WORD_COUNTS = (12, 24)


def normalize_seed_phrase(text: str) -> str:
    """Collapse whitespace and lowercase BIP39-style phrases for consistent storage."""
    words = [part.lower() for part in str(text or "").strip().split() if part]
    return " ".join(words)


def seed_word_list(text: str) -> list[str]:
    return [part.lower() for part in str(text or "").strip().split() if part]


@dataclass(slots=True)
class SeedEntry:
    """Cryptocurrency wallet seed phrases (typically 12 or 24 words) + optional passphrase."""

    name: str
    wallet: str = ""
    word_count: int = 12
    seed_phrase: str = ""
    passphrase: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        try:
            count = int(self.word_count)
        except (TypeError, ValueError):
            count = 12
        self.word_count = count if count in ALLOWED_WORD_COUNTS else 12
        self.seed_phrase = normalize_seed_phrase(self.seed_phrase)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "wallet": self.wallet,
            "word_count": self.word_count,
            "seed_phrase": self.seed_phrase,
            "passphrase": self.passphrase,
            "notes": self.notes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SeedEntry":
        now = utc_now_iso()
        created_at = str(data.get("created_at") or now)
        try:
            word_count = int(data.get("word_count") or 12)
        except (TypeError, ValueError):
            word_count = 12
        return cls(
            id=str(data.get("id") or uuid4().hex),
            name=str(data.get("name") or "Wallet seed"),
            wallet=str(data.get("wallet") or ""),
            word_count=word_count,
            seed_phrase=str(data.get("seed_phrase") or ""),
            passphrase=str(data.get("passphrase") or ""),
            notes=str(data.get("notes") or ""),
            created_at=created_at,
            modified_at=str(data.get("modified_at") or created_at),
        )

    def mark_modified(self) -> None:
        self.modified_at = utc_now_iso()

    def display_title(self) -> str:
        if self.wallet and self.name:
            return f"{self.wallet} — {self.name}"
        return self.wallet or self.name or "Wallet seed"

    def actual_word_count(self) -> int:
        return len(seed_word_list(self.seed_phrase))

    def phrase_matches_word_count(self) -> bool:
        return self.actual_word_count() == self.word_count

    def masked_phrase_preview(self) -> str:
        words = seed_word_list(self.seed_phrase)
        if not words:
            return "(empty)"
        if len(words) == 1:
            return "••••"
        return f"{words[0]} · · · ({len(words)} words)"

    def matches(self, text: str) -> bool:
        query = text.strip().lower()
        if not query:
            return True
        haystack = [
            self.name,
            self.wallet,
            self.seed_phrase,
            self.passphrase,
            self.notes,
            str(self.word_count),
            self.created_at,
            self.modified_at,
            self.display_title(),
        ]
        return any(query in item.lower() for item in haystack if item)
