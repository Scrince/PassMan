# -*- mode: python ; coding: utf-8 -*-

from src.version import APP_NAME, APP_VERSION


ASSETS_DIR = 'assets'
APP_ICON_PNG = f'{ASSETS_DIR}/passman_icon.png'
MAC_ICON = f'{ASSETS_DIR}/icns/mac/PassMan.icns'


a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[(APP_ICON_PNG, 'assets')],
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
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
    icon=[MAC_ICON],
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
app = BUNDLE(
    coll,
    name=f'{APP_NAME}.app',
    icon=MAC_ICON,
    bundle_identifier=None,
    info_plist={
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
    },
)
