from __future__ import annotations

from dataclasses import dataclass, field

from .authenticator import AuthenticatorEntry
from .entry import Entry
from .key_project import KeyProject
from .recovery import RecoveryEntry
from .seed import SeedEntry
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
    key_projects: list[KeyProject] = field(default_factory=list)
    authenticator_entries: list[AuthenticatorEntry] = field(default_factory=list)
    recovery_entries: list[RecoveryEntry] = field(default_factory=list)
    seed_entries: list[SeedEntry] = field(default_factory=list)
    settings: VaultSettings = field(default_factory=VaultSettings)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "key_projects": [project.to_dict() for project in self.key_projects],
            "authenticator_entries": [item.to_dict() for item in self.authenticator_entries],
            "recovery_entries": [item.to_dict() for item in self.recovery_entries],
            "seed_entries": [item.to_dict() for item in self.seed_entries],
            "settings": self.settings.to_dict(),
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> "VaultModel":
        raw_entries = data.get("entries", [])
        entries = [Entry.from_dict(item) for item in raw_entries if isinstance(item, dict)]
        raw_projects = data.get("key_projects", [])
        key_projects = [
            KeyProject.from_dict(item) for item in raw_projects if isinstance(item, dict)
        ]
        raw_authenticators = data.get("authenticator_entries", [])
        authenticator_entries = [
            AuthenticatorEntry.from_dict(item)
            for item in raw_authenticators
            if isinstance(item, dict)
        ]
        raw_recovery = data.get("recovery_entries", [])
        recovery_entries = [
            RecoveryEntry.from_dict(item) for item in raw_recovery if isinstance(item, dict)
        ]
        raw_seeds = data.get("seed_entries", [])
        seed_entries = [SeedEntry.from_dict(item) for item in raw_seeds if isinstance(item, dict)]
        settings = VaultSettings.from_dict(data.get("settings"))
        return cls(
            entries=entries,
            key_projects=key_projects,
            authenticator_entries=authenticator_entries,
            recovery_entries=recovery_entries,
            seed_entries=seed_entries,
            settings=settings,
        )

