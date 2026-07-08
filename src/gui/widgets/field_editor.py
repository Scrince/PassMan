from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QStyle, QWidget


FIELD_TYPES = [("Text", "text"), ("Password", "password"), ("Notes", "notes")]


class FieldEditor(QWidget):
    def __init__(self, name: str = "", value: str = "", field_type: str = "text") -> None:
        super().__init__()
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("Field name")
        self.type_combo = QComboBox()
        for label, value_data in FIELD_TYPES:
            self.type_combo.addItem(label, value_data)
        self._set_field_type(field_type)
        self.value_edit = QLineEdit(value)
        self.value_edit.setPlaceholderText("Value")
        self.remove_button = QPushButton("Remove")
        self.remove_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.remove_button.setToolTip("Remove field")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.name_edit, 2)
        layout.addWidget(self.type_combo, 1)
        layout.addWidget(self.value_edit, 3)
        layout.addWidget(self.remove_button)
        self.type_combo.currentIndexChanged.connect(self._update_echo)
        self._update_echo()

    def _set_field_type(self, field_type: str) -> None:
        index = self.type_combo.findData(field_type.lower())
        self.type_combo.setCurrentIndex(index if index >= 0 else 0)

    def _update_echo(self) -> None:
        if self.field_type() == "password":
            self.value_edit.setEchoMode(QLineEdit.EchoMode.Password)
            return
        self.value_edit.setEchoMode(QLineEdit.EchoMode.Normal)

    def value(self) -> tuple[str, str, str]:
        return self.name_edit.text().strip(), self.value_edit.text(), self.field_type()

    def field_type(self) -> str:
        return str(self.type_combo.currentData())
