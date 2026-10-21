# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

try:
    ROOT = Path(SPECPATH).resolve()
except NameError:
    ROOT = Path(__file__).resolve().parent

SRC = ROOT / 'src'
ASSETS = SRC / 'assets'

a = Analysis(
    [str(SRC / 'main.py')],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(ASSETS / 'passman_icon.png'), 'assets')],
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
    a.binaries,
    a.datas,
    [],
    name='PassMan-1.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ASSETS / 'passman_icon.ico')],
)
