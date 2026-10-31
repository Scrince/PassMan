from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from utils.secure_files import write_private_file


class SecureFileTests(unittest.TestCase):
    def test_write_private_file_creates_and_replaces_secret_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.key"
            path.write_bytes(b"old key")
            if os.name != "nt":
                path.chmod(0o644)

            write_private_file(path, b"new private key")

            self.assertEqual(path.read_bytes(), b"new private key")
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main(verbosity=2)
