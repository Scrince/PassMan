from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QStyle, QVBoxLayout, QWidget

from gui.widgets.field_editor import FieldEditor
from models.entry import Entry


SENSITIVE_FIELD_HINTS = ("password", "pass", "pin", "key", "secret", "token", "seed", "recovery")


def _field_type_for_name(name: str) -> str:
    lowered = name.lower()
    if any(hint in lowered for hint in SENSITIVE_FIELD_HINTS):
        return "password"
    return "text"


class AddEntryWindow(QDialog):
    def __init__(self, parent: QWidget | None = None, entry: Entry | None = None, category: str = "Website") -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Entry" if entry else "Add Entry")
        self.setMinimumSize(560, 420)
        self._field_rows: list[FieldEditor] = []
        self._entry_id = entry.id if entry else None
        self._created_at = entry.created_at if entry else None
        self._notes = entry.notes if entry else ""

        root = QVBoxLayout(self)
        title = QLabel("Entry")
        title.setObjectName("Title")
        root.addWidget(title)

        self.name_edit = QLineEdit(entry.name if entry else "")
        self.name_edit.setPlaceholderText("Name")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Website", "Wallet", "Drive", "Custom"])
        self.type_combo.setCurrentText(entry.type if entry else category)
        root.addWidget(self.name_edit)
        root.addWidget(self.type_combo)

        self.fields_widget = QWidget()
        self.fields_layout = QVBoxLayout(self.fields_widget)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.fields_widget)
        root.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        add_field = QPushButton("Add Field")
        add_field.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        save = QPushButton("Save")
        save.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        save.setObjectName("PrimaryButton")
        cancel = QPushButton("Cancel")
        cancel.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        button_row.addWidget(add_field)
        button_row.addStretch(1)
        button_row.addWidget(cancel)
        button_row.addWidget(save)
        root.addLayout(button_row)

        if entry:
            for key, value in entry.fields.items():
                field_name = str(key)
                self.add_field(field_name, str(value), _field_type_for_name(field_name))
        else:
            self._add_defaults(category)

        add_field.clicked.connect(lambda: self.add_field())
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

    def _add_defaults(self, category: str) -> None:
        defaults = {
            "Website": [("Username", "", "text"), ("Password", "", "password")],
            "Wallet": [("Pin", "", "password")],
            "Drive": [("Key", "", "password")],
            "Custom": [],
        }
        for name, value, field_type in defaults.get(category, []):
            self.add_field(name, value, field_type)

    def add_field(self, name: str = "", value: str = "", field_type: str = "text") -> None:
        editor = FieldEditor(name, value, field_type)
        editor.remove_button.clicked.connect(lambda: self.remove_field(editor))
        self._field_rows.append(editor)
        self.fields_layout.addWidget(editor)

    def remove_field(self, editor: FieldEditor) -> None:
        self._field_rows.remove(editor)
        editor.setParent(None)
        editor.deleteLater()

    def accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Entry name is required.")
            return
        names = [row.value()[0] for row in self._field_rows if row.value()[0]]
        if len(names) != len(set(names)):
            QMessageBox.warning(self, "Duplicate fields", "Field names must be unique.")
            return
        super().accept()

    def entry(self) -> Entry:
        fields = {}
        for row in self._field_rows:
            name, value = row.value()
            if name:
                fields[name] = value
        if self._entry_id:
            return Entry(
                id=self._entry_id,
                name=self.name_edit.text().strip(),
                type=self.type_combo.currentText(),
                fields=fields,
                notes=self._notes,
                created_at=self._created_at or "",
            )
        return Entry(
            name=self.name_edit.text().strip(),
            type=self.type_combo.currentText(),
            fields=fields,
            notes=self._notes,
        )
