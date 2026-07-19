#!/usr/bin/env python3
"""Cross-platform PassMan packaging entry point.

Run this on the target OS (native build only — no cross-compile from Windows):

  python build.py                 # auto-detect host platform
  python build.py --platform linux
  python build.py --platform macos --arch arm64
  python build.py --platform macos --arch x86_64
  python build.py --platform macos --arch universal2
  python build.py --platform windows
  python build.py --skip-package  # PyInstaller only (no tar/deb/dmg)

See docs/Build.txt for prerequisites and release signing steps.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

from src.version import APP_NAME, APP_VERSION


ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "src" / "main.py"
SOURCE_DIR = ROOT / "src"
ASSETS_DIR = SOURCE_DIR / "assets"
ICON_ICO = ASSETS_DIR / "passman_icon.ico"
ICON_PNG = ASSETS_DIR / "passman_icon.png"
ICON_ICNS = ASSETS_DIR / "macos" / "passman_icon.icns"
ICON_LINUX_256 = ASSETS_DIR / "linux" / "passman_icon_256x256.png"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "PassMan.spec"

# PyInstaller --add-data separator: ";" on Windows, ":" on Unix.
ADD_DATA_SEP = ";" if os.name == "nt" else ":"


def die(message: str, code: int = 1) -> int:
    print(message, file=sys.stderr)
    return code


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> int:
    print("+", " ".join(command))
    return subprocess.call(command, cwd=str(cwd or ROOT), env=env)


def host_platform() -> str:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return sys.platform


def host_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x64"
    if machine in {"aarch64", "arm64"}:
        return "arm64"
    return machine


def release_dir(os_name: str) -> Path:
    return ROOT / "release" / f"v{APP_VERSION}" / os_name


def ensure_core_assets() -> None:
    required = [ENTRY, ICON_PNG]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing required build inputs:\n  " + "\n  ".join(missing))


def pyinstaller_cli(name: str, extra: list[str] | None = None) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--paths",
        str(SOURCE_DIR),
        "--add-data",
        f"{ICON_PNG}{ADD_DATA_SEP}assets",
        "--name",
        name,
    ]
    if extra:
        command.extend(extra)
    command.append(str(ENTRY))
    return command


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def build_windows() -> int:
    if host_platform() != "windows":
        return die("Windows builds must be produced on Windows.")

    ensure_core_assets()
    if not ICON_ICO.exists():
        return die(f"Missing Windows icon: {ICON_ICO}")

    build_name = f"{APP_NAME}-{APP_VERSION}"
    command = pyinstaller_cli(
        build_name,
        ["--onefile", "--icon", str(ICON_ICO)],
    )
    result = run(command)
    if result != 0:
        return result

    built_exe = DIST_DIR / f"{build_name}.exe"
    if not built_exe.exists():
        return die(f"Build finished but executable was not found: {built_exe}")

    out = release_dir("windows")
    out.mkdir(parents=True, exist_ok=True)
    release_exe = out / f"{APP_NAME}.exe"
    shutil.copy2(built_exe, release_exe)
    print(f"Release executable: {release_exe}")
    return 0


# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------


def _linux_desktop_entry(exec_name: str = "passman") -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "Comment=Encrypted password manager\n"
        f"Exec={exec_name}\n"
        "Icon=passman\n"
        "Terminal=false\n"
        "Categories=Utility;Security;\n"
    )


def _write_tar_gz(source_dir: Path, archive_path: Path, arcname_root: str) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(source_dir, arcname=arcname_root)
    print(f"Created: {archive_path}")


def _ar_member(name: str, data: bytes, mode: int = 0o644) -> bytes:
    """Build a single GNU ar member (used for .deb packages)."""
    header = (
        f"{name:<16}"
        f"{int(time.time()):<12}"
        f"{0:<6}"
        f"{0:<6}"
        f"{mode:<8o}"
        f"{len(data):<10}"
        "`\n"
    ).encode("ascii")
    member = header + data
    if len(data) % 2 == 1:
        member += b"\n"
    return member


def _create_deb(app_dir: Path, deb_path: Path, arch: str = "amd64") -> None:
    """Create a simple Debian package without requiring dpkg-deb."""
    icon_src = ICON_LINUX_256 if ICON_LINUX_256.exists() else ICON_PNG
    if not icon_src.exists():
        raise FileNotFoundError("Need a PNG icon for the .deb package")

    with tempfile.TemporaryDirectory(prefix="passman-deb-") as tmp:
        tmp_path = Path(tmp)
        rootfs = tmp_path / "root"
        opt_app = rootfs / "opt" / APP_NAME
        bin_dir = rootfs / "usr" / "bin"
        apps_dir = rootfs / "usr" / "share" / "applications"
        icon_dir = rootfs / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
        for path in (opt_app, bin_dir, apps_dir, icon_dir):
            path.mkdir(parents=True, exist_ok=True)

        shutil.copytree(app_dir, opt_app, dirs_exist_ok=True)
        passman_bin = opt_app / APP_NAME
        if passman_bin.exists():
            passman_bin.chmod(passman_bin.stat().st_mode | 0o111)

        launcher = bin_dir / "passman"
        launcher.write_text(
            "#!/bin/sh\n"
            f'exec /opt/{APP_NAME}/{APP_NAME} "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        launcher.chmod(0o755)

        (apps_dir / "passman.desktop").write_text(
            _linux_desktop_entry("passman"),
            encoding="utf-8",
            newline="\n",
        )
        shutil.copy2(icon_src, icon_dir / "passman.png")

        installed_size = sum(p.stat().st_size for p in rootfs.rglob("*") if p.is_file())
        installed_kib = max(1, installed_size // 1024)

        control = (
            f"Package: passman\n"
            f"Version: {APP_VERSION}\n"
            f"Section: utils\n"
            f"Priority: optional\n"
            f"Architecture: {arch}\n"
            f"Installed-Size: {installed_kib}\n"
            f"Maintainer: PassMan <passman@example.local>\n"
            f"Description: Encrypted password manager\n"
            f" PassMan is a local desktop password manager with an encrypted vault.\n"
        )
        control_path = tmp_path / "control"
        control_path.write_text(control, encoding="utf-8", newline="\n")

        data_tar = tmp_path / "data.tar.xz"
        control_tar = tmp_path / "control.tar.xz"

        with tarfile.open(data_tar, "w:xz") as tar:
            # recursive=False: rglob already walks the tree; recursive add would
            # re-embed every directory's children and bloat the .deb massively.
            for path in sorted(rootfs.rglob("*")):
                arcname = path.relative_to(rootfs).as_posix()
                tar.add(path, arcname=arcname, recursive=False)

        with tarfile.open(control_tar, "w:xz") as tar:
            tar.add(control_path, arcname="control", recursive=False)

        deb_path.parent.mkdir(parents=True, exist_ok=True)
        with deb_path.open("wb") as out:
            out.write(b"!<arch>\n")
            out.write(_ar_member("debian-binary", b"2.0\n"))
            out.write(_ar_member("control.tar.xz", control_tar.read_bytes()))
            out.write(_ar_member("data.tar.xz", data_tar.read_bytes()))

    print(f"Created: {deb_path}")


def build_linux(*, package: bool = True) -> int:
    if host_platform() != "linux":
        return die(
            "Linux builds must be produced on Linux "
            f"(current host is {host_platform()})."
        )

    ensure_core_assets()
    arch = host_arch()
    if arch not in {"x64", "arm64"}:
        return die(f"Unsupported Linux architecture: {arch}")

    dist_label = f"linux-{arch}"
    work_dist = DIST_DIR / dist_label
    if work_dist.exists():
        shutil.rmtree(work_dist)

    extra = [
        "--onedir",
        "--distpath",
        str(work_dist),
        "--workpath",
        str(BUILD_DIR / dist_label),
    ]
    if ICON_PNG.exists():
        extra.extend(["--icon", str(ICON_PNG)])

    result = run(pyinstaller_cli(APP_NAME, extra))
    if result != 0:
        return result

    app_dir = work_dist / APP_NAME
    binary = app_dir / APP_NAME
    if not binary.exists():
        return die(f"Build finished but binary was not found: {binary}")
    binary.chmod(binary.stat().st_mode | 0o111)
    print(f"Linux onedir build: {app_dir}")

    if not package:
        return 0

    dist_tar = DIST_DIR / f"{APP_NAME}-linux-{arch}.tar.gz"
    dist_deb = DIST_DIR / f"{APP_NAME}-linux-{arch}.deb"
    _write_tar_gz(app_dir, dist_tar, APP_NAME)

    deb_arch = "amd64" if arch == "x64" else "arm64"
    try:
        _create_deb(app_dir, dist_deb, arch=deb_arch)
    except Exception as exc:  # noqa: BLE001
        return die(f"Failed to create .deb package: {exc}")

    out = release_dir("linux")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dist_tar, out / dist_tar.name)
    shutil.copy2(dist_deb, out / dist_deb.name)
    print(f"Release artifacts copied to: {out}")
    print("Next (optional on the build machine):")
    print(f"  cd {out}")
    print(f"  sha256sum {dist_tar.name} {dist_deb.name} > SHA256SUMS")
    print("  gpg --detach-sign --armor SHA256SUMS")
    print(f"  gpg --detach-sign --armor {dist_tar.name}")
    print(f"  gpg --detach-sign --armor {dist_deb.name}")
    return 0


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


def _resolve_macos_arch(arch: str) -> str:
    if arch == "native":
        detected = host_arch()
        if detected == "arm64":
            return "arm64"
        if detected == "x64":
            return "x86_64"
        return detected
    if arch in {"arm64", "x86_64", "universal2"}:
        return arch
    raise ValueError(
        f"Unsupported macOS arch: {arch} (use arm64, x86_64, universal2, or native)"
    )


def _macos_label(arch: str) -> str:
    return {
        "arm64": "arm64",
        "x86_64": "x64",
        "universal2": "universal",
    }.get(arch, arch)


def _create_dmg(app_bundle: Path, dmg_path: Path, volume_name: str) -> int:
    """Create a simple read-only DMG with hdiutil (macOS only)."""
    if not app_bundle.exists():
        return die(f"App bundle not found for DMG: {app_bundle}")
    if shutil.which("hdiutil") is None:
        return die("hdiutil not found; cannot create DMG on this system.")

    dmg_path.parent.mkdir(parents=True, exist_ok=True)
    if dmg_path.exists():
        dmg_path.unlink()

    with tempfile.TemporaryDirectory(prefix="passman-dmg-") as tmp:
        stage = Path(tmp) / "stage"
        stage.mkdir()
        shutil.copytree(app_bundle, stage / app_bundle.name, symlinks=True)
        try:
            (stage / "Applications").symlink_to("/Applications")
        except OSError:
            pass

        result = run(
            [
                "hdiutil",
                "create",
                "-volname",
                volume_name,
                "-srcfolder",
                str(stage),
                "-ov",
                "-format",
                "UDZO",
                str(dmg_path),
            ]
        )
        if result != 0:
            return result

    print(f"Created: {dmg_path}")
    return 0


def build_macos(*, arch: str = "native", package: bool = True) -> int:
    if host_platform() != "macos":
        return die(
            "macOS builds must be produced on macOS "
            f"(current host is {host_platform()})."
        )

    ensure_core_assets()
    if not ICON_ICNS.exists():
        return die(f"Missing macOS icon: {ICON_ICNS}")
    if not SPEC_FILE.exists():
        return die(f"Missing PyInstaller spec: {SPEC_FILE}")

    try:
        resolved_arch = _resolve_macos_arch(arch)
    except ValueError as exc:
        return die(str(exc))

    label = _macos_label(resolved_arch)
    dist_label = f"macos-{label}"
    work_dist = DIST_DIR / dist_label
    work_path = BUILD_DIR / dist_label
    if work_dist.exists():
        shutil.rmtree(work_dist)

    env = os.environ.copy()
    env["PASSMAN_TARGET_ARCH"] = resolved_arch

    result = run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(work_dist),
            "--workpath",
            str(work_path),
            str(SPEC_FILE),
        ],
        env=env,
    )
    if result != 0:
        return result

    app_bundle = work_dist / f"{APP_NAME}.app"
    onedir = work_dist / APP_NAME
    if not app_bundle.exists():
        # Older layouts sometimes place the bundle one level higher.
        alt = DIST_DIR / f"{APP_NAME}.app"
        if alt.exists():
            app_bundle = alt

    if app_bundle.exists():
        print(f"macOS app bundle: {app_bundle}")
    elif onedir.exists():
        print(f"macOS onedir (no .app): {onedir}")
    else:
        return die(f"Build finished but neither .app nor onedir was found under {work_dist}")

    if not package:
        return 0

    if not app_bundle.exists():
        return die(f"Cannot package DMG; app bundle missing: {app_bundle}")

    dmg_name = f"{APP_NAME}-macOS-{label}.dmg"
    dist_dmg = DIST_DIR / dmg_name
    result = _create_dmg(app_bundle, dist_dmg, f"{APP_NAME} {APP_VERSION}")
    if result != 0:
        return result

    out = release_dir("macos")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dist_dmg, out / dmg_name)
    print(f"Release artifact: {out / dmg_name}")
    print("Next (optional on the build machine):")
    print(f"  cd {out}")
    print(f"  shasum -a 256 {dmg_name} >> SHA256SUMS")
    print(f"  gpg --detach-sign --armor {dmg_name}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Build {APP_NAME} {APP_VERSION} for the current platform.",
    )
    parser.add_argument(
        "--platform",
        choices=("auto", "windows", "linux", "macos"),
        default="auto",
        help="Target platform (default: auto-detect host). "
        "Must match the machine you are building on.",
    )
    parser.add_argument(
        "--arch",
        default="native",
        help="macOS only: arm64, x86_64, universal2, or native (default).",
    )
    parser.add_argument(
        "--skip-package",
        action="store_true",
        help="Run PyInstaller only; skip tar.gz/.deb/.dmg packaging steps.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target = host_platform() if args.platform == "auto" else args.platform
    package = not args.skip_package

    print(f"PassMan build {APP_VERSION}")
    print(f"  host platform : {host_platform()} ({platform.platform()})")
    print(f"  host arch     : {host_arch()} ({platform.machine()})")
    print(f"  target        : {target}")
    print(f"  python        : {sys.version.split()[0]} ({sys.executable})")
    print(f"  package steps : {package}")

    if target == "windows":
        return build_windows()
    if target == "linux":
        return build_linux(package=package)
    if target == "macos":
        return build_macos(arch=args.arch, package=package)
    return die(f"Unsupported platform: {target}")


if __name__ == "__main__":
    raise SystemExit(main())
