from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PyQt6.QtCore import QSettings, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox  # noqa: E402

from crypto.vault import Vault  # noqa: E402
from gui.settings_window import SettingsWindow  # noqa: E402
from main import PassManApp, PasswordDialog  # noqa: E402
from models.entry import Entry  # noqa: E402


class VaultSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.settings = QSettings(str(directory / "settings.ini"), QSettings.Format.IniFormat)
        self.settings.setValue("vault/directory", str(directory))
        self.settings.sync()
        self.app = self.new_app()
        self.addCleanup(self.app.close_and_lock_vault)
        self.original = self.app.vault
        self.assertEqual(self.original.path, directory / "vault.dat")
        self.original.create("original-test-password")
        self.original.model.entries.append(Entry("Original test entry", "Custom", {}))
        self.original.save()
        self.app.show_main_window()

        self.target_path = directory / "second-vault.dat"
        target = Vault(self.target_path)
        target.create("target-test-password")
        target.model.entries.append(Entry("Target test entry", "Custom", {}))
        target.save()
        target.lock()

    def new_app(self) -> PassManApp:
        with (
            patch("main.QApplication", return_value=self.qt),
            patch("main.QSettings", return_value=self.settings),
        ):
            return PassManApp()

    def open_settings_and_select(self, selected: str) -> None:
        def click_change_vault(dialog: SettingsWindow) -> int:
            def select_file() -> None:
                dialog.change_vault_button.click()
                if dialog.isVisible():
                    dialog.reject()

            QTimer.singleShot(0, select_file)
            return QDialog.exec(dialog)

        with (
            patch.object(SettingsWindow, "exec", new=click_change_vault),
            patch.object(QFileDialog, "getOpenFileName", return_value=(selected, "")),
        ):
            self.app.window.open_settings()

    def test_settings_switch_retries_and_remembers_the_exact_file(self) -> None:
        passwords = iter(("incorrect-test-password", "target-test-password"))
        original_window = self.app.window
        original_bytes = self.original.path.read_bytes()
        original_backup = self.original.backup_path.read_bytes()

        def enter_password(dialog: PasswordDialog) -> int:
            self.assertFalse(self.original.is_unlocked)
            self.assertFalse(original_window.isVisible())
            self.assertFalse(original_window.auto_lock_timer.isActive())
            self.assertFalse(dialog.creating)
            dialog.password.setText(next(passwords))
            QTimer.singleShot(0, dialog.accept)
            return QDialog.exec(dialog)

        with (
            patch.object(PasswordDialog, "exec", new=enter_password),
            patch.object(QMessageBox, "warning") as warning,
        ):
            self.open_settings_and_select(str(self.target_path))

        warning.assert_called_once()
        self.assertIsNot(self.app.window, original_window)
        self.assertTrue(self.app.window.isVisible())
        self.assertEqual(self.app.vault.path, self.target_path)
        self.assertEqual(self.app.vault.model.entries[0].name, "Target test entry")
        self.assertEqual(self.original.path.read_bytes(), original_bytes)
        self.assertEqual(self.original.backup_path.read_bytes(), original_backup)
        self.assertEqual(self.new_app().vault.path, self.target_path)

    def test_canceling_unlock_reopens_the_previous_vault_with_its_password(self) -> None:
        attempts = iter((None, "original-test-password"))

        def enter_password(dialog: PasswordDialog) -> int:
            self.assertFalse(self.original.is_unlocked)
            password = next(attempts)
            if password is None:
                return QDialog.DialogCode.Rejected
            dialog.password.setText(password)
            return QDialog.DialogCode.Accepted

        with patch.object(PasswordDialog, "exec", new=enter_password):
            self.open_settings_and_select(str(self.target_path))

        self.assertIs(self.app.vault, self.original)
        self.assertTrue(self.original.is_unlocked)
        self.assertEqual(self.new_app().vault.path, self.original.path)

    def test_canceling_file_picker_leaves_the_current_vault_unlocked(self) -> None:
        window = self.app.window
        with patch.object(PasswordDialog, "exec") as prompt:
            self.open_settings_and_select("")

        prompt.assert_not_called()
        self.assertIs(self.app.window, window)
        self.assertTrue(self.original.is_unlocked)
