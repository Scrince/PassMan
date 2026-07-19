from __future__ import annotations

from PyQt6.QtCore import QPropertyAnimation, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crypto.vault import Vault
from gui.resizable import ResizableDialog
from models.recovery import RecoveryEntry


class RecoveryEditorDialog(ResizableDialog):
    def __init__(self, parent: QWidget | None = None, entry: RecoveryEntry | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Recovery Codes" if entry else "Add Recovery Codes")
        self.setMinimumSize(560, 480)
        self.resize(640, 560)
        self._entry_id = entry.id if entry else None
        self._created_at = entry.created_at if entry else None

        root = QVBoxLayout(self)
        title = QLabel("Recovery")
        title.setObjectName("Title")
        root.addWidget(title)
        hint = QLabel(
            "Store recovery keys, backup codes, or word lists for services like GitHub, "
            "BitLocker, Microsoft Account, or similar locked-account recovery material."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QFormLayout()
        self.name_edit = QLineEdit(entry.name if entry else "")
        self.name_edit.setPlaceholderText("Label (e.g. Personal account backup codes)")
        self.service_edit = QLineEdit(entry.service if entry else "")
        self.service_edit.setPlaceholderText("Service (e.g. GitHub, BitLocker)")
        form.addRow("Name", self.name_edit)
        form.addRow("Service", self.service_edit)
        root.addLayout(form)

        codes_label = QLabel("Codes / Phrase")
        codes_label.setObjectName("Muted")
        root.addWidget(codes_label)
        self.codes_edit = QTextEdit()
        self.codes_edit.setPlaceholderText(
            "Paste recovery codes or a word list, one per line or as provided by the service:\n\n"
            "1a2b-3c4d\n"
            "5e6f-7g8h\n"
            "...\n\n"
            "or a single recovery key / phrase"
        )
        self.codes_edit.setPlainText(entry.codes if entry else "")
        mono = QFont("Cascadia Mono")
        if not mono.exactMatch():
            mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        self.codes_edit.setFont(mono)
        root.addWidget(self.codes_edit, 1)

        notes_label = QLabel("Notes")
        notes_label.setObjectName("Muted")
        root.addWidget(notes_label)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(entry.notes if entry else "")
        self.notes_edit.setMaximumHeight(90)
        self.notes_edit.setPlaceholderText("Optional notes (when issued, device name, etc.)")
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

    def accept(self) -> None:
        if not self.name_edit.text().strip() and not self.service_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Name or service is required.")
            return
        if not self.codes_edit.toPlainText().strip():
            QMessageBox.warning(self, "Missing codes", "Enter at least one recovery code or phrase.")
            return
        super().accept()

    def entry(self) -> RecoveryEntry:
        name = self.name_edit.text().strip() or self.service_edit.text().strip() or "Recovery codes"
        if self._entry_id:
            return RecoveryEntry(
                id=self._entry_id,
                name=name,
                service=self.service_edit.text().strip(),
                codes=self.codes_edit.toPlainText().strip(),
                notes=self.notes_edit.toPlainText(),
                created_at=self._created_at or "",
            )
        return RecoveryEntry(
            name=name,
            service=self.service_edit.text().strip(),
            codes=self.codes_edit.toPlainText().strip(),
            notes=self.notes_edit.toPlainText(),
        )


class RecoveryCard(QFrame):
    copy_requested = pyqtSignal(str)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    view_requested = pyqtSignal(str)

    def __init__(self, entry: RecoveryEntry) -> None:
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
        line_count = entry.code_line_count()
        meta = QLabel(
            f"{line_count} code line{'s' if line_count != 1 else ''}"
            + (f" · {entry.service}" if entry.service and entry.service not in entry.display_title() else "")
        )
        meta.setObjectName("Muted")
        title_box.addWidget(meta)
        header.addLayout(title_box, 1)
        root.addLayout(header)

        if entry.notes.strip():
            notes_preview = entry.notes.strip().splitlines()[0]
            if len(notes_preview) > 100:
                notes_preview = notes_preview[:97] + "..."
            notes_label = QLabel(notes_preview)
            notes_label.setObjectName("Muted")
            notes_label.setWordWrap(True)
            root.addWidget(notes_label)

        actions = QHBoxLayout()
        view_btn = _action_button("View", "View and copy recovery codes")
        copy_btn = _action_button("Copy All", "Copy all recovery codes")
        edit_btn = _action_button("Edit", "Edit recovery entry")
        delete_btn = _action_button("Delete", "Delete recovery entry", danger=True)
        actions.addWidget(view_btn)
        actions.addWidget(copy_btn)
        actions.addStretch(1)
        actions.addWidget(edit_btn)
        actions.addWidget(delete_btn)
        root.addLayout(actions)

        view_btn.clicked.connect(lambda: self.view_requested.emit(entry.id))
        copy_btn.clicked.connect(lambda: self.copy_requested.emit(entry.codes))
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(entry.id))
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(entry.id))


class RecoveryViewDialog(ResizableDialog):
    def __init__(
        self,
        entry: RecoveryEntry,
        copy_callback,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._copy_callback = copy_callback
        self._codes = entry.codes
        self.setWindowTitle(f"Recovery — {entry.display_title()}")
        self.setMinimumSize(560, 420)
        self.resize(680, 520)

        root = QVBoxLayout(self)
        heading = QLabel(entry.display_title())
        heading.setObjectName("Title")
        root.addWidget(heading)
        if entry.service:
            service = QLabel(f"Service: {entry.service}")
            service.setObjectName("Muted")
            root.addWidget(service)

        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(entry.codes)
        mono = QFont("Cascadia Mono")
        if not mono.exactMatch():
            mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        viewer.setFont(mono)
        root.addWidget(viewer, 1)

        if entry.notes.strip():
            notes_label = QLabel("Notes")
            notes_label.setObjectName("Muted")
            root.addWidget(notes_label)
            notes = QTextEdit()
            notes.setReadOnly(True)
            notes.setPlainText(entry.notes)
            notes.setMaximumHeight(100)
            root.addWidget(notes)

        buttons = QHBoxLayout()
        copy_all = QPushButton("Copy All")
        copy_all.setObjectName("PrimaryButton")
        copy_all.clicked.connect(self._copy_all)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(copy_all)
        buttons.addStretch(1)
        buttons.addWidget(close)
        root.addLayout(buttons)

    def _copy_all(self) -> None:
        if self._codes:
            self._copy_callback(self._codes)


class RecoveryPanel(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, vault: Vault, copy_callback, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault = vault
        self.copy_callback = copy_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        heading = QLabel("Recovery")
        heading.setObjectName("Title")
        root.addWidget(heading)
        subtitle = QLabel(
            "Store recovery keys, backup codes, and word lists for services like GitHub, "
            "BitLocker, and other locked-account recovery material. Separate from passwords and seeds."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name, service, codes, or notes")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Name A-Z", "name")
        self.sort_combo.addItem("Recently Modified", "modified_desc")
        self.sort_combo.addItem("Service A-Z", "service")
        add = QPushButton("Add")
        add.setObjectName("PrimaryButton")
        add.clicked.connect(self.add_entry)
        top.addWidget(self.search, 1)
        top.addWidget(self.sort_combo)
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
        self.refresh()

    def _filtered(self) -> list[RecoveryEntry]:
        query = self.search.text()
        matching = [item for item in self.vault.model.recovery_entries if item.matches(query)]
        mode = self.sort_combo.currentData()
        if mode == "modified_desc":
            return sorted(matching, key=lambda item: item.modified_at, reverse=True)
        if mode == "service":
            return sorted(matching, key=lambda item: (item.service.lower(), item.name.lower()))
        return sorted(matching, key=lambda item: item.display_title().lower())

    def refresh(self) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        entries = self._filtered()
        self.count_label.setText(f"{len(entries)} recovery entr{'y' if len(entries) == 1 else 'ies'}")
        for entry in entries:
            card = RecoveryCard(entry)
            card.copy_requested.connect(self._copy_text)
            card.edit_requested.connect(self.edit_entry)
            card.delete_requested.connect(self.delete_entry)
            card.view_requested.connect(self.view_entry)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
            animation = QPropertyAnimation(card, b"windowOpacity", self)
            animation.setDuration(120)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def add_entry(self) -> None:
        dialog = RecoveryEditorDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entry = dialog.entry()
        entry.mark_modified()
        self.vault.model.recovery_entries.append(entry)
        if not self._persist():
            self.vault.model.recovery_entries = [
                item for item in self.vault.model.recovery_entries if item.id != entry.id
            ]
            return
        self.refresh()
        self.status_message.emit(f"Saved {entry.display_title()}")

    def edit_entry(self, entry_id: str) -> None:
        entry = self._by_id(entry_id)
        if not entry:
            return
        dialog = RecoveryEditorDialog(self, entry=entry)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.entry()
        previous = (entry.name, entry.service, entry.codes, entry.notes, entry.modified_at)
        entry.name = updated.name
        entry.service = updated.service
        entry.codes = updated.codes
        entry.notes = updated.notes
        entry.mark_modified()
        if not self._persist():
            entry.name, entry.service, entry.codes, entry.notes, entry.modified_at = previous
            return
        self.refresh()
        self.status_message.emit(f"Updated {entry.display_title()}")

    def delete_entry(self, entry_id: str) -> None:
        entry = self._by_id(entry_id)
        if not entry:
            return
        answer = QMessageBox.question(
            self,
            "Delete recovery entry",
            f"Delete “{entry.display_title()}”?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        previous = list(self.vault.model.recovery_entries)
        self.vault.model.recovery_entries = [
            item for item in self.vault.model.recovery_entries if item.id != entry_id
        ]
        if not self._persist():
            self.vault.model.recovery_entries = previous
            return
        self.refresh()
        self.status_message.emit("Recovery entry deleted")

    def view_entry(self, entry_id: str) -> None:
        entry = self._by_id(entry_id)
        if not entry:
            return
        dialog = RecoveryViewDialog(entry, self._copy_text, self)
        dialog.exec()

    def _by_id(self, entry_id: str) -> RecoveryEntry | None:
        return next((item for item in self.vault.model.recovery_entries if item.id == entry_id), None)

    def _copy_text(self, text: str) -> None:
        self.copy_callback(text)
        self.status_message.emit("Copied to clipboard")

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
