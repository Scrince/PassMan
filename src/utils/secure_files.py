from __future__ import annotations

import os
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile


def _restrict_permissions(path: Path) -> None:
    if os.name == "nt":
        username = os.environ.get("USERNAME")
        if not username:
            raise OSError("Could not determine the current Windows account for file permissions.")
        domain = os.environ.get("USERDOMAIN")
        account = f"{domain}\\{username}" if domain else username
        # Set the ACL before writing any private key bytes to disk.
        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"{account}:(F)",
                "*S-1-5-18:(F)",  # Local System
                "*S-1-5-32-544:(F)",  # Local Administrators
            ],
            check=True,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return

    os.chmod(path, 0o600)


def write_private_file(path: Path, data: bytes) -> None:
    """Atomically write secret material with restrictive file permissions."""
    path = Path(path)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile("wb", dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            _restrict_permissions(temporary_path)
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        if os.name != "nt":
            os.chmod(path, 0o600)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
