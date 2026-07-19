from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from utils.totp import (
    generate_hotp,
    generate_totp,
    normalize_secret,
    seconds_remaining,
)
from .entry import utc_now_iso


@dataclass(slots=True)
class AuthenticatorEntry:
    name: str
    secret: str
    issuer: str = ""
    type: str = "totp"  # totp | hotp
    algorithm: str = "SHA1"
    digits: int = 6
    period: int = 30
    counter: int = 0
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.type = "hotp" if str(self.type).lower() == "hotp" else "totp"
        self.secret = normalize_secret(self.secret)
        self.algorithm = str(self.algorithm or "SHA1").upper()
        try:
            self.digits = int(self.digits)
        except (TypeError, ValueError):
            self.digits = 6
        self.digits = 6 if self.digits not in {6, 7, 8} else self.digits
        try:
            self.period = max(1, min(300, int(self.period)))
        except (TypeError, ValueError):
            self.period = 30
        try:
            self.counter = max(0, int(self.counter))
        except (TypeError, ValueError):
            self.counter = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "issuer": self.issuer,
            "secret": self.secret,
            "type": self.type,
            "algorithm": self.algorithm,
            "digits": self.digits,
            "period": self.period,
            "counter": self.counter,
            "notes": self.notes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthenticatorEntry":
        now = utc_now_iso()
        created_at = str(data.get("created_at") or now)
        return cls(
            id=str(data.get("id") or uuid4().hex),
            name=str(data.get("name") or "Authenticator"),
            issuer=str(data.get("issuer") or ""),
            secret=str(data.get("secret") or ""),
            type=str(data.get("type") or "totp"),
            algorithm=str(data.get("algorithm") or "SHA1"),
            digits=int(data.get("digits") or 6),
            period=int(data.get("period") or 30),
            counter=int(data.get("counter") or 0),
            notes=str(data.get("notes") or ""),
            created_at=created_at,
            modified_at=str(data.get("modified_at") or created_at),
        )

    def mark_modified(self) -> None:
        self.modified_at = utc_now_iso()

    def display_title(self) -> str:
        if self.issuer and self.name:
            return f"{self.issuer} ({self.name})"
        return self.issuer or self.name or "Authenticator"

    def current_code(self) -> str:
        if self.type == "hotp":
            return generate_hotp(
                self.secret,
                self.counter,
                digits=self.digits,
                algorithm=self.algorithm,
            )
        return generate_totp(
            self.secret,
            period=self.period,
            digits=self.digits,
            algorithm=self.algorithm,
        )

    def seconds_remaining(self) -> int:
        if self.type == "hotp":
            return 0
        return seconds_remaining(self.period)

    def matches(self, text: str) -> bool:
        query = text.strip().lower()
        if not query:
            return True
        haystack = [
            self.name,
            self.issuer,
            self.type,
            self.algorithm,
            self.notes,
            self.created_at,
            self.modified_at,
            self.display_title(),
        ]
        return any(query in item.lower() for item in haystack if item)
