from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
)

from crypto.vault import InvalidPasswordError, Vault, VaultError, VaultFormatError
from gui.main_window import MainWindow
from utils.file_paths import VAULT_FILENAME, asset_path, vault_path
from utils.themes import DEFAULT_THEME_NAME, theme_stylesheet
from version import APP_DISPLAY_NAME, APP_NAME, APP_VERSION


APP_ICON_PATH = asset_path("passman_icon.png")


class PasswordDialog(QDialog):
    def __init__(self, creating: bool) -> None:
        super().__init__()
        self.creating = creating
        action = "Create Vault" if creating else "Unlock Vault"
        self.setWindowTitle(f"{action} - {APP_DISPLAY_NAME}")
        if APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.setMinimumWidth(390)
        root = QVBoxLayout(self)
        icon_label = QLabel()
        icon_label.setPixmap(
            QPixmap(str(APP_ICON_PATH)).scaled(
                72,
                72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        root.addWidget(icon_label)
        title = QLabel("Create Master Password" if creating else "Enter Master Password")
        title.setObjectName("Title")
        root.addWidget(title)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Master Password")
        root.addWidget(self.password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.setPlaceholderText("Confirm Master Password")
        self.confirm.setVisible(creating)
        root.addWidget(self.confirm)
        button = QPushButton("Create Vault" if creating else "Unlock")
        button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        button.setObjectName("PrimaryButton")
        root.addWidget(button)
        button.clicked.connect(self.accept)
        self.password.returnPressed.connect(self.accept)
        self.confirm.returnPressed.connect(self.accept)

    def accept(self) -> None:
        if not self.password.text():
            QMessageBox.warning(self, "Password Required", "Master Password is required.")
            return
        if self.creating and self.password.text() != self.confirm.text():
            QMessageBox.warning(self, "Mismatch", "Password confirmation does not match.")
            return
        super().accept()


class PassManApp:
    def __init__(self) -> None:
        self.qt = QApplication(sys.argv)
        self.qt.setApplicationName(APP_NAME)
        self.qt.setApplicationVersion(APP_VERSION)
        self.theme_name = DEFAULT_THEME_NAME
        self.qt.setStyleSheet(theme_stylesheet(self.theme_name))
        if APP_ICON_PATH.exists():
            self.qt.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.vault = Vault(vault_path())
        self.window: MainWindow | None = None

    def run(self) -> int:
        if not self.choose_existing_vault_if_needed():
            return 0
        if not self.unlock_or_create():
            return 0
        return self.qt.exec()

    def choose_existing_vault_if_needed(self) -> bool:
        if self.vault.exists():
            return True

        answer = QMessageBox.question(
            None,
            "No vault found",
            "No vault.dat was found in the application vault folder.\n\n"
            "Do you want to load an existing vault.dat or vault.dat.bak from another location?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return True

        selected, _ = QFileDialog.getOpenFileName(
            None,
            "Choose existing vault",
            str(vault_path().parent),
            "PassMan vaults (vault.dat vault.dat.bak);;Vault files (*.dat *.bak);;All files (*)",
        )
        if not selected:
            return True

        selected_path = Path(selected)
        if selected_path.name == f"{VAULT_FILENAME}.bak":
            self.vault = Vault(selected_path.with_name(VAULT_FILENAME), load_path=selected_path)
        else:
            self.vault = Vault(selected_path)
        return True

    def unlock_or_create(self) -> bool:
        creating = not self.vault.exists()
        while True:
            dialog = PasswordDialog(creating)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            password = dialog.password.text()
            try:
                if creating:
                    self.vault.create(password)
                else:
                    self.vault.unlock(password)
            except InvalidPasswordError:
                if not creating and self.offer_backup_restore(password):
                    self.apply_vault_theme()
                    self.show_main_window()
                    return True
                QMessageBox.warning(None, "Unlock failed", "Incorrect password or corrupted vault.")
                continue
            except VaultFormatError:
                if not creating and self.offer_backup_restore(password):
                    self.apply_vault_theme()
                    self.show_main_window()
                    return True
                QMessageBox.warning(None, "Unlock failed", "Vault is corrupted and no usable backup was found.")
                continue
            self.apply_vault_theme()
            self.show_main_window()
            return True

    def offer_backup_restore(self, password: str) -> bool:
        if not self.vault.backup_exists():
            return False
        backup_vault = Vault(self.vault.backup_path)
        try:
            backup_vault.unlock(password)
        except VaultError:
            return False
        answer = QMessageBox.question(
            None,
            "Restore backup?",
            "The main vault could not be opened, but vault.dat.bak unlocked successfully.\n\n"
            "Restore the encrypted backup now?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        self.vault.restore_backup()
        self.vault.unlock(password)
        return True

    def show_main_window(self) -> None:
        self.window = MainWindow(self.vault, self.qt, self.theme_name)
        self.window.lock_requested.connect(self.lock)
        self.window.theme_changed.connect(self.update_theme)
        self.window.show()

    def update_theme(self, theme_name: str) -> None:
        self.theme_name = theme_name

    def apply_vault_theme(self) -> None:
        self.theme_name = self.vault.model.settings.theme_name
        self.qt.setStyleSheet(theme_stylesheet(self.theme_name))

    def lock(self) -> None:
        if self.window:
            self.window.close()
            self.window = None
        self.vault.lock()
        if not self.unlock_or_create():
            self.qt.quit()


def main() -> int:
    return PassManApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
