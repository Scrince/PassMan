from __future__ import annotations

from dataclasses import dataclass, field

from .entry import Entry
from utils.themes import DEFAULT_THEME_NAME, THEME_OPTIONS


@dataclass(slots=True)
class VaultSettings:
    debug_enabled: bool = False
    auto_lock_seconds: int = 300
    clipboard_clear_seconds: int = 30
    theme_name: str = DEFAULT_THEME_NAME

    def to_dict(self) -> dict[str, object]:
        return {
            "debug_enabled": self.debug_enabled,
            "auto_lock_seconds": self.auto_lock_seconds,
            "clipboard_clear_seconds": self.clipboard_clear_seconds,
            "theme_name": self.theme_name,
        }

    @classmethod
    def from_dict(cls, data: object) -> "VaultSettings":
        if not isinstance(data, dict):
            return cls()
        theme_name = str(data.get("theme_name") or DEFAULT_THEME_NAME)
        if theme_name not in THEME_OPTIONS:
            theme_name = DEFAULT_THEME_NAME
        return cls(
            debug_enabled=bool(data.get("debug_enabled", False)),
            auto_lock_seconds=_bounded_int(data.get("auto_lock_seconds"), 300, 0, 3600),
            clipboard_clear_seconds=_bounded_int(data.get("clipboard_clear_seconds"), 30, 0, 600),
            theme_name=theme_name,
        )


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


@dataclass(slots=True)
class VaultModel:
    entries: list[Entry] = field(default_factory=list)
    settings: VaultSettings = field(default_factory=VaultSettings)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "settings": self.settings.to_dict(),
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> "VaultModel":
        raw_entries = data.get("entries", [])
        entries = [Entry.from_dict(item) for item in raw_entries if isinstance(item, dict)]
        settings = VaultSettings.from_dict(data.get("settings"))
        return cls(entries=entries, settings=settings)
