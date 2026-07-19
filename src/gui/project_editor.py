from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.resizable import ResizableDialog
from models.key_project import (
    GPG_ROLE_CODES,
    GPG_ROLE_LABELS,
    GpgKey,
    KeyProject,
    normalize_role,
    role_display,
)
from utils.gpg_metadata import apply_identity_to_fields, describe_extraction_failure


class NoWheelComboBox(QComboBox):
    """Combo box that ignores mouse-wheel selection changes; open the dropdown to pick."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        event.ignore()


class KeyEditorRow(QFrame):
    def __init__(self, key: GpgKey | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._key_id = key.id if key else None
        self._created_at = key.created_at if key else None
        self._key_filename = key.key_filename if key else ""
        self._key_data_b64 = key.key_data_b64 if key else ""

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("GPG Key (.key)")
        title.setObjectName("CardTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.remove_button = QPushButton("Remove")
        self.remove_button.setObjectName("DangerButton")
        self.remove_button.setToolTip("Remove this key from the project")
        header.addWidget(self.remove_button)
        root.addLayout(header)

        form = QFormLayout()
        form.setSpacing(8)

        self.role_combo = NoWheelComboBox()
        for code in GPG_ROLE_CODES:
            self.role_combo.addItem(role_display(code), code)
        if key:
            index = self.role_combo.findData(normalize_role(key.role))
            self.role_combo.setCurrentIndex(index if index >= 0 else 0)

        self.label_edit = QLineEdit(key.label if key else "")
        self.label_edit.setPlaceholderText("Optional label (e.g. release signing)")
        self.fingerprint_edit = QLineEdit(key.fingerprint if key else "")
        self.fingerprint_edit.setPlaceholderText("Fingerprint")
        self.key_id_edit = QLineEdit(key.key_id if key else "")
        self.key_id_edit.setPlaceholderText("Key ID")

        form.addRow("Role", self.role_combo)
        form.addRow("Label", self.label_edit)
        form.addRow("Fingerprint", self.fingerprint_edit)
        form.addRow("Key ID", self.key_id_edit)
        root.addLayout(form)

        key_label = QLabel("Key file (.key) — stored encrypted in the vault")
        key_label.setObjectName("Muted")
        root.addWidget(key_label)

        self.key_status = QLabel()
        self.key_status.setObjectName("Muted")
        self.key_status.setWordWrap(True)
        root.addWidget(self.key_status)
        self._refresh_key_status()

        key_row = QHBoxLayout()
        import_key = QPushButton("Import .key")
        import_key.setToolTip("Import a C/S/E/A key file")
        import_key.clicked.connect(self._import_key_file)
        export_key = QPushButton("Export .key")
        export_key.setToolTip("Export the stored key file")
        export_key.clicked.connect(self._export_key_file)
        clear_key = QPushButton("Clear .key")
        clear_key.setToolTip("Remove the stored key file from this entry")
        clear_key.clicked.connect(self._clear_key_file)
        key_row.addWidget(import_key)
        key_row.addWidget(export_key)
        key_row.addWidget(clear_key)
        key_row.addStretch(1)
        root.addLayout(key_row)

        notes_label = QLabel("Key notes")
        notes_label.setObjectName("Muted")
        root.addWidget(notes_label)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Usage notes, passphrase location reminders, etc.")
        self.notes_edit.setPlainText(key.notes if key else "")
        self.notes_edit.setMaximumHeight(80)
        root.addWidget(self.notes_edit)

    def _refresh_key_status(self) -> None:
        if not self._key_data_b64.strip():
            self.key_status.setText("No .key file imported.")
            return
        size = 0
        try:
            size = GpgKey(key_data_b64=self._key_data_b64).key_size_bytes
        except Exception:
            size = 0
        name = self._key_filename or "key.key"
        self.key_status.setText(f"Stored: {name} ({size} bytes)")

    def _import_key_file(self) -> None:
        path_name, _ = QFileDialog.getOpenFileName(
            self,
            "Import key file",
            "",
            "Key files (*.key);;All files (*)",
        )
        if not path_name:
            return
        path = Path(path_name)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            QMessageBox.warning(self, "Import failed", f"Could not read file:\n{exc}")
            return
        if not raw:
            QMessageBox.warning(self, "Import failed", "The selected key file is empty.")
            return
        filename = path.name if path.suffix.lower() == ".key" else f"{path.stem}.key"
        temp = GpgKey()
        temp.set_key_file(filename, raw)
        self._key_filename = temp.key_filename
        self._key_data_b64 = temp.key_data_b64
        self._refresh_key_status()
        self._apply_metadata_from_key_bytes(raw, filename)

    def _apply_metadata_from_key_bytes(self, raw: bytes, filename: str = "") -> None:
        preferred_role = str(self.role_combo.currentData() or "")
        identity = apply_identity_to_fields(raw, preferred_role=preferred_role, filename=filename)
        if identity is None or (not identity.fingerprint and not identity.key_id):
            QMessageBox.information(
                self,
                "Metadata not detected",
                describe_extraction_failure(raw, filename=filename),
            )
            return
        if identity.fingerprint:
            self.fingerprint_edit.setText(identity.fingerprint)
        if identity.key_id:
            self.key_id_edit.setText(identity.key_id)
        # Only auto-set role when the imported material clearly indicates one.
        if identity.role in GPG_ROLE_CODES:
            index = self.role_combo.findData(identity.role)
            if index >= 0:
                self.role_combo.setCurrentIndex(index)
        # Fill empty label from UID when available.
        if identity.label and not self.label_edit.text().strip():
            self.label_edit.setText(identity.label)


    def _export_key_file(self) -> None:
        if not self._key_data_b64.strip():
            QMessageBox.warning(self, "Nothing to export", "This entry has no .key file stored.")
            return
        role = str(self.role_combo.currentData() or "S").lower()
        default_name = self._key_filename or f"{role}.key"
        path_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export key file",
            default_name,
            "Key files (*.key);;All files (*)",
        )
        if not path_name:
            return
        path = Path(path_name)
        if path.suffix.lower() != ".key":
            path = path.with_suffix(".key")
        try:
            path.write_bytes(GpgKey(key_data_b64=self._key_data_b64).key_file_bytes())
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", f"Could not write file:\n{exc}")
            return
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    def _clear_key_file(self) -> None:
        self._key_filename = ""
        self._key_data_b64 = ""
        self._refresh_key_status()

    def to_key(self) -> GpgKey:
        role = str(self.role_combo.currentData() or "S")
        if self._key_id:
            return GpgKey(
                id=self._key_id,
                role=role,
                label=self.label_edit.text().strip(),
                fingerprint=self.fingerprint_edit.text().strip(),
                key_id=self.key_id_edit.text().strip(),
                key_filename=self._key_filename,
                key_data_b64=self._key_data_b64,
                notes=self.notes_edit.toPlainText(),
                created_at=self._created_at or "",
            )
        return GpgKey(
            role=role,
            label=self.label_edit.text().strip(),
            fingerprint=self.fingerprint_edit.text().strip(),
            key_id=self.key_id_edit.text().strip(),
            key_filename=self._key_filename,
            key_data_b64=self._key_data_b64,
            notes=self.notes_edit.toPlainText(),
        )


class ProjectEditorDialog(ResizableDialog):
    def __init__(self, parent: QWidget | None = None, project: KeyProject | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Project Keys" if project else "Add Project Keys")
        self.setMinimumSize(680, 520)
        self.resize(760, 720)
        self._project_id = project.id if project else None
        self._created_at = project.created_at if project else None
        self._key_rows: list[KeyEditorRow] = []

        root = QVBoxLayout(self)
        root.setSpacing(12)

        title = QLabel("Project" if not project else project.name)
        title.setObjectName("Title")
        root.addWidget(title)

        form = QFormLayout()
        self.name_edit = QLineEdit(project.name if project else "")
        self.name_edit.setPlaceholderText("Project name")
        self.description_edit = QLineEdit(project.description if project else "")
        self.description_edit.setPlaceholderText("Short description")
        form.addRow("Name", self.name_edit)
        form.addRow("Description", self.description_edit)
        root.addLayout(form)

        project_public = QLabel("Public key half (.asc) — the only ASCII-armored public export")
        project_public.setObjectName("Muted")
        root.addWidget(project_public)
        self.public_asc = QTextEdit()
        self.public_asc.setPlaceholderText(
            "Project public key (.asc)\n-----BEGIN PGP PUBLIC KEY BLOCK-----"
        )
        self.public_asc.setPlainText(project.public_asc if project else "")
        self.public_asc.setMinimumHeight(110)
        root.addWidget(self.public_asc)

        public_actions = QHBoxLayout()
        import_project_public = QPushButton("Import .asc")
        import_project_public.clicked.connect(self._import_project_public)
        export_project_public = QPushButton("Export .asc")
        export_project_public.clicked.connect(self._export_project_public)
        public_actions.addWidget(import_project_public)
        public_actions.addWidget(export_project_public)
        public_actions.addStretch(1)
        root.addLayout(public_actions)

        notes_label = QLabel("Project notes")
        notes_label.setObjectName("Muted")
        root.addWidget(notes_label)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Project-level notes about key usage or distribution")
        self.notes_edit.setPlainText(project.notes if project else "")
        self.notes_edit.setMaximumHeight(80)
        root.addWidget(self.notes_edit)

        keys_header = QHBoxLayout()
        keys_title = QLabel("Key files (C / S / E / A .key)")
        keys_title.setObjectName("CardTitle")
        keys_header.addWidget(keys_title)
        keys_header.addStretch(1)
        add_key = QPushButton("Add Key")
        add_key.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        add_key.setObjectName("PrimaryButton")
        add_key.clicked.connect(lambda: self._add_key_row())
        keys_header.addWidget(add_key)
        root.addLayout(keys_header)

        role_hint = QLabel(
            "Roles: C = Certify, S = Sign, E = Encrypt, A = Authenticate. "
            "Each role stores a .key file. The public half is the project .asc only."
        )
        role_hint.setObjectName("Muted")
        role_hint.setWordWrap(True)
        root.addWidget(role_hint)

        self.keys_container = QWidget()
        self.keys_layout = QVBoxLayout(self.keys_container)
        self.keys_layout.setContentsMargins(0, 0, 0, 0)
        self.keys_layout.setSpacing(10)
        self.keys_layout.addStretch(1)
        keys_scroll = QScrollArea()
        keys_scroll.setWidgetResizable(True)
        keys_scroll.setWidget(self.keys_container)
        keys_scroll.setMinimumHeight(220)
        root.addWidget(keys_scroll, 1)

        if project and project.keys:
            for key in project.keys:
                self._add_key_row(key)
        else:
            for code in GPG_ROLE_CODES:
                self._add_key_row(GpgKey(role=code, label=GPG_ROLE_LABELS[code]))

        button_row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save Project")
        save.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self.accept)
        button_row.addStretch(1)
        button_row.addWidget(cancel)
        button_row.addWidget(save)
        root.addLayout(button_row)

    def _add_key_row(self, key: GpgKey | None = None) -> None:
        row = KeyEditorRow(key, self)
        row.remove_button.clicked.connect(lambda: self._remove_key_row(row))
        self._key_rows.append(row)
        self.keys_layout.insertWidget(self.keys_layout.count() - 1, row)

    def _remove_key_row(self, row: KeyEditorRow) -> None:
        if row not in self._key_rows:
            return
        self._key_rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    def _import_project_public(self) -> None:
        text = _load_text_file(
            self,
            "Import public key (.asc)",
            "Public key files (*.asc);;All files (*)",
        )
        if text is not None:
            self.public_asc.setPlainText(text)

    def _export_project_public(self) -> None:
        text = self.public_asc.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Nothing to export", "This project has no public .asc content.")
            return
        name = self.name_edit.text().strip() or "project"
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name)
        _save_text_file(
            self,
            "Export public key (.asc)",
            text,
            f"{safe}-public.asc",
            "Public key files (*.asc);;All files (*)",
            preferred_suffix=".asc",
        )

    def accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Project name is required.")
            return
        super().accept()

    def project(self) -> KeyProject:
        keys = [row.to_key() for row in self._key_rows]
        keys = [key for key in keys if _key_has_content(key)]
        if self._project_id:
            return KeyProject(
                id=self._project_id,
                name=self.name_edit.text().strip(),
                description=self.description_edit.text().strip(),
                public_asc=self.public_asc.toPlainText().strip(),
                notes=self.notes_edit.toPlainText(),
                keys=keys,
                created_at=self._created_at or "",
            )
        return KeyProject(
            name=self.name_edit.text().strip(),
            description=self.description_edit.text().strip(),
            public_asc=self.public_asc.toPlainText().strip(),
            notes=self.notes_edit.toPlainText(),
            keys=keys,
        )


def _key_has_content(key: GpgKey) -> bool:
    return any(
        [
            key.label.strip() and key.label.strip() != GPG_ROLE_LABELS.get(normalize_role(key.role), ""),
            key.fingerprint.strip(),
            key.key_id.strip(),
            key.has_key_file,
            key.notes.strip(),
        ]
    )


def _load_text_file(parent: QWidget, title: str, file_filter: str) -> str | None:
    path_name, _ = QFileDialog.getOpenFileName(parent, title, "", file_filter)
    if not path_name:
        return None
    try:
        return Path(path_name).read_text(encoding="utf-8")
    except OSError as exc:
        QMessageBox.warning(parent, "Import failed", f"Could not read file:\n{exc}")
        return None


def _save_text_file(
    parent: QWidget,
    title: str,
    content: str,
    default_name: str,
    file_filter: str,
    preferred_suffix: str,
) -> None:
    path_name, _ = QFileDialog.getSaveFileName(parent, title, default_name, file_filter)
    if not path_name:
        return
    path = Path(path_name)
    if path.suffix.lower() != preferred_suffix.lower():
        path = path.with_suffix(preferred_suffix)
    try:
        path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    except OSError as exc:
        QMessageBox.warning(parent, "Export failed", f"Could not write file:\n{exc}")
        return
    QMessageBox.information(parent, "Exported", f"Saved to:\n{path}")
