from __future__ import annotations

import sys
from pathlib import Path


VAULT_FILENAME = "vault.dat"
APP_DATA_DIRNAME = "PassMan"


def app_dir() -> Path:
    """Use the app folder in a build, and the repo root while developing."""
    if getattr(sys, "frozen", False):
        if sys.platform.startswith("linux"):
            from os import environ

            data_root = Path(environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
            return data_root / APP_DATA_DIRNAME
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundled_dir() -> Path:
    """Find bundled assets whether we are frozen by PyInstaller or running from source."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def asset_path(filename: str) -> Path:
    return bundled_dir() / "assets" / filename


def vault_path() -> Path:
    return app_dir() / VAULT_FILENAME
