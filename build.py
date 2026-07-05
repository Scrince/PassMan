from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.version import APP_NAME, APP_VERSION


ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "src" / "main.py"
SOURCE_DIR = ROOT / "src"
ASSETS_DIR = ROOT / "assets"
ICON_FILE = ASSETS_DIR / "passman_icon.ico"
ICON_PNG = ASSETS_DIR / "passman_icon.png"


def main() -> int:
    """Package PassMan into the single-file Windows app we ship."""
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--paths",
        str(SOURCE_DIR),
        "--icon",
        str(ICON_FILE),
        "--add-data",
        f"{ICON_PNG};assets",
        "--name",
        f"{APP_NAME}-{APP_VERSION}",
        str(ENTRY),
    ]
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
