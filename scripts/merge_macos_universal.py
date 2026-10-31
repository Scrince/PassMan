from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


CRYPT_WHEEL_TAG = "cp314-abi3-macosx_11_0_universal2"


def macho_files(root: Path) -> set[Path]:
    found: set[Path] = set()
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink() and not path.name.startswith("._"):
            result = subprocess.run(
                ["/usr/bin/lipo", "-archs", str(path)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                found.add(path.relative_to(root))
    return found


def merge_apps(arm_app: Path, x64_app: Path, output_app: Path) -> int:
    arm_files = macho_files(arm_app)
    x64_files = macho_files(x64_app)
    if arm_files != x64_files:
        only_arm = sorted(map(str, arm_files - x64_files))
        only_x64 = sorted(map(str, x64_files - arm_files))
        raise RuntimeError(f"Mach-O file sets differ. arm64-only={only_arm}; x64-only={only_x64}")

    def ignore_appledouble(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name.startswith("._")}

    if output_app.exists():
        shutil.rmtree(output_app)
    shutil.copytree(arm_app, output_app, symlinks=True, ignore=ignore_appledouble)

    with tempfile.TemporaryDirectory(
        prefix="passman-universal-lipo-", dir=output_app.parent
    ) as temp_dir:
        for relative in sorted(arm_files):
            target = output_app / relative
            source_x64 = x64_app / relative
            merged = Path(temp_dir) / "merged"
            subprocess.run(
                ["/usr/bin/lipo", "-create", str(target), str(source_x64), "-output", str(merged)],
                check=True,
            )
            shutil.copymode(target, merged)
            os.replace(merged, target)

    wheel_path = output_app / "Contents/Resources/cryptography-50.0.2.dist-info/WHEEL"
    record_path = wheel_path.with_name("RECORD")
    if not wheel_path.is_file() or not record_path.is_file():
        raise RuntimeError("Could not find bundled cryptography wheel metadata.")
    wheel_text = wheel_path.read_text(encoding="utf-8")
    lines = [line for line in wheel_text.splitlines() if not line.startswith("Tag: ")]
    lines.append(f"Tag: {CRYPT_WHEEL_TAG}")
    wheel_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    wheel_path.write_bytes(wheel_bytes)

    rows = list(csv.reader(io.StringIO(record_path.read_text(encoding="utf-8"))))
    relative_wheel = wheel_path.relative_to(output_app / "Contents/Resources").as_posix()
    digest = base64.urlsafe_b64encode(hashlib.sha256(wheel_bytes).digest()).rstrip(b"=").decode("ascii")
    for row in rows:
        if row and row[0] == relative_wheel:
            row[1] = f"sha256={digest}"
            row[2] = str(len(wheel_bytes))
            break
    else:
        raise RuntimeError("cryptography WHEEL entry is missing from RECORD.")
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    record_path.write_text(output.getvalue(), encoding="utf-8")
    return len(arm_files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge native PassMan macOS bundles into a universal2 app.")
    parser.add_argument("arm64_app", type=Path)
    parser.add_argument("x64_app", type=Path)
    parser.add_argument("output_app", type=Path)
    args = parser.parse_args()
    count = merge_apps(args.arm64_app, args.x64_app, args.output_app)
    print(f"Merged {count} Mach-O files into {args.output_app}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
