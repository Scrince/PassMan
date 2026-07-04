from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QStyle, QVBoxLayout, QWidget

from utils.themes import THEME_OPTIONS


class SecondsControl(QWidget):
    def __init__(self, value: int, minimum: int, maximum: int, parent=None) -> None:
        super().__init__(parent)
        self.minimum = minimum
        self.maximum = maximum

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.value_edit = QLineEdit(str(value))
        self.value_edit.setObjectName("SecondsInput")
        self.value_edit.setValidator(QIntValidator(minimum, maximum, self))
        self.value_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_edit.editingFinished.connect(self.normalize_value)

        decrease = QPushButton("-")
        decrease.setObjectName("StepperButton")
        decrease.setToolTip("Decrease seconds")
        decrease.clicked.connect(lambda: self.adjust_value(-1))

        increase = QPushButton("+")
        increase.setObjectName("StepperButton")
        increase.setToolTip("Increase seconds")
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


class SettingsWindow(QDialog):
    password_change_requested = pyqtSignal(str, str)
    lock_requested = pyqtSignal()
    settings_changed = pyqtSignal(bool, int, int, str)

    def __init__(
        self,
        debug_enabled: bool,
        allow_debug_tools: bool,
        auto_lock_seconds: int,
        clipboard_clear_seconds: int,
        theme_name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setObjectName("Title")
        root.addWidget(title)

        form = QFormLayout()
        self.allow_debug_tools = allow_debug_tools
        self.debug_check = QCheckBox("Enable debug tools")
        self.debug_check.setChecked(debug_enabled)
        self.debug_check.setVisible(allow_debug_tools)
        self.auto_lock_control = SecondsControl(auto_lock_seconds, 0, 3600)
        self.clipboard_control = SecondsControl(clipboard_clear_seconds, 0, 600)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEME_OPTIONS)
        self.theme_combo.setCurrentText(theme_name if theme_name in THEME_OPTIONS else THEME_OPTIONS[0])
        if allow_debug_tools:
            form.addRow("Debug mode", self.debug_check)
        form.addRow("Auto-lock timer", self.auto_lock_control)
        form.addRow("Clipboard clear timer", self.clipboard_control)
        form.addRow("Theme", self.theme_combo)
        root.addLayout(form)

        self.old_password = QLineEdit()
        self.old_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.old_password.setPlaceholderText("Current master password")
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setPlaceholderText("New master password")
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.setPlaceholderText("Confirm new master password")
        root.addWidget(self.old_password)
        root.addWidget(self.new_password)
        root.addWidget(self.confirm_password)

        row = QHBoxLayout()
        change = QPushButton("Change Password")
        change.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        change.setObjectName("PrimaryButton")
        lock = QPushButton("Lock Vault")
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

    def closeEvent(self, event) -> None:  # noqa: N802
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
