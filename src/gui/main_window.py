from __future__ import annotations

import json
import math
import secrets
import shutil
import string
import sys
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from PyQt6.QtCore import QEvent, QPropertyAnimation, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QIntValidator, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crypto.vault import InvalidPasswordError, Vault, VaultError, VaultFormatError
from gui.add_entry_window import AddEntryWindow
from gui.settings_window import SettingsWindow
from gui.widgets.entry_card import EntryCard
from models.entry import Entry
from utils.clipboard import ClipboardManager
from utils.file_paths import asset_path
from utils.themes import DEFAULT_THEME_NAME, theme_stylesheet
from version import APP_DISPLAY_NAME, APP_NAME


APP_ICON_PATH = asset_path("passman_icon.png")


class DeveloperWindow(QDialog):
    def __init__(self, vault: Vault, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Developer Vault JSON")
        self.setMinimumSize(700, 520)
        root = QVBoxLayout(self)
        title = QLabel("Decrypted JSON")
        title.setObjectName("Title")
        root.addWidget(title)
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(json.dumps(vault.model.to_json_dict(), indent=2, sort_keys=True))
        root.addWidget(viewer)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)


class NotesWindow(QDialog):
    def __init__(self, entry: Entry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Notes - {entry.name}")
        self.setMinimumSize(520, 360)
        root = QVBoxLayout(self)

        title = QLabel(entry.name)
        title.setObjectName("Title")
        root.addWidget(title)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Recovery keys, backup codes, or other notes")
        self.notes_edit.setPlainText(entry.notes)
        root.addWidget(self.notes_edit, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def notes(self) -> str:
        return self.notes_edit.toPlainText()


class PasswordGeneratorWindow(QDialog):
    def __init__(self, copy_callback: Callable[[str], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.copy_callback = copy_callback
        self.setWindowTitle("Password Generator")
        self.setMinimumSize(560, 430)

        root = QVBoxLayout(self)
        root.setSpacing(14)

        title = QLabel("Password Generator")
        title.setObjectName("Title")
        root.addWidget(title)

        output_panel = QFrame()
        output_panel.setObjectName("GeneratorPanel")
        output_layout = QVBoxLayout(output_panel)
        output_layout.setSpacing(10)

        self.password_output = QLineEdit()
        self.password_output.setReadOnly(True)
        self.password_output.setObjectName("GeneratedPassword")
        self.password_output.setPlaceholderText("Click Generate to create a password")
        output_layout.addWidget(self.password_output)

        meter_row = QHBoxLayout()
        self.strength_meter = QProgressBar()
        self.strength_meter.setRange(0, 100)
        self.strength_meter.setTextVisible(False)
        self.strength_label = QLabel()
        self.strength_label.setObjectName("StrengthLabel")
        self.strength_label.setText("Not generated")
        meter_row.addWidget(self.strength_meter, 1)
        meter_row.addWidget(self.strength_label)
        output_layout.addLayout(meter_row)
        root.addWidget(output_panel)

        controls = QFrame()
        controls.setObjectName("GeneratorPanel")
        control_grid = QGridLayout(controls)
        control_grid.setHorizontalSpacing(14)
        control_grid.setVerticalSpacing(12)

        length_label = QLabel("Length")
        length_label.setObjectName("Muted")
        length_controls = QHBoxLayout()
        length_controls.setSpacing(8)
        self.length_edit = QLineEdit("20")
        self.length_edit.setObjectName("LengthInput")
        self.length_edit.setValidator(QIntValidator(8, 128, self))
        self.length_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.length_edit.editingFinished.connect(self.normalize_length)
        decrease = QPushButton("-")
        decrease.setObjectName("StepperButton")
        decrease.setToolTip("Decrease length")
        decrease.clicked.connect(lambda: self.adjust_length(-1))
        increase = QPushButton("+")
        increase.setObjectName("StepperButton")
        increase.setToolTip("Increase length")
        increase.clicked.connect(lambda: self.adjust_length(1))
        length_controls.addWidget(self.length_edit)
        length_controls.addWidget(decrease)
        length_controls.addWidget(increase)
        control_grid.addWidget(length_label, 0, 0)
        control_grid.addLayout(length_controls, 0, 1)

        self.uppercase_check = QCheckBox("Capital letters")
        self.uppercase_check.setChecked(True)
        self.lowercase_check = QCheckBox("Lowercase letters")
        self.lowercase_check.setChecked(True)
        self.numbers_check = QCheckBox("Numbers")
        self.numbers_check.setChecked(True)
        self.symbols_check = QCheckBox("Symbols")
        self.symbols_check.setChecked(True)

        for index, checkbox in enumerate(
            [self.uppercase_check, self.lowercase_check, self.numbers_check, self.symbols_check],
            start=1,
        ):
            control_grid.addWidget(checkbox, index, 0, 1, 2)

        root.addWidget(controls)

        button_row = QHBoxLayout()
        regenerate = QPushButton("Generate")
        regenerate.setObjectName("PrimaryButton")
        regenerate.clicked.connect(self.generate_password)
        self.copy_button = QPushButton("Copy")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_password)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        button_row.addWidget(regenerate)
        button_row.addStretch(1)
        button_row.addWidget(self.copy_button)
        button_row.addWidget(close)
        root.addLayout(button_row)

    def _selected_sets(self) -> list[str]:
        sets = []
        if self.uppercase_check.isChecked():
            sets.append(string.ascii_uppercase)
        if self.lowercase_check.isChecked():
            sets.append(string.ascii_lowercase)
        if self.numbers_check.isChecked():
            sets.append(string.digits)
        if self.symbols_check.isChecked():
            sets.append("!@#$%^&*()-_=+[]{};:,.?/")
        return sets

    def generate_password(self) -> None:
        selected_sets = self._selected_sets()
        if not selected_sets:
            self.lowercase_check.setChecked(True)
            selected_sets = self._selected_sets()

        length = self.normalize_length()
        pool = "".join(selected_sets)
        password_chars = [secrets.choice(charset) for charset in selected_sets]
        password_chars.extend(secrets.choice(pool) for _ in range(length - len(password_chars)))
        secrets.SystemRandom().shuffle(password_chars)
        password = "".join(password_chars)
        self.password_output.setText(password)
        self.copy_button.setEnabled(True)
        self.update_strength(len(pool), length)

    def normalize_length(self) -> int:
        try:
            length = int(self.length_edit.text())
        except ValueError:
            length = 20
        length = max(8, min(128, length))
        self.length_edit.setText(str(length))
        return length

    def adjust_length(self, amount: int) -> None:
        length = max(8, min(128, self.normalize_length() + amount))
        self.length_edit.setText(str(length))

    def update_strength(self, pool_size: int, length: int) -> None:
        entropy = length * math.log2(pool_size)
        score = max(0, min(100, int((entropy / 120) * 100)))
        if entropy >= 100:
            label = "Excellent"
            color = "#38d996"
        elif entropy >= 75:
            label = "Strong"
            color = "#7bdc65"
        elif entropy >= 50:
            label = "Moderate"
            color = "#f0b84f"
        else:
            label = "Weak"
            color = "#e66b6b"
        self.strength_meter.setValue(score)
        self.strength_meter.setStyleSheet(
            f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}"
        )
        self.strength_label.setText(f"{label} ({int(entropy)} bits)")

    def copy_password(self) -> None:
        password = self.password_output.text()
        if password:
            self.copy_callback(password)


class BackupWindow(QDialog):
    def __init__(self, vault: Vault, restored_callback: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault = vault
        self.restored_callback = restored_callback
        self.setWindowTitle("Backup Manager")
        self.setMinimumSize(520, 300)

        root = QVBoxLayout(self)
        root.setSpacing(14)

        title = QLabel("Backup Manager")
        title.setObjectName("Title")
        root.addWidget(title)

        panel = QFrame()
        panel.setObjectName("GeneratorPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(10)

        current_vault = QLabel(f"Current vault: {self.vault.path}")
        current_vault.setObjectName("Muted")
        current_vault.setWordWrap(True)
        panel_layout.addWidget(current_vault)

        guidance = QLabel(
            "Create Backup saves an encrypted vault.dat wherever you choose. "
            "Restore Backup lets you pick a vault.dat from another folder or drive."
        )
        guidance.setObjectName("Muted")
        guidance.setWordWrap(True)
        panel_layout.addWidget(guidance)
        root.addWidget(panel)

        button_row = QHBoxLayout()
        create = QPushButton("Create Backup")
        create.setObjectName("PrimaryButton")
        create.clicked.connect(self.create_backup)
        restore = QPushButton("Restore Backup")
        restore.clicked.connect(self.restore_backup)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        button_row.addWidget(create)
        button_row.addStretch(1)
        button_row.addWidget(restore)
        button_row.addWidget(close)
        root.addLayout(button_row)

    def create_backup(self) -> None:
        if not self.vault.path.exists():
            QMessageBox.warning(self, "Backup unavailable", "No vault file exists to back up.")
            return
        backup_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save encrypted backup",
            str(self.vault.path.parent / "vault.dat"),
            "Vault files (*.dat);;All files (*)",
        )
        if not backup_name:
            return
        backup_path = Path(backup_name)
        if backup_path.suffix.lower() != ".dat":
            backup_path = backup_path.with_suffix(".dat")
        if backup_path.resolve() == self.vault.path.resolve():
            QMessageBox.warning(self, "Choose another location", "Choose a different folder or drive for the backup.")
            return
        shutil.copy2(self.vault.path, backup_path)
        QMessageBox.information(self, "Backup created", f"Encrypted backup saved to:\n{backup_path}")

    def restore_backup(self) -> None:
        backup_name, _ = QFileDialog.getOpenFileName(
            self,
            "Choose encrypted backup",
            str(self.vault.path.parent),
            "Vault files (*.dat);;All files (*)",
        )
        if not backup_name:
            return
        backup_path = Path(backup_name)
        if backup_path.resolve() == self.vault.path.resolve():
            QMessageBox.warning(self, "Choose another file", "Choose a backup vault.dat from another folder or drive.")
            return
        answer = QMessageBox.question(
            self,
            "Restore backup?",
            f"Restore this encrypted backup?\n\n{backup_path}\n\n"
            "Your current vault will be saved as vault.dat.bak before restoring.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.vault.restore_from_file(backup_path)
        except (InvalidPasswordError, VaultError) as exc:
            QMessageBox.warning(self, "Restore failed", str(exc))
            return
        self.restored_callback()
        QMessageBox.information(self, "Backup restored", "Backup restored successfully.")


class MainWindow(QMainWindow):
    lock_requested = pyqtSignal()
    theme_changed = pyqtSignal(str)

    def __init__(self, vault: Vault, app: QApplication, theme_name: str = DEFAULT_THEME_NAME) -> None:
        super().__init__()
        self.vault = vault
        self.app = app
        self.clipboard = ClipboardManager(app)
        self.allow_debug_tools = not getattr(sys, "frozen", False)
        settings = self.vault.model.settings
        self.debug_enabled = settings.debug_enabled if self.allow_debug_tools else False
        self.auto_lock_seconds = settings.auto_lock_seconds
        self.clipboard_clear_seconds = settings.clipboard_clear_seconds
        self.theme_name = settings.theme_name or theme_name
        self.app.setStyleSheet(theme_stylesheet(self.theme_name))
        self.setWindowTitle(APP_DISPLAY_NAME)
        if APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.resize(1120, 740)

        self.auto_lock_timer = QTimer(self)
        self.auto_lock_timer.setSingleShot(True)
        self.auto_lock_timer.timeout.connect(self.lock_requested.emit)
        app.installEventFilter(self)

        root = QWidget()
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(190)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 18, 14, 18)
        if APP_ICON_PATH.exists():
            logo = QLabel()
            logo.setPixmap(
                QPixmap(str(APP_ICON_PATH)).scaled(
                    64,
                    64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            logo.setAlignment(Qt.AlignmentFlag.AlignLeft)
            side_layout.addWidget(logo)
        brand = QLabel(APP_NAME)
        brand.setObjectName("Title")
        side_layout.addWidget(brand)

        subtitle = QLabel("Secure Vault")
        subtitle.setTextFormat(Qt.TextFormat.PlainText)
        subtitle.setObjectName("Muted")
        side_layout.addWidget(subtitle)

        generator = QPushButton("Password Generator")
        generator.setObjectName("SidebarButton")
        generator.clicked.connect(self.open_password_generator)
        side_layout.addWidget(generator)
        backup = QPushButton("Backup")
        backup.setObjectName("SidebarButton")
        backup.clicked.connect(self.open_backup_manager)
        side_layout.addWidget(backup)
        side_layout.addStretch(1)

        self.debug_panel: QWidget | None = None
        if self.allow_debug_tools:
            self.debug_panel = QWidget()
            debug_layout = QVBoxLayout(self.debug_panel)
            debug_layout.setContentsMargins(0, 0, 0, 0)
            for label, handler in [
                ("Developer JSON", self.show_developer_window),
                ("Add Samples", self.add_sample_entries),
                ("Test Crypto", self.test_encryption),
                ("Test Password", self.test_password_change),
                ("Test Search", self.test_search),
            ]:
                button = QPushButton(label)
                button.clicked.connect(handler)
                debug_layout.addWidget(button)
            self.debug_panel.hide()
            side_layout.addWidget(self.debug_panel)

        settings = QPushButton("Settings")
        settings.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        settings.clicked.connect(self.open_settings)
        lock = QPushButton("Lock")
        lock.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning))
        lock.clicked.connect(self.lock_requested.emit)
        side_layout.addWidget(settings)
        side_layout.addWidget(lock)
        shell.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(22, 18, 22, 18)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name, type, field name, or value")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Name A-Z", "name")
        self.sort_combo.addItem("Recently Modified", "modified_desc")
        self.sort_combo.addItem("Oldest Modified", "modified_asc")
        self.sort_combo.addItem("Newest Created", "created_desc")
        self.sort_combo.addItem("Oldest Created", "created_asc")
        add = QPushButton("Add Entry")
        add.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        add.setObjectName("PrimaryButton")
        add.clicked.connect(self.add_entry)
        top.addWidget(self.search, 1)
        top.addWidget(self.sort_combo)
        top.addWidget(add)
        content_layout.addLayout(top)

        self.count_label = QLabel()
        self.count_label.setObjectName("Muted")
        content_layout.addWidget(self.count_label)

        self.list_widget = QWidget()
        self.list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(12)
        self.list_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.list_widget)
        content_layout.addWidget(scroll, 1)
        shell.addWidget(content, 1)

        self.search.textChanged.connect(self.refresh_entries)
        self.sort_combo.currentIndexChanged.connect(self.refresh_entries)
        self.refresh_entries()
        self.reset_auto_lock_timer()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() in {
            QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress,
            QEvent.Type.Wheel,
        }:
            self.reset_auto_lock_timer()
        return super().eventFilter(obj, event)

    def reset_auto_lock_timer(self) -> None:
        self.auto_lock_timer.stop()
        if self.auto_lock_seconds > 0:
            self.auto_lock_timer.start(self.auto_lock_seconds * 1000)

    def _filtered_entries(self) -> list[Entry]:
        entries = self.vault.model.entries
        query = self.search.text()
        matching_entries = [entry for entry in entries if entry.matches(query)]
        sort_mode = self.sort_combo.currentData()
        if sort_mode == "modified_desc":
            return sorted(matching_entries, key=lambda entry: entry.modified_at, reverse=True)
        if sort_mode == "modified_asc":
            return sorted(matching_entries, key=lambda entry: entry.modified_at)
        if sort_mode == "created_desc":
            return sorted(matching_entries, key=lambda entry: entry.created_at, reverse=True)
        if sort_mode == "created_asc":
            return sorted(matching_entries, key=lambda entry: entry.created_at)
        return sorted(matching_entries, key=lambda entry: (entry.name.lower(), entry.type.lower()))

    def refresh_entries(self) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        entries = self._filtered_entries()
        self.count_label.setText(f"{len(entries)} entries")
        for entry in entries:
            card = EntryCard(entry)
            card.copy_requested.connect(self.copy_text)
            card.edit_requested.connect(self.edit_entry)
            card.delete_requested.connect(self.delete_entry)
            card.notes_requested.connect(self.edit_notes)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
            animation = QPropertyAnimation(card, b"windowOpacity", self)
            animation.setDuration(120)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def add_entry(self) -> None:
        dialog = AddEntryWindow(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.vault.model.entries.append(dialog.entry())
            self.vault.save()
            self.refresh_entries()

    def edit_entry(self, entry_id: str) -> None:
        entry = self._entry_by_id(entry_id)
        if not entry:
            return
        dialog = AddEntryWindow(self, entry=entry)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.entry()
            entry.name = updated.name
            entry.type = updated.type
            entry.fields = updated.fields
            entry.notes = updated.notes
            entry.mark_modified()
            self.vault.save()
            self.refresh_entries()

    def edit_notes(self, entry_id: str) -> None:
        entry = self._entry_by_id(entry_id)
        if not entry:
            return
        dialog = NotesWindow(entry, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            entry.notes = dialog.notes()
            entry.mark_modified()
            self.vault.save()
            self.refresh_entries()

    def delete_entry(self, entry_id: str) -> None:
        entry = self._entry_by_id(entry_id)
        if not entry:
            return
        answer = QMessageBox.question(self, "Delete entry", f"Delete {entry.name}?")
        if answer == QMessageBox.StandardButton.Yes:
            self.vault.model.entries = [item for item in self.vault.model.entries if item.id != entry_id]
            self.vault.save()
            self.refresh_entries()

    def _entry_by_id(self, entry_id: str) -> Entry | None:
        return next((entry for entry in self.vault.model.entries if entry.id == entry_id), None)

    def copy_text(self, text: str) -> None:
        self.clipboard.copy(text, self.clipboard_clear_seconds)
        self.statusBar().showMessage("Copied to clipboard", 2500)

    def open_settings(self) -> None:
        dialog = SettingsWindow(
            self.debug_enabled,
            self.allow_debug_tools,
            self.auto_lock_seconds,
            self.clipboard_clear_seconds,
            self.theme_name,
            self,
        )
        dialog.password_change_requested.connect(self.change_password)
        dialog.lock_requested.connect(self.lock_requested.emit)
        dialog.settings_changed.connect(self.update_settings)
        dialog.exec()

    def open_password_generator(self) -> None:
        PasswordGeneratorWindow(self.copy_text, self).exec()

    def open_backup_manager(self) -> None:
        BackupWindow(self.vault, self.reload_from_vault_settings, self).exec()

    def update_settings(self, debug: bool, auto_lock: int, clipboard_clear: int, theme_name: str) -> None:
        self.debug_enabled = debug if self.allow_debug_tools else False
        self.auto_lock_seconds = auto_lock
        self.clipboard_clear_seconds = clipboard_clear
        self.theme_name = theme_name
        self.vault.model.settings.debug_enabled = self.debug_enabled
        self.vault.model.settings.auto_lock_seconds = self.auto_lock_seconds
        self.vault.model.settings.clipboard_clear_seconds = self.clipboard_clear_seconds
        self.vault.model.settings.theme_name = self.theme_name
        self.vault.save()
        self.app.setStyleSheet(theme_stylesheet(theme_name))
        self.theme_changed.emit(theme_name)
        if self.debug_panel:
            self.debug_panel.setVisible(self.debug_enabled)
        self.reset_auto_lock_timer()

    def reload_from_vault_settings(self) -> None:
        settings = self.vault.model.settings
        self.debug_enabled = settings.debug_enabled if self.allow_debug_tools else False
        self.auto_lock_seconds = settings.auto_lock_seconds
        self.clipboard_clear_seconds = settings.clipboard_clear_seconds
        self.theme_name = settings.theme_name
        self.app.setStyleSheet(theme_stylesheet(self.theme_name))
        self.theme_changed.emit(self.theme_name)
        if self.debug_panel:
            self.debug_panel.setVisible(self.debug_enabled)
        self.reset_auto_lock_timer()
        self.refresh_entries()

    def change_password(self, old_password: str, new_password: str) -> None:
        try:
            self.vault.change_password(old_password, new_password)
        except InvalidPasswordError:
            QMessageBox.warning(self, "Password unchanged", "Current master password is incorrect.")
            return
        except VaultFormatError:
            QMessageBox.warning(self, "Password unchanged", "Vault file is malformed or corrupted.")
            return
        except VaultError as exc:
            QMessageBox.warning(self, "Password unchanged", str(exc))
            return
        except OSError as exc:
            QMessageBox.warning(self, "Password unchanged", f"Could not write the updated vault:\n{exc}")
            return
        QMessageBox.information(self, "Password changed", "Master password changed successfully.")

    def show_developer_window(self) -> None:
        if not self.allow_debug_tools or not self.debug_enabled:
            return
        DeveloperWindow(self.vault, self).exec()

    def add_sample_entries(self) -> None:
        samples = [
            Entry("Example Mail", "Website", {"username": "alex@example.com", "password": "sample-password"}),
            Entry("Hardware Wallet", "Wallet", {"pin": "123456"}),
            Entry("Backup Drive", "Drive", {"key": "drive-recovery-key"}),
        ]
        self.vault.model.entries.extend(samples)
        self.vault.save()
        self.refresh_entries()

    def test_encryption(self) -> None:
        try:
            with TemporaryDirectory() as tmp:
                test = Vault(Path(tmp) / "vault.dat")
                test.create("test-pass")
                test.model.entries.append(Entry("Crypto Test", "Custom", {"secret": "ok"}))
                test.save()
                test.unlock("test-pass")
                assert test.model.entries[0].fields["secret"] == "ok"
        except Exception as exc:  # pragma: no cover - debug utility
            QMessageBox.critical(self, "Crypto test failed", str(exc))
            return
        QMessageBox.information(self, "Crypto test", "Encryption/decryption test passed.")

    def test_password_change(self) -> None:
        try:
            with TemporaryDirectory() as tmp:
                test = Vault(Path(tmp) / "vault.dat")
                test.create("old-pass")
                test.model.entries.append(Entry("Password Test", "Custom", {"field": "value"}))
                test.save()
                test.change_password("old-pass", "new-pass")
                test.unlock("new-pass")
                assert test.model.entries[0].name == "Password Test"
        except Exception as exc:  # pragma: no cover - debug utility
            QMessageBox.critical(self, "Password test failed", str(exc))
            return
        QMessageBox.information(self, "Password test", "Password change test passed.")

    def test_search(self) -> None:
        if not self.vault.model.entries:
            self.add_sample_entries()
        self.search.setText("wallet")
        QMessageBox.information(self, "Search test", "Search has been set to 'wallet'.")
