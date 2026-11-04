"""Portable PyInstaller spec for PassMan.

Uses relative paths only so the same file works on Linux, macOS, and Windows
checkouts. Prefer `python build.py` which invokes platform-specific packaging;
this spec is primarily for macOS .app bundling and manual PyInstaller runs.

Optional environment:
  PASSMAN_TARGET_ARCH  - arm64 | x86_64 | universal2 (macOS only)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    ROOT = Path(SPECPATH).resolve()
except NameError:
    ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.version import APP_NAME, APP_VERSION

SRC = ROOT / "src"
ASSETS = SRC / "assets"
APP_ICON_PNG = ASSETS / "passman_icon.png"
MAC_ICON = ASSETS / "macos" / "passman_icon.icns"
WIN_ICON = ASSETS / "passman_icon.ico"

TARGET_ARCH = os.environ.get("PASSMAN_TARGET_ARCH") or None
if TARGET_ARCH in {"", "native", "None"}:
    TARGET_ARCH = None

if sys.platform == "darwin" and MAC_ICON.exists():
    EXE_ICON = [str(MAC_ICON)]
elif sys.platform.startswith("win") and WIN_ICON.exists():
    EXE_ICON = [str(WIN_ICON)]
elif APP_ICON_PNG.exists():
    EXE_ICON = [str(APP_ICON_PNG)]
else:
    EXE_ICON = None


a = Analysis(
    [str(SRC / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(APP_ICON_PNG), "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=sys.platform == "darwin",
    target_arch=TARGET_ARCH,
    codesign_identity=None,
    entitlements_file=None,
    icon=EXE_ICON,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(MAC_ICON) if MAC_ICON.exists() else None,
        bundle_identifier="local.passman.app",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "CFBundleIdentifier": "local.passman.app",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
