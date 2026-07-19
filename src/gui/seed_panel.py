from __future__ import annotations

from PyQt6.QtCore import QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
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
from gui.project_editor import NoWheelComboBox
from gui.resizable import ResizableDialog, center_widget_on_screen
from models.seed import ALLOWED_WORD_COUNTS, SeedEntry, normalize_seed_phrase, seed_word_list

GRID_COLUMNS = 3

# Dialog sizes grow for 24-word seeds so the numbered grid is not cramped.
EDITOR_SIZE_12 = (720, 660)
EDITOR_SIZE_24 = (820, 960)
EDITOR_MIN_12 = (640, 560)
EDITOR_MIN_24 = (760, 860)
VIEW_SIZE_12 = (720, 560)
VIEW_SIZE_24 = (820, 820)
VIEW_MIN_12 = (620, 480)
VIEW_MIN_24 = (760, 720)
FIELD_MIN_WIDTH = 130
FIELD_MIN_HEIGHT = 32


def _mono_font(point_size: int = 10) -> QFont:
    mono = QFont("Cascadia Mono")
    if not mono.exactMatch():
        mono = QFont("Consolas")
    mono.setStyleHint(QFont.StyleHint.Monospace)
    mono.setPointSize(point_size)
    return mono


def _dialog_sizes(word_count: int, *, editor: bool) -> tuple[tuple[int, int], tuple[int, int]]:
    is_24 = int(word_count) >= 24
    if editor:
        return (EDITOR_SIZE_24 if is_24 else EDITOR_SIZE_12, EDITOR_MIN_24 if is_24 else EDITOR_MIN_12)
    return (VIEW_SIZE_24 if is_24 else VIEW_SIZE_12, VIEW_MIN_24 if is_24 else VIEW_MIN_12)


class SeedWordGrid(QWidget):
    """Numbered BIP39-style word grid with password-bullet hide/show."""

    words_changed = pyqtSignal()

    def __init__(
        self,
        word_count: int = 12,
        words: list[str] | None = None,
        *,
        read_only: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._word_count = 12
        self._read_only = read_only
        self._revealed = False
        self._fields: list[QLineEdit] = []
        self._index_labels: list[QLabel] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(8)
        self._grid_host = QWidget()
        self._grid_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(10)
        self._root.addWidget(self._grid_host)
        self.rebuild(word_count, words or [])

    @property
    def word_count(self) -> int:
        return self._word_count

    @property
    def revealed(self) -> bool:
        return self._revealed

    def rebuild(self, word_count: int, words: list[str] | None = None) -> None:
        current = list(words) if words is not None else self.words()
        try:
            count = int(word_count)
        except (TypeError, ValueError):
            count = 12
        if count not in ALLOWED_WORD_COUNTS:
            count = 12
        self._word_count = count

        # Extra room between rows when showing a full 24-word grid.
        if count >= 24:
            self._grid.setHorizontalSpacing(16)
            self._grid.setVerticalSpacing(12)
        else:
            self._grid.setHorizontalSpacing(14)
            self._grid.setVerticalSpacing(10)

        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._fields.clear()
        self._index_labels.clear()

        for index in range(count):
            row = index // GRID_COLUMNS
            col = index % GRID_COLUMNS
            cell = QHBoxLayout()
            cell.setSpacing(6)
            cell.setContentsMargins(0, 2, 0, 2)
            number = QLabel(f"{index + 1}.")
            number.setObjectName("Muted")
            number.setMinimumWidth(32)
            number.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            field = QLineEdit()
            field.setFont(_mono_font(10))
            field.setPlaceholderText(f"word {index + 1}")
            field.setMinimumWidth(FIELD_MIN_WIDTH)
            field.setMinimumHeight(FIELD_MIN_HEIGHT)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if index < len(current):
                field.setText(current[index])
            field.setReadOnly(self._read_only)
            field.setEchoMode(
                QLineEdit.EchoMode.Normal if self._revealed else QLineEdit.EchoMode.Password
            )
            if not self._read_only:
                field.textChanged.connect(self._on_field_changed)
                field.editingFinished.connect(lambda f=field: self._normalize_field(f))
            cell_host = QWidget()
            cell_host.setLayout(cell)
            cell_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cell.addWidget(number)
            cell.addWidget(field, 1)
            self._grid.addWidget(cell_host, row, col)
            self._fields.append(field)
            self._index_labels.append(number)

        # Keep columns equal width so boxes stay evenly spaced.
        for col in range(GRID_COLUMNS):
            self._grid.setColumnStretch(col, 1)

        # Preferred height scales with row count so dialogs can size to fit.
        rows = max(1, (count + GRID_COLUMNS - 1) // GRID_COLUMNS)
        row_pitch = FIELD_MIN_HEIGHT + (14 if count >= 24 else 12)
        self.setMinimumHeight(rows * row_pitch)
        self._apply_echo_mode()

    def set_revealed(self, revealed: bool) -> None:
        self._revealed = bool(revealed)
        self._apply_echo_mode()

    def toggle_revealed(self) -> bool:
        self.set_revealed(not self._revealed)
        return self._revealed

    def _apply_echo_mode(self) -> None:
        mode = QLineEdit.EchoMode.Normal if self._revealed else QLineEdit.EchoMode.Password
        for field in self._fields:
            field.setEchoMode(mode)

    def words(self) -> list[str]:
        result: list[str] = []
        for field in self._fields:
            token = field.text().strip()
            if token:
                result.append(token)
        return result

    def phrase(self) -> str:
        return normalize_seed_phrase(" ".join(self.words()))

    def set_phrase(self, text: str) -> None:
        words = seed_word_list(text)
        for index, field in enumerate(self._fields):
            field.blockSignals(True)
            field.setText(words[index] if index < len(words) else "")
            field.blockSignals(False)
        self.words_changed.emit()

    def filled_count(self) -> int:
        return sum(1 for field in self._fields if field.text().strip())

    def _normalize_field(self, field: QLineEdit) -> None:
        text = field.text().strip()
        # If the user pastes multiple words into one box, distribute across the grid.
        parts = seed_word_list(text)
        if len(parts) > 1:
            # Full 12/24-word paste replaces the entire grid so no stale slots remain.
            if len(parts) in ALLOWED_WORD_COUNTS:
                self.set_phrase(" ".join(parts))
                return
            try:
                start = self._fields.index(field)
            except ValueError:
                start = 0
            last_written = start - 1
            for offset, word in enumerate(parts):
                target = start + offset
                if target >= len(self._fields):
                    break
                self._fields[target].blockSignals(True)
                self._fields[target].setText(word)
                self._fields[target].blockSignals(False)
                last_written = target
            # Clear any following slots so previous words cannot leak into the phrase.
            for target in range(last_written + 1, len(self._fields)):
                self._fields[target].blockSignals(True)
                self._fields[target].setText("")
                self._fields[target].blockSignals(False)
            self.words_changed.emit()
            return
        if text != field.text():
            field.blockSignals(True)
            field.setText(text)
            field.blockSignals(False)

    def _on_field_changed(self, _text: str = "") -> None:
        self.words_changed.emit()


class SeedEditorDialog(ResizableDialog):
    def __init__(self, parent: QWidget | None = None, entry: SeedEntry | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Seed Phrase" if entry else "Add Seed Phrase")
        self._entry_id = entry.id if entry else None
        self._created_at = entry.created_at if entry else None
        initial_count = entry.word_count if entry else 12

        root = QVBoxLayout(self)
        root.setSpacing(10)
        title = QLabel("Seed")
        title.setObjectName("Title")
        root.addWidget(title)
        hint = QLabel(
            "Store 12- or 24-word cryptocurrency wallet seed phrases, an optional BIP39-style "
            "passphrase, and related notes. Words are hidden by default."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QFormLayout()
        self.name_edit = QLineEdit(entry.name if entry else "")
        self.name_edit.setPlaceholderText("Label (e.g. Hardware wallet cold storage)")
        self.wallet_edit = QLineEdit(entry.wallet if entry else "")
        self.wallet_edit.setPlaceholderText("Wallet / chain (e.g. Bitcoin, Ethereum, Ledger)")

        self.word_count_combo = NoWheelComboBox()
        for count in ALLOWED_WORD_COUNTS:
            self.word_count_combo.addItem(f"{count} words", count)
        if entry:
            idx = self.word_count_combo.findData(entry.word_count)
            self.word_count_combo.setCurrentIndex(idx if idx >= 0 else 0)

        form.addRow("Name", self.name_edit)
        form.addRow("Wallet", self.wallet_edit)
        form.addRow("Word count", self.word_count_combo)
        root.addLayout(form)

        seed_header = QHBoxLayout()
        seed_label = QLabel("Seed phrase")
        seed_label.setObjectName("Muted")
        seed_header.addWidget(seed_label)
        seed_header.addStretch(1)
        self.show_seed_btn = QPushButton("Show seed")
        self.show_seed_btn.setCheckable(True)
        self.show_seed_btn.toggled.connect(self._toggle_seed_visibility)
        seed_header.addWidget(self.show_seed_btn)
        root.addLayout(seed_header)

        initial_words = seed_word_list(entry.seed_phrase) if entry else []
        self.word_grid = SeedWordGrid(
            initial_count,
            initial_words,
            read_only=False,
        )
        root.addWidget(self.word_grid, 1)

        paste_row = QHBoxLayout()
        self.paste_edit = QLineEdit()
        self.paste_edit.setPlaceholderText("Or paste full 12/24-word phrase here, then Apply")
        self.paste_edit.setEchoMode(QLineEdit.EchoMode.Password)
        apply_paste = QPushButton("Apply paste")
        apply_paste.clicked.connect(self._apply_paste)
        paste_row.addWidget(self.paste_edit, 1)
        paste_row.addWidget(apply_paste)
        root.addLayout(paste_row)

        self.word_count_hint = QLabel()
        self.word_count_hint.setObjectName("Muted")
        root.addWidget(self.word_count_hint)
        self.word_grid.words_changed.connect(self._update_word_count_hint)
        self.word_count_combo.currentIndexChanged.connect(self._on_word_count_changed)
        self._update_word_count_hint()

        passphrase_label = QLabel("Passphrase (optional)")
        passphrase_label.setObjectName("Muted")
        root.addWidget(passphrase_label)
        self.passphrase_edit = QLineEdit(entry.passphrase if entry else "")
        self.passphrase_edit.setPlaceholderText("BIP39 / wallet passphrase if used")
        self.passphrase_edit.setEchoMode(QLineEdit.EchoMode.Password)
        root.addWidget(self.passphrase_edit)

        show_row = QHBoxLayout()
        self.show_passphrase = QPushButton("Show passphrase")
        self.show_passphrase.setCheckable(True)
        self.show_passphrase.toggled.connect(self._toggle_passphrase_visibility)
        show_row.addWidget(self.show_passphrase)
        show_row.addStretch(1)
        root.addLayout(show_row)

        notes_label = QLabel("Notes")
        notes_label.setObjectName("Muted")
        root.addWidget(notes_label)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(entry.notes if entry else "")
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Optional notes (derivation path, account index, etc.)")
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

        self._fit_window_for_word_count(initial_count)

    def _fit_window_for_word_count(self, word_count: int) -> None:
        """Grow (or shrink) the dialog so 24-word grids are not bunched."""
        target, minimum = _dialog_sizes(word_count, editor=True)
        self.setMinimumSize(*minimum)
        # Always expand up to the target for more words; never shrink below current if larger.
        width = max(self.width() if self.isVisible() else 0, target[0])
        height = max(self.height() if self.isVisible() else 0, target[1])
        # When switching back to 12 words, allow a comfortable default rather than staying huge.
        if int(word_count) < 24:
            width, height = target
        else:
            width, height = max(width, target[0]), max(height, target[1])
        self.resize(width, height)
        if self.isVisible():
            center_widget_on_screen(self)

    def _expected_count(self) -> int:
        data = self.word_count_combo.currentData()
        try:
            return int(data)
        except (TypeError, ValueError):
            return 12

    def _on_word_count_changed(self) -> None:
        count = self._expected_count()
        self.word_grid.rebuild(count, self.word_grid.words())
        self._fit_window_for_word_count(count)
        self._update_word_count_hint()

    def _update_word_count_hint(self) -> None:
        expected = self._expected_count()
        actual = self.word_grid.filled_count()
        if actual == 0:
            self.word_count_hint.setText(f"Enter exactly {expected} words in the numbered grid.")
        elif actual == expected:
            self.word_count_hint.setText(f"{actual} words — matches {expected}-word seed.")
        else:
            self.word_count_hint.setText(f"{actual} words filled — expected {expected}.")

    def _toggle_seed_visibility(self, checked: bool) -> None:
        self.word_grid.set_revealed(checked)
        self.paste_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.show_seed_btn.setText("Hide seed" if checked else "Show seed")

    def _toggle_passphrase_visibility(self, checked: bool) -> None:
        self.passphrase_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.show_passphrase.setText("Hide passphrase" if checked else "Show passphrase")

    def _apply_paste(self) -> None:
        text = self.paste_edit.text().strip()
        if not text:
            QMessageBox.information(self, "Nothing to paste", "Paste a full seed phrase first.")
            return
        words = seed_word_list(text)
        expected = self._expected_count()
        if len(words) not in ALLOWED_WORD_COUNTS and len(words) != expected:
            # Still apply, but warn if count is wrong.
            pass
        if len(words) in ALLOWED_WORD_COUNTS and len(words) != expected:
            idx = self.word_count_combo.findData(len(words))
            if idx >= 0:
                self.word_count_combo.blockSignals(True)
                self.word_count_combo.setCurrentIndex(idx)
                self.word_count_combo.blockSignals(False)
                self.word_grid.rebuild(len(words), words)
                self._fit_window_for_word_count(len(words))
                self._update_word_count_hint()
                self.paste_edit.clear()
                return
        self.word_grid.set_phrase(text)
        self.paste_edit.clear()
        self._update_word_count_hint()

    def accept(self) -> None:
        if not self.name_edit.text().strip() and not self.wallet_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Name or wallet is required.")
            return
        phrase = self.word_grid.phrase()
        if not phrase:
            QMessageBox.warning(self, "Missing seed", "Seed phrase is required.")
            return
        expected = self._expected_count()
        actual = len(seed_word_list(phrase))
        if actual != expected:
            QMessageBox.warning(
                self,
                "Word count mismatch",
                f"Expected {expected} words but found {actual}. "
                f"Fill every numbered slot or change the word count.",
            )
            return
        super().accept()

    def entry(self) -> SeedEntry:
        name = self.name_edit.text().strip() or self.wallet_edit.text().strip() or "Wallet seed"
        if self._entry_id:
            return SeedEntry(
                id=self._entry_id,
                name=name,
                wallet=self.wallet_edit.text().strip(),
                word_count=self._expected_count(),
                seed_phrase=self.word_grid.phrase(),
                passphrase=self.passphrase_edit.text(),
                notes=self.notes_edit.toPlainText(),
                created_at=self._created_at or "",
            )
        return SeedEntry(
            name=name,
            wallet=self.wallet_edit.text().strip(),
            word_count=self._expected_count(),
            seed_phrase=self.word_grid.phrase(),
            passphrase=self.passphrase_edit.text(),
            notes=self.notes_edit.toPlainText(),
        )


class SeedCard(QFrame):
    copy_seed_requested = pyqtSignal(str)
    copy_passphrase_requested = pyqtSignal(str)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    view_requested = pyqtSignal(str)

    def __init__(self, entry: SeedEntry) -> None:
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
        bits = [f"{entry.word_count}-word seed", "hidden"]
        if entry.passphrase:
            bits.append("passphrase set")
        meta = QLabel(" · ".join(bits))
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
        view_btn = _action_button("View", "View numbered seed grid")
        copy_seed = _action_button("Copy Seed", "Copy full 12/24-word seed phrase")
        edit_btn = _action_button("Edit", "Edit seed entry")
        delete_btn = _action_button("Delete", "Delete seed entry", danger=True)
        actions.addWidget(view_btn)
        actions.addWidget(copy_seed)
        if entry.passphrase:
            copy_pp = _action_button("Copy PP", "Copy passphrase")
            copy_pp.clicked.connect(lambda: self.copy_passphrase_requested.emit(entry.passphrase))
            actions.addWidget(copy_pp)
        actions.addStretch(1)
        actions.addWidget(edit_btn)
        actions.addWidget(delete_btn)
        root.addLayout(actions)

        view_btn.clicked.connect(lambda: self.view_requested.emit(entry.id))
        # Always copy the full normalized space-separated seed phrase.
        copy_seed.clicked.connect(
            lambda: self.copy_seed_requested.emit(normalize_seed_phrase(entry.seed_phrase))
        )
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(entry.id))
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(entry.id))


class SeedViewDialog(ResizableDialog):
    def __init__(
        self,
        entry: SeedEntry,
        copy_seed_callback,
        copy_passphrase_callback=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._copy_seed_callback = copy_seed_callback
        self._copy_passphrase_callback = copy_passphrase_callback
        self._seed = normalize_seed_phrase(entry.seed_phrase)
        self._passphrase = entry.passphrase
        self.setWindowTitle(f"Seed — {entry.display_title()}")
        target, minimum = _dialog_sizes(entry.word_count, editor=False)
        self.setMinimumSize(*minimum)
        self.resize(*target)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        heading = QLabel(entry.display_title())
        heading.setObjectName("Title")
        root.addWidget(heading)
        meta = QLabel(
            f"{entry.word_count}-word seed"
            + (f" · {entry.wallet}" if entry.wallet else "")
            + (" · passphrase set" if entry.passphrase else "")
        )
        meta.setObjectName("Muted")
        root.addWidget(meta)

        seed_header = QHBoxLayout()
        seed_label = QLabel("Seed phrase")
        seed_label.setObjectName("Muted")
        seed_header.addWidget(seed_label)
        seed_header.addStretch(1)
        self.show_seed_btn = QPushButton("Show seed")
        self.show_seed_btn.setCheckable(True)
        self.show_seed_btn.toggled.connect(self._toggle_seed_visibility)
        seed_header.addWidget(self.show_seed_btn)
        root.addLayout(seed_header)

        self.word_grid = SeedWordGrid(
            entry.word_count,
            seed_word_list(entry.seed_phrase),
            read_only=True,
        )
        root.addWidget(self.word_grid, 1)

        if entry.passphrase:
            pp_label = QLabel("Passphrase")
            pp_label.setObjectName("Muted")
            root.addWidget(pp_label)
            self.pp_edit = QLineEdit(entry.passphrase)
            self.pp_edit.setReadOnly(True)
            self.pp_edit.setEchoMode(QLineEdit.EchoMode.Password)
            root.addWidget(self.pp_edit)
            show_pp = QPushButton("Show passphrase")
            show_pp.setCheckable(True)

            def _toggle(checked: bool) -> None:
                self.pp_edit.setEchoMode(
                    QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
                )
                show_pp.setText("Hide passphrase" if checked else "Show passphrase")

            show_pp.toggled.connect(_toggle)
            root.addWidget(show_pp)

        if entry.notes.strip():
            notes_label = QLabel("Notes")
            notes_label.setObjectName("Muted")
            root.addWidget(notes_label)
            notes = QTextEdit()
            notes.setReadOnly(True)
            notes.setPlainText(entry.notes)
            root.addWidget(notes, 1)
        else:
            root.addStretch(1)

        buttons = QHBoxLayout()
        copy_seed = QPushButton("Copy Seed")
        copy_seed.setObjectName("PrimaryButton")
        copy_seed.setToolTip("Copy the full space-separated seed phrase")
        copy_seed.clicked.connect(self._copy_full_seed)
        buttons.addWidget(copy_seed)
        if entry.passphrase:
            copy_pp = QPushButton("Copy Passphrase")
            copy_pp.clicked.connect(self._copy_passphrase)
            buttons.addWidget(copy_pp)
        buttons.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)

        QShortcut(QKeySequence.StandardKey.Copy, self, activated=self._copy_full_seed)

    def _toggle_seed_visibility(self, checked: bool) -> None:
        self.word_grid.set_revealed(checked)
        self.show_seed_btn.setText("Hide seed" if checked else "Show seed")

    def _copy_full_seed(self) -> None:
        if self._seed:
            self._copy_seed_callback(self._seed)

    def _copy_passphrase(self) -> None:
        if self._passphrase and self._copy_passphrase_callback:
            self._copy_passphrase_callback(self._passphrase)


class SeedPanel(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, vault: Vault, copy_callback, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault = vault
        self.copy_callback = copy_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        heading = QLabel("Seed")
        heading.setObjectName("Title")
        root.addWidget(heading)
        subtitle = QLabel(
            "Store 12- or 24-word cryptocurrency wallet seed phrases, optional passphrases, "
            "and notes. Words are shown in a numbered grid and hidden until you choose Show seed."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name, wallet, seed words, passphrase, or notes")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Name A-Z", "name")
        self.sort_combo.addItem("Recently Modified", "modified_desc")
        self.sort_combo.addItem("Wallet A-Z", "wallet")
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

    def _filtered(self) -> list[SeedEntry]:
        query = self.search.text()
        matching = [item for item in self.vault.model.seed_entries if item.matches(query)]
        mode = self.sort_combo.currentData()
        if mode == "modified_desc":
            return sorted(matching, key=lambda item: item.modified_at, reverse=True)
        if mode == "wallet":
            return sorted(matching, key=lambda item: (item.wallet.lower(), item.name.lower()))
        return sorted(matching, key=lambda item: item.display_title().lower())

    def refresh(self) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        entries = self._filtered()
        self.count_label.setText(f"{len(entries)} seed entr{'y' if len(entries) == 1 else 'ies'}")
        for entry in entries:
            card = SeedCard(entry)
            card.copy_seed_requested.connect(self._copy_seed)
            card.copy_passphrase_requested.connect(self._copy_passphrase)
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
        dialog = SeedEditorDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entry = dialog.entry()
        entry.mark_modified()
        self.vault.model.seed_entries.append(entry)
        if not self._persist():
            self.vault.model.seed_entries = [
                item for item in self.vault.model.seed_entries if item.id != entry.id
            ]
            return
        self.refresh()
        self.status_message.emit(f"Saved {entry.display_title()}")

    def edit_entry(self, entry_id: str) -> None:
        entry = self._by_id(entry_id)
        if not entry:
            return
        dialog = SeedEditorDialog(self, entry=entry)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.entry()
        previous = (
            entry.name,
            entry.wallet,
            entry.word_count,
            entry.seed_phrase,
            entry.passphrase,
            entry.notes,
            entry.modified_at,
        )
        entry.name = updated.name
        entry.wallet = updated.wallet
        entry.word_count = updated.word_count
        entry.seed_phrase = updated.seed_phrase
        entry.passphrase = updated.passphrase
        entry.notes = updated.notes
        entry.mark_modified()
        if not self._persist():
            (
                entry.name,
                entry.wallet,
                entry.word_count,
                entry.seed_phrase,
                entry.passphrase,
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
            "Delete seed entry",
            f"Delete “{entry.display_title()}”? This cannot be undone from the vault.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        previous = list(self.vault.model.seed_entries)
        self.vault.model.seed_entries = [
            item for item in self.vault.model.seed_entries if item.id != entry_id
        ]
        if not self._persist():
            self.vault.model.seed_entries = previous
            return
        self.refresh()
        self.status_message.emit("Seed entry deleted")

    def view_entry(self, entry_id: str) -> None:
        entry = self._by_id(entry_id)
        if not entry:
            return
        dialog = SeedViewDialog(entry, self._copy_seed, self._copy_passphrase, self)
        dialog.exec()

    def _by_id(self, entry_id: str) -> SeedEntry | None:
        return next((item for item in self.vault.model.seed_entries if item.id == entry_id), None)

    def _copy_seed(self, text: str) -> None:
        phrase = normalize_seed_phrase(text)
        self.copy_callback(phrase)
        word_count = len(seed_word_list(phrase))
        self.status_message.emit(f"Full {word_count}-word seed copied to clipboard")

    def _copy_passphrase(self, text: str) -> None:
        self.copy_callback(text)
        self.status_message.emit("Passphrase copied to clipboard")

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
