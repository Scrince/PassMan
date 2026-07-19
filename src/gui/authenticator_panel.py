from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPropertyAnimation, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crypto.vault import Vault
from gui.project_editor import NoWheelComboBox
from gui.resizable import ResizableDialog
from models.authenticator import AuthenticatorEntry
from utils.totp import parse_import_text


class AuthenticatorEditorDialog(ResizableDialog):
    def __init__(self, parent: QWidget | None = None, entry: AuthenticatorEntry | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Authenticator" if entry else "Add Authenticator")
        self.setMinimumSize(520, 420)
        self.resize(580, 480)
        self._entry_id = entry.id if entry else None
        self._created_at = entry.created_at if entry else None

        root = QVBoxLayout(self)
        title = QLabel("Authenticator")
        title.setObjectName("Title")
        root.addWidget(title)

        form = QFormLayout()
        self.name_edit = QLineEdit(entry.name if entry else "")
        self.name_edit.setPlaceholderText("Account name")
        self.issuer_edit = QLineEdit(entry.issuer if entry else "")
        self.issuer_edit.setPlaceholderText("Issuer (e.g. GitHub)")
        self.secret_edit = QLineEdit(entry.secret if entry else "")
        self.secret_edit.setPlaceholderText("Base32 secret")
        self.secret_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.type_combo = NoWheelComboBox()
        self.type_combo.addItem("TOTP (time-based)", "totp")
        self.type_combo.addItem("HOTP (counter-based)", "hotp")
        if entry:
            idx = self.type_combo.findData(entry.type)
            self.type_combo.setCurrentIndex(idx if idx >= 0 else 0)

        self.algo_combo = NoWheelComboBox()
        for algo in ("SHA1", "SHA256", "SHA512"):
            self.algo_combo.addItem(algo, algo)
        if entry:
            idx = self.algo_combo.findData(entry.algorithm)
            self.algo_combo.setCurrentIndex(idx if idx >= 0 else 0)

        self.digits_spin = QSpinBox()
        self.digits_spin.setRange(6, 8)
        self.digits_spin.setValue(entry.digits if entry else 6)
        self.period_spin = QSpinBox()
        self.period_spin.setRange(1, 300)
        self.period_spin.setValue(entry.period if entry else 30)
        self.counter_spin = QSpinBox()
        self.counter_spin.setRange(0, 2_000_000_000)
        self.counter_spin.setValue(entry.counter if entry else 0)

        form.addRow("Name", self.name_edit)
        form.addRow("Issuer", self.issuer_edit)
        form.addRow("Secret", self.secret_edit)
        form.addRow("Type", self.type_combo)
        form.addRow("Algorithm", self.algo_combo)
        form.addRow("Digits", self.digits_spin)
        form.addRow("Period (sec)", self.period_spin)
        form.addRow("Counter", self.counter_spin)
        root.addLayout(form)

        notes_label = QLabel("Notes")
        notes_label.setObjectName("Muted")
        root.addWidget(notes_label)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(entry.notes if entry else "")
        self.notes_edit.setMaximumHeight(90)
        root.addWidget(self.notes_edit)

        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        self.type_combo.currentIndexChanged.connect(self._sync_type_fields)
        self._sync_type_fields()

    def _sync_type_fields(self) -> None:
        is_hotp = str(self.type_combo.currentData()) == "hotp"
        self.period_spin.setEnabled(not is_hotp)
        self.counter_spin.setEnabled(is_hotp)

    def accept(self) -> None:
        if not self.name_edit.text().strip() and not self.issuer_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Name or issuer is required.")
            return
        if not self.secret_edit.text().strip():
            QMessageBox.warning(self, "Missing secret", "Authenticator secret is required.")
            return
        try:
            # Validate by constructing entry and generating a code.
            entry = self.entry()
            entry.current_code()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid secret", str(exc))
            return
        super().accept()

    def entry(self) -> AuthenticatorEntry:
        name = self.name_edit.text().strip() or self.issuer_edit.text().strip() or "Authenticator"
        if self._entry_id:
            return AuthenticatorEntry(
                id=self._entry_id,
                name=name,
                issuer=self.issuer_edit.text().strip(),
                secret=self.secret_edit.text().strip(),
                type=str(self.type_combo.currentData() or "totp"),
                algorithm=str(self.algo_combo.currentData() or "SHA1"),
                digits=self.digits_spin.value(),
                period=self.period_spin.value(),
                counter=self.counter_spin.value(),
                notes=self.notes_edit.toPlainText(),
                created_at=self._created_at or "",
            )
        return AuthenticatorEntry(
            name=name,
            issuer=self.issuer_edit.text().strip(),
            secret=self.secret_edit.text().strip(),
            type=str(self.type_combo.currentData() or "totp"),
            algorithm=str(self.algo_combo.currentData() or "SHA1"),
            digits=self.digits_spin.value(),
            period=self.period_spin.value(),
            counter=self.counter_spin.value(),
            notes=self.notes_edit.toPlainText(),
        )


class ImportAuthenticatorDialog(ResizableDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Authenticator Codes")
        self.setMinimumSize(560, 420)
        self.resize(640, 500)

        root = QVBoxLayout(self)
        title = QLabel("Import Authenticator Codes")
        title.setObjectName("Title")
        root.addWidget(title)
        hint = QLabel(
            "Paste otpauth:// URIs, lines like Issuer:Account,SECRET, or bare Base32 secrets. "
            "You can also load a text file."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.text = QTextEdit()
        self.text.setPlaceholderText(
            "otpauth://totp/GitHub:you@example.com?secret=JBSWY3DPEHPK3PXP&issuer=GitHub\n"
            "Google:you@example.com,JBSWY3DPEHPK3PXP\n"
            "JBSWY3DPEHPK3PXP"
        )
        mono = QFont("Cascadia Mono")
        if not mono.exactMatch():
            mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(mono)
        root.addWidget(self.text, 1)

        row = QHBoxLayout()
        load_file = QPushButton("Load File")
        load_file.clicked.connect(self._load_file)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        import_btn = QPushButton("Import")
        import_btn.setObjectName("PrimaryButton")
        import_btn.clicked.connect(self.accept)
        row.addWidget(load_file)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(import_btn)
        root.addLayout(row)

    def _load_file(self) -> None:
        path_name, _ = QFileDialog.getOpenFileName(
            self,
            "Import authenticator file",
            "",
            "Text files (*.txt *.csv *.uri *.otp);;All files (*)",
        )
        if not path_name:
            return
        try:
            content = Path(path_name).read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Import failed", f"Could not read file:\n{exc}")
            return
        self.text.setPlainText(content)

    def accept(self) -> None:
        if not self.entries():
            QMessageBox.warning(self, "Nothing to import", "No valid authenticator codes were found.")
            return
        super().accept()

    def entries(self) -> list[AuthenticatorEntry]:
        parsed = parse_import_text(self.text.toPlainText())
        result: list[AuthenticatorEntry] = []
        for item in parsed:
            result.append(
                AuthenticatorEntry(
                    name=item.name,
                    issuer=item.issuer,
                    secret=item.secret,
                    type=item.type,
                    algorithm=item.algorithm,
                    digits=item.digits,
                    period=item.period,
                    counter=item.counter,
                )
            )
        return result


class AuthenticatorCard(QFrame):
    copy_requested = pyqtSignal(str)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    advance_requested = pyqtSignal(str)

    def __init__(self, entry: AuthenticatorEntry) -> None:
        super().__init__()
        self.entry = entry
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(entry.display_title())
        title.setObjectName("CardTitle")
        title_box.addWidget(title)
        meta = QLabel(
            f"{entry.type.upper()} · {entry.algorithm} · {entry.digits} digits"
            + (f" · {entry.period}s" if entry.type == "totp" else f" · counter {entry.counter}")
        )
        meta.setObjectName("Muted")
        title_box.addWidget(meta)
        header.addLayout(title_box, 1)

        self.code_label = QLabel("------")
        code_font = QFont("Cascadia Mono")
        if not code_font.exactMatch():
            code_font = QFont("Consolas")
        code_font.setStyleHint(QFont.StyleHint.Monospace)
        code_font.setPointSize(22)
        code_font.setBold(True)
        self.code_label.setFont(code_font)
        header.addWidget(self.code_label)

        self.timer_label = QLabel("")
        self.timer_label.setObjectName("Muted")
        self.timer_label.setMinimumWidth(48)
        header.addWidget(self.timer_label)
        root.addLayout(header)

        actions = QHBoxLayout()
        copy_btn = _action_button("Copy Code", "Copy current code")
        edit_btn = _action_button("Edit", "Edit authenticator")
        delete_btn = _action_button("Delete", "Delete authenticator", danger=True)
        actions.addWidget(copy_btn)
        if entry.type == "hotp":
            next_btn = _action_button("Next", "Advance HOTP counter")
            next_btn.clicked.connect(lambda: self.advance_requested.emit(entry.id))
            actions.addWidget(next_btn)
        actions.addStretch(1)
        actions.addWidget(edit_btn)
        actions.addWidget(delete_btn)
        root.addLayout(actions)

        copy_btn.clicked.connect(self._copy_code)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(entry.id))
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(entry.id))
        self.refresh_code()

    def refresh_code(self) -> None:
        try:
            code = self.entry.current_code()
            self.code_label.setText(code)
            if self.entry.type == "totp":
                remaining = self.entry.seconds_remaining()
                self.timer_label.setText(f"{remaining}s")
            else:
                self.timer_label.setText("HOTP")
        except Exception:
            self.code_label.setText("Error")
            self.timer_label.setText("")

    def _copy_code(self) -> None:
        try:
            self.copy_requested.emit(self.entry.current_code())
        except Exception as exc:
            QMessageBox.warning(self, "Copy failed", str(exc))


class AuthenticatorPanel(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, vault: Vault, copy_callback, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault = vault
        self.copy_callback = copy_callback
        self._cards: list[AuthenticatorCard] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        heading = QLabel("Authenticator")
        heading.setObjectName("Title")
        root.addWidget(heading)
        subtitle = QLabel(
            "Store TOTP/HOTP authenticator secrets and generate one-time codes. "
            "This area is separate from passwords and project keys."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name, issuer, type, or notes")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Name A-Z", "name")
        self.sort_combo.addItem("Recently Modified", "modified_desc")
        self.sort_combo.addItem("Issuer A-Z", "issuer")
        add = QPushButton("Add")
        add.setObjectName("PrimaryButton")
        add.clicked.connect(self.add_entry)
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self.import_entries)
        top.addWidget(self.search, 1)
        top.addWidget(self.sort_combo)
        top.addWidget(import_btn)
        top.addWidget(add)
        root.addLayout(top)

        self.count_label = QLabel()
        self.count_label.setObjectName("Muted")
        root.addWidget(self.count_label)

        self.list_widget = QWidget()
        self.list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(12)
        self.list_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.list_widget)
        root.addWidget(scroll, 1)

        self.search.textChanged.connect(self.refresh)
        self.sort_combo.currentIndexChanged.connect(self.refresh)

        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._refresh_codes)
        self._tick.start()

        self.refresh()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._tick.isActive():
            self._tick.start()
        self._refresh_codes()

    def hideEvent(self, event) -> None:  # type: ignore[override]
        self._tick.stop()
        super().hideEvent(event)

    def _filtered(self) -> list[AuthenticatorEntry]:
        query = self.search.text()
        matching = [item for item in self.vault.model.authenticator_entries if item.matches(query)]
        mode = self.sort_combo.currentData()
        if mode == "modified_desc":
            return sorted(matching, key=lambda item: item.modified_at, reverse=True)
        if mode == "issuer":
            return sorted(matching, key=lambda item: (item.issuer.lower(), item.name.lower()))
        return sorted(matching, key=lambda item: item.display_title().lower())

    def refresh(self) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._cards.clear()
        entries = self._filtered()
        self.count_label.setText(f"{len(entries)} authenticators")
        for entry in entries:
            card = AuthenticatorCard(entry)
            card.copy_requested.connect(self._copy_text)
            card.edit_requested.connect(self.edit_entry)
            card.delete_requested.connect(self.delete_entry)
            card.advance_requested.connect(self.advance_hotp)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
            self._cards.append(card)
            animation = QPropertyAnimation(card, b"windowOpacity", self)
            animation.setDuration(120)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _refresh_codes(self) -> None:
        for card in self._cards:
            card.refresh_code()

    def add_entry(self) -> None:
        dialog = AuthenticatorEditorDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entry = dialog.entry()
        entry.mark_modified()
        self.vault.model.authenticator_entries.append(entry)
        if not self._persist():
            self.vault.model.authenticator_entries = [
                item for item in self.vault.model.authenticator_entries if item.id != entry.id
            ]
            return
        self.refresh()
        self.status_message.emit(f"Saved {entry.display_title()}")

    def import_entries(self) -> None:
        dialog = ImportAuthenticatorDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        imported = dialog.entries()
        existing_secrets = {item.secret for item in self.vault.model.authenticator_entries}
        previous = list(self.vault.model.authenticator_entries)
        added = 0
        for entry in imported:
            if entry.secret in existing_secrets:
                continue
            entry.mark_modified()
            self.vault.model.authenticator_entries.append(entry)
            existing_secrets.add(entry.secret)
            added += 1
        if added:
            if not self._persist():
                self.vault.model.authenticator_entries = previous
                return
            self.refresh()
        self.status_message.emit(f"Imported {added} authenticator(s)")
        if added == 0:
            QMessageBox.information(self, "Import", "No new authenticators were added (duplicates skipped).")

    def edit_entry(self, entry_id: str) -> None:
        entry = self._by_id(entry_id)
        if not entry:
            return
        dialog = AuthenticatorEditorDialog(self, entry=entry)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.entry()
        previous = (
            entry.name,
            entry.issuer,
            entry.secret,
            entry.type,
            entry.algorithm,
            entry.digits,
            entry.period,
            entry.counter,
            entry.notes,
            entry.modified_at,
        )
        entry.name = updated.name
        entry.issuer = updated.issuer
        entry.secret = updated.secret
        entry.type = updated.type
        entry.algorithm = updated.algorithm
        entry.digits = updated.digits
        entry.period = updated.period
        entry.counter = updated.counter
        entry.notes = updated.notes
        entry.mark_modified()
        if not self._persist():
            (
                entry.name,
                entry.issuer,
                entry.secret,
                entry.type,
                entry.algorithm,
                entry.digits,
                entry.period,
                entry.counter,
                entry.notes,
                entry.modified_at,
            ) = previous
            return
        self.refresh()
        self.status_message.emit(f"Updated {entry.display_title()}")

    def delete_entry(self, entry_id: str) -> None:
        entry = self._by_id(entry_id)
        if not entry:
            return
        answer = QMessageBox.question(
            self,
            "Delete authenticator",
            f"Delete “{entry.display_title()}”?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        previous = list(self.vault.model.authenticator_entries)
        self.vault.model.authenticator_entries = [
            item for item in self.vault.model.authenticator_entries if item.id != entry_id
        ]
        if not self._persist():
            self.vault.model.authenticator_entries = previous
            return
        self.refresh()
        self.status_message.emit("Authenticator deleted")

    def advance_hotp(self, entry_id: str) -> None:
        entry = self._by_id(entry_id)
        if not entry or entry.type != "hotp":
            return
        previous_counter = entry.counter
        previous_modified = entry.modified_at
        entry.counter += 1
        entry.mark_modified()
        if not self._persist():
            entry.counter = previous_counter
            entry.modified_at = previous_modified
            return
        self.refresh()
        self.status_message.emit(f"Counter advanced to {entry.counter}")

    def _by_id(self, entry_id: str) -> AuthenticatorEntry | None:
        return next((item for item in self.vault.model.authenticator_entries if item.id == entry_id), None)

    def _copy_text(self, text: str) -> None:
        self.copy_callback(text)
        self.status_message.emit("Code copied to clipboard")

    def _persist(self) -> bool:
        try:
            self.vault.save()
            return True
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", f"Could not write the vault:\n{exc}")
            return False


def _action_button(label: str, tooltip: str, danger: bool = False) -> QPushButton:
    button = QPushButton(label)
    button.setObjectName("DangerButton" if danger else "ActionButton")
    button.setFixedWidth(100)
    button.setMinimumHeight(34)
    button.setToolTip(tooltip)
    return button
