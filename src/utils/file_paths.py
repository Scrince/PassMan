from __future__ import annotations

import sys
from pathlib import Path


VAULT_FILENAME = "vault.dat"
APP_DATA_DIRNAME = "PassMan"


def app_dir() -> Path:
    """Directory used for vault.dat (and its automatic backup).

    - Source checkout: repository root
    - Frozen Linux: $XDG_DATA_HOME/PassMan or ~/.local/share/PassMan
    - Frozen macOS: ~/Library/Application Support/PassMan
    - Frozen Windows: %LOCALAPPDATA%/PassMan
    - Other frozen platforms: directory containing the executable
    """
    if getattr(sys, "frozen", False):
        if sys.platform.startswith("linux"):
            from os import environ

            data_root = Path(environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
            return data_root / APP_DATA_DIRNAME
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / APP_DATA_DIRNAME
        if sys.platform.startswith("win"):
            from os import environ

            data_root = Path(environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            return data_root / APP_DATA_DIRNAME
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundled_dir() -> Path:
    """Find bundled assets whether frozen by PyInstaller or running from source."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def asset_path(filename: str) -> Path:
    return bundled_dir() / "assets" / filename


def vault_path() -> Path:
    if getattr(sys, "frozen", False) and sys.platform.startswith("win"):
        executable_vault = Path(sys.executable).resolve().parent / VAULT_FILENAME
        executable_backup = executable_vault.with_name(f"{VAULT_FILENAME}.bak")
        if executable_vault.is_file() or executable_backup.is_file():
            return executable_vault
    return app_dir() / VAULT_FILENAME
