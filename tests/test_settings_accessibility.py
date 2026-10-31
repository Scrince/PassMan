from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from gui.settings_window import SettingsWindow  # noqa: E402


class SettingsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_controls_have_accessible_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = SettingsWindow(False, False, 300, 30, "Dark", Path(directory) / "vault.dat")
            self.addCleanup(window.close)
            self.assertEqual(window.move_vault_button.accessibleName(), "Move the vault and backup to another folder")
            self.assertEqual(window.vault_path_label.accessibleName(), "Current vault file path")
            self.assertIn("auto-lock timeout", window.auto_lock_control.value_edit.accessibleName())
            self.assertEqual(window.theme_combo.accessibleName(), "Application theme")


if __name__ == "__main__":
    unittest.main(verbosity=2)
