from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton, QStyle, QVBoxLayout, QWidget, QSizePolicy

from models.entry import Entry


SENSITIVE_FIELD_HINTS = ("password", "pass", "pin", "key", "secret", "token", "seed", "recovery")
MASK_TEXT = "\u2022" * 8
HEADER_BUTTON_WIDTH = 92
FIELD_BUTTON_WIDTH = 86
SECRET_REVEAL_MS = 15000


def _field_sort_key(item: tuple[str, object]) -> tuple[int, str]:
    name = item[0].lower()
    if name == "username" or name == "user":
        return (0, name)
    if "password" in name or name == "pass":
        return (1, name)
    return (2, name)


def _format_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.astimezone().strftime("%Y-%m-%d %I:%M %p")


def _configure_button(button: QPushButton, width: int, object_name: str = "ActionButton") -> QPushButton:
    button.setObjectName(object_name)
    button.setFixedWidth(width)
    button.setMinimumHeight(34)
    return button


class EntryCard(QFrame):
    copy_requested = pyqtSignal(str)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    notes_requested = pyqtSignal(str)

    def __init__(self, entry: Entry) -> None:
        super().__init__()
        self.entry = entry
        self._reveal_timers: dict[QLabel, QTimer] = {}
        self.setObjectName("Card")
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(entry.name)
        title.setObjectName("CardTitle")
        type_label = QLabel(entry.type)
        type_label.setObjectName("Muted")
        timestamp_label = QLabel(
            f"Created {_format_timestamp(entry.created_at)} | Modified {_format_timestamp(entry.modified_at)}"
        )
        timestamp_label.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(type_label)
        title_box.addWidget(timestamp_label)
        header.addLayout(title_box, 1)

        copy_button = _configure_button(QPushButton("Copy"), HEADER_BUTTON_WIDTH)
        copy_button.setToolTip("Copy entry data")
        edit_button = _configure_button(QPushButton("Edit"), HEADER_BUTTON_WIDTH)
        edit_button.setToolTip("Edit entry")
        delete_button = _configure_button(QPushButton("Delete"), HEADER_BUTTON_WIDTH, "DangerButton")
        delete_button.setToolTip("Delete entry")
        header.addWidget(copy_button)
        header.addWidget(edit_button)
        header.addWidget(delete_button)
        root.addLayout(header)

        fields = QWidget()
        fields.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        grid = QGridLayout(fields)
        grid.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        for column in (2, 3, 4):
            grid.setColumnMinimumWidth(column, FIELD_BUTTON_WIDTH)
        for row, (key, value) in enumerate(sorted(entry.fields.items(), key=_field_sort_key)):
            name_label = QLabel(str(key))
            name_label.setObjectName("Muted")
            value_text = str(value)
            is_sensitive = any(hint in str(key).lower() for hint in SENSITIVE_FIELD_HINTS)
            shown = MASK_TEXT if is_sensitive else value_text
            value_label = QLabel(shown)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            field_copy = _configure_button(QPushButton("Copy"), FIELD_BUTTON_WIDTH, "FieldActionButton")
            field_copy.setToolTip(f"Copy {key}")
            field_copy.clicked.connect(lambda checked=False, text=value_text: self.copy_requested.emit(text))
            grid.addWidget(name_label, row, 0)
            grid.addWidget(value_label, row, 1)
            if is_sensitive:
                notes_button = _configure_button(QPushButton("Notes"), FIELD_BUTTON_WIDTH, "FieldActionButton")
                notes_button.setToolTip(f"Edit notes for {entry.name}")
                notes_button.clicked.connect(lambda checked=False, entry_id=entry.id: self.notes_requested.emit(entry_id))
                grid.addWidget(notes_button, row, 2)
                reveal_button = _configure_button(QPushButton("Show"), FIELD_BUTTON_WIDTH, "FieldActionButton")
                reveal_button.setToolTip(f"Show or hide {key}")
                reveal_button.clicked.connect(
                    lambda checked=False, label=value_label, button=reveal_button, text=value_text: self._toggle_secret(
                        label, button, text
                    )
                )
                grid.addWidget(reveal_button, row, 3)
            grid.addWidget(field_copy, row, 4)
        root.addWidget(fields)

        copy_button.clicked.connect(self._copy_entry)
        edit_button.clicked.connect(lambda: self.edit_requested.emit(entry.id))
        delete_button.clicked.connect(lambda: self.delete_requested.emit(entry.id))

    def _copy_entry(self) -> None:
        lines = [f"{self.entry.name} ({self.entry.type})"]
        lines.extend(f"{key}: {value}" for key, value in self.entry.fields.items())
        self.copy_requested.emit("\n".join(lines))

    def _toggle_secret(self, label: QLabel, button: QPushButton, text: str) -> None:
        if button.text() == "Show":
            label.setText(text)
            button.setText("Hide")
            self._start_reveal_timer(label, button)
        else:
            self._hide_secret(label, button)

    def _start_reveal_timer(self, label: QLabel, button: QPushButton) -> None:
        timer = self._reveal_timers.get(label)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda label=label, button=button: self._hide_secret(label, button))
            self._reveal_timers[label] = timer
        timer.start(SECRET_REVEAL_MS)

    def _hide_secret(self, label: QLabel, button: QPushButton) -> None:
        timer = self._reveal_timers.get(label)
        if timer:
            timer.stop()
        label.setText(MASK_TEXT)
        button.setText("Show")
