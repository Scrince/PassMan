from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from gui.resizable import ResizableDialog
from utils.themes import THEME_OPTIONS


class SecondsControl(QWidget):
    def __init__(
        self,
        value: int,
        minimum: int,
        maximum: int,
        accessible_name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.minimum = minimum
        self.maximum = maximum

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.value_edit = QLineEdit(str(value))
        self.value_edit.setObjectName("SecondsInput")
        self.value_edit.setAccessibleName(f"{accessible_name} in seconds")
        self.value_edit.setValidator(QIntValidator(minimum, maximum, self))
        self.value_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_edit.editingFinished.connect(self.normalize_value)

        decrease = QPushButton("-")
        decrease.setObjectName("StepperButton")
        decrease.setToolTip("Decrease seconds")
        decrease.setAccessibleName(f"Decrease {accessible_name}")
        decrease.clicked.connect(lambda: self.adjust_value(-1))

        increase = QPushButton("+")
        increase.setObjectName("StepperButton")
        increase.setToolTip("Increase seconds")
        increase.setAccessibleName(f"Increase {accessible_name}")
        increase.clicked.connect(lambda: self.adjust_value(1))

        layout.addWidget(self.value_edit, 1)
        layout.addWidget(decrease)
        layout.addWidget(increase)

    def value(self) -> int:
        return self.normalize_value()

    def normalize_value(self) -> int:
        try:
            value = int(self.value_edit.text())
        except ValueError:
            value = self.minimum
        value = max(self.minimum, min(self.maximum, value))
        self.value_edit.setText(str(value))
        return value

    def adjust_value(self, amount: int) -> None:
        self.value_edit.setText(str(max(self.minimum, min(self.maximum, self.normalize_value() + amount))))


class SettingsWindow(ResizableDialog):
    password_change_requested = pyqtSignal(str, str)
    lock_requested = pyqtSignal()
    settings_changed = pyqtSignal(bool, int, int, str)
    vault_move_requested = pyqtSignal(str)

    def __init__(
        self,
        debug_enabled: bool,
        allow_debug_tools: bool,
        auto_lock_seconds: int,
        clipboard_clear_seconds: int,
        theme_name: str,
        vault_path: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(460, 360)
        self.resize(520, 420)

        root = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setObjectName("Title")
        root.addWidget(title)

        form = QFormLayout()
        self.allow_debug_tools = allow_debug_tools
        self.debug_check = QCheckBox("Enable debug tools")
        self.debug_check.setChecked(debug_enabled)
        self.debug_check.setVisible(allow_debug_tools)
        self.auto_lock_control = SecondsControl(
            auto_lock_seconds, 0, 3600, "auto-lock timeout"
        )
        self.clipboard_control = SecondsControl(
            clipboard_clear_seconds, 0, 600, "clipboard clear timeout"
        )
        self.theme_combo = QComboBox()
        self.theme_combo.setAccessibleName("Application theme")
        self.theme_combo.addItems(THEME_OPTIONS)
        self.theme_combo.setCurrentText(theme_name if theme_name in THEME_OPTIONS else THEME_OPTIONS[0])
        if allow_debug_tools:
            form.addRow("Debug mode", self.debug_check)
        form.addRow("Auto-lock timer", self.auto_lock_control)
        form.addRow("Clipboard clear timer", self.clipboard_control)
        form.addRow("Theme", self.theme_combo)
        self.vault_path_label = QLabel(str(vault_path))
        self.vault_path_label.setWordWrap(True)
        self.vault_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.vault_path_label.setAccessibleName("Current vault file path")
        self.move_vault_button = QPushButton("Move Vault…")
        self.move_vault_button.setAccessibleName("Move the vault and backup to another folder")
        self.move_vault_button.setToolTip(
            "Copies and verifies the vault and backup before switching locations."
        )
        form.addRow("Current vault file", self.vault_path_label)
        form.addRow(self.move_vault_button)
        root.addLayout(form)

        self.old_password = QLineEdit()
        self.old_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.old_password.setPlaceholderText("Current master password")
        self.old_password.setAccessibleName("Current master password")
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setPlaceholderText("New master password")
        self.new_password.setAccessibleName("New master password")
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.setPlaceholderText("Confirm new master password")
        self.confirm_password.setAccessibleName("Confirm new master password")
        root.addWidget(self.old_password)
        root.addWidget(self.new_password)
        root.addWidget(self.confirm_password)

        row = QHBoxLayout()
        change = QPushButton("Change Password")
        change.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        change.setObjectName("PrimaryButton")
        lock = QPushButton("Lock Vault")
        lock.setAccessibleName("Lock the current vault")
        lock.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning))
        close = QPushButton("Close")
        close.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        row.addWidget(change)
        row.addWidget(lock)
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)

        change.clicked.connect(self._change_password)
        lock.clicked.connect(self._lock_and_close)
        close.clicked.connect(self._save_and_close)
        self.move_vault_button.clicked.connect(self._request_vault_move)

    def set_vault_path(self, path: Path) -> None:
        self.vault_path_label.setText(str(path))
        self.vault_path_label.setAccessibleDescription(f"Current vault file: {path}")

    def _request_vault_move(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose destination folder for vault",
            str(Path(self.vault_path_label.text()).parent),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return
        destination = Path(selected).resolve()
        current = Path(self.vault_path_label.text()).resolve().parent
        if destination == current:
            return
        answer = QMessageBox.question(
            self,
            "Move vault?",
            "PassMan will copy and verify vault.dat and vault.dat.bak at the new location, "
            "switch to that location, and then remove the original files. Continue?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.vault_move_requested.emit(str(destination))

    def closeEvent(self, event) -> None:
        self._save_and_close()
        event.accept()

    def _change_password(self) -> None:
        old = self.old_password.text()
        new = self.new_password.text()
        confirm = self.confirm_password.text()
        if not old or not new:
            QMessageBox.warning(self, "Missing password", "Both current and new passwords are required.")
            return
        if new != confirm:
            QMessageBox.warning(self, "Mismatch", "New password confirmation does not match.")
            return
        self.password_change_requested.emit(old, new)

    def _lock_and_close(self) -> None:
        self.lock_requested.emit()
        self.reject()

    def _save_and_close(self) -> None:
        self.settings_changed.emit(
            self.debug_check.isChecked() if self.allow_debug_tools else False,
            self.auto_lock_control.value(),
            self.clipboard_control.value(),
            self.theme_combo.currentText(),
        )
        self.accept()
