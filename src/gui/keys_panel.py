from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crypto.vault import Vault
from gui.project_editor import ProjectEditorDialog
from gui.resizable import ResizableDialog
from models.key_project import GPG_ROLE_CODES, GPG_ROLE_LABELS, GpgKey, KeyProject, normalize_role


class KeyTextViewer(ResizableDialog):
    """Popup showing the raw .key file text for copy/paste."""

    def __init__(
        self,
        title: str,
        filename: str,
        raw_text: str,
        copy_callback,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._copy_callback = copy_callback
        self._raw_text = raw_text
        self.setWindowTitle(title)
        self.setMinimumSize(560, 420)
        self.resize(720, 540)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        heading = QLabel(filename or "key.key")
        heading.setObjectName("Title")
        root.addWidget(heading)

        hint = QLabel("Raw .key file contents. Select text or use Copy All to paste elsewhere.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.viewer = QTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setPlainText(raw_text)
        mono = QFont("Cascadia Mono")
        if not mono.exactMatch():
            mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        self.viewer.setFont(mono)
        root.addWidget(self.viewer, 1)

        buttons = QHBoxLayout()
        copy_all = QPushButton("Copy All")
        copy_all.setObjectName("PrimaryButton")
        copy_all.setToolTip("Copy the entire .key file text to the clipboard")
        copy_all.clicked.connect(self._copy_all)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(copy_all)
        buttons.addStretch(1)
        buttons.addWidget(close)
        root.addLayout(buttons)

    def _copy_all(self) -> None:
        if self._raw_text:
            self._copy_callback(self._raw_text)


class ProjectCard(QFrame):
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    copy_public_requested = pyqtSignal(str)
    export_public_requested = pyqtSignal(str)
    view_key_requested = pyqtSignal(str, str)  # project_id, key_id
    export_key_requested = pyqtSignal(str, str)  # project_id, key_id
    copy_text_requested = pyqtSignal(str)

    def __init__(self, project: KeyProject) -> None:
        super().__init__()
        self.project = project
        self.setObjectName("Card")
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(project.name)
        title.setObjectName("CardTitle")
        title_box.addWidget(title)
        if project.description:
            desc = QLabel(project.description)
            desc.setObjectName("Muted")
            desc.setWordWrap(True)
            title_box.addWidget(desc)
        roles = project.roles_present()
        role_text = "Roles: " + (
            ", ".join(f"{code} ({GPG_ROLE_LABELS[code]})" for code in roles) if roles else "none yet"
        )
        roles_label = QLabel(role_text)
        roles_label.setObjectName("Muted")
        title_box.addWidget(roles_label)
        stamps = QLabel(
            f"Created {_format_timestamp(project.created_at)} | Modified {_format_timestamp(project.modified_at)}"
        )
        stamps.setObjectName("Muted")
        title_box.addWidget(stamps)
        header.addLayout(title_box, 1)

        edit_button = _action_button("Edit", "Edit project and keys")
        export_button = _action_button("Export ASC", "Export project public .asc")
        copy_public = _action_button("Copy ASC", "Copy project public .asc")
        delete_button = _action_button("Delete", "Delete project", danger=True)
        header.addWidget(edit_button)
        header.addWidget(export_button)
        header.addWidget(copy_public)
        header.addWidget(delete_button)
        root.addLayout(header)

        if project.keys:
            for key in sorted(
                project.keys,
                key=lambda item: (GPG_ROLE_CODES.index(normalize_role(item.role)), item.label.lower()),
            ):
                root.addWidget(self._build_key_row(key))
        else:
            empty = QLabel("No .key files stored for this project yet.")
            empty.setObjectName("Muted")
            root.addWidget(empty)

        if project.public_asc.strip():
            public_hint = QLabel("Public key half (.asc) is stored.")
            public_hint.setObjectName("Muted")
            root.addWidget(public_hint)

        edit_button.clicked.connect(lambda: self.edit_requested.emit(project.id))
        export_button.clicked.connect(lambda: self.export_public_requested.emit(project.id))
        copy_public.clicked.connect(lambda: self.copy_public_requested.emit(project.id))
        delete_button.clicked.connect(lambda: self.delete_requested.emit(project.id))

    def _build_key_row(self, key: GpgKey) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(10)

        role = normalize_role(key.role)
        role_label = QLabel(f"{role}")
        role_label.setToolTip(GPG_ROLE_LABELS[role])
        role_label.setFixedWidth(28)
        role_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        role_label.setStyleSheet(
            "font-weight: 700; border: 1px solid palette(mid); border-radius: 4px; padding: 2px;"
        )

        details = QVBoxLayout()
        details.setSpacing(2)
        label_text = key.label.strip() or GPG_ROLE_LABELS[role]
        name = QLabel(label_text)
        details.addWidget(name)

        identity_parts: list[str] = []
        if key.fingerprint:
            identity_parts.append(f"Fingerprint: {key.fingerprint}")
        if key.key_id:
            identity_parts.append(f"ID: {key.key_id}")
        if identity_parts:
            identity = QLabel(" | ".join(identity_parts))
            identity.setObjectName("Muted")
            identity.setWordWrap(True)
            details.addWidget(identity)
        else:
            missing = QLabel("Fingerprint: (none) | ID: (none)")
            missing.setObjectName("Muted")
            missing.setWordWrap(True)
            details.addWidget(missing)

        if key.has_key_file:
            filename = key.key_filename or f"{role.lower()}.key"
            file_line = QLabel(f"{filename} ({key.key_size_bytes} bytes)")
        else:
            file_line = QLabel("No .key file")
        file_line.setObjectName("Muted")
        file_line.setWordWrap(True)
        details.addWidget(file_line)

        layout.addWidget(role_label)
        layout.addLayout(details, 1)

        if key.has_key_file:
            view_key = _field_button("View Key")
            view_key.setToolTip("View raw .key file text for copy/paste")
            view_key.clicked.connect(
                lambda checked=False, project_id=self.project.id, key_id=key.id: self.view_key_requested.emit(
                    project_id, key_id
                )
            )
            layout.addWidget(view_key)
            export_key = _field_button("Export Key")
            export_key.setToolTip("Export this role's .key file")
            export_key.clicked.connect(
                lambda checked=False, project_id=self.project.id, key_id=key.id: self.export_key_requested.emit(
                    project_id, key_id
                )
            )
            layout.addWidget(export_key)
        if key.fingerprint.strip():
            copy_fp = _field_button("Copy FP")
            copy_fp.setToolTip("Copy fingerprint")
            copy_fp.clicked.connect(
                lambda checked=False, text=key.fingerprint: self.copy_text_requested.emit(text)
            )
            layout.addWidget(copy_fp)
        return row


class KeysPanel(QWidget):
    """Standalone project-key browser, separate from password entries."""

    status_message = pyqtSignal(str)

    def __init__(self, vault: Vault, copy_callback, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault = vault
        self.copy_callback = copy_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        heading = QLabel("Project Keys")
        heading.setObjectName("Title")
        root.addWidget(heading)
        subtitle = QLabel(
            "Store C / S / E / A GPG .key files and the public .asc half by project. "
            "This area is separate from password entries."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search projects, roles (C/S/E/A), fingerprints, key IDs, .key names, or notes"
        )
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Name A-Z", "name")
        self.sort_combo.addItem("Recently Modified", "modified_desc")
        self.sort_combo.addItem("Oldest Modified", "modified_asc")
        self.sort_combo.addItem("Newest Created", "created_desc")
        self.sort_combo.addItem("Oldest Created", "created_asc")
        add = QPushButton("Add Project")
        add.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        add.setObjectName("PrimaryButton")
        add.clicked.connect(self.add_project)
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
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.list_widget)
        root.addWidget(scroll, 1)

        self.search.textChanged.connect(self.refresh)
        self.sort_combo.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def _filtered_projects(self) -> list[KeyProject]:
        query = self.search.text()
        matching = [project for project in self.vault.model.key_projects if project.matches(query)]
        sort_mode = self.sort_combo.currentData()
        if sort_mode == "modified_desc":
            return sorted(matching, key=lambda project: project.modified_at, reverse=True)
        if sort_mode == "modified_asc":
            return sorted(matching, key=lambda project: project.modified_at)
        if sort_mode == "created_desc":
            return sorted(matching, key=lambda project: project.created_at, reverse=True)
        if sort_mode == "created_asc":
            return sorted(matching, key=lambda project: project.created_at)
        return sorted(matching, key=lambda project: project.name.lower())

    def refresh(self) -> None:
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        projects = self._filtered_projects()
        key_count = sum(len(project.keys) for project in projects)
        self.count_label.setText(f"{len(projects)} projects · {key_count} keys")
        for project in projects:
            card = ProjectCard(project)
            card.edit_requested.connect(self.edit_project)
            card.delete_requested.connect(self.delete_project)
            card.copy_public_requested.connect(self.copy_project_public)
            card.export_public_requested.connect(self.export_project_public)
            card.view_key_requested.connect(self.view_role_key)
            card.export_key_requested.connect(self.export_role_key)
            card.copy_text_requested.connect(self._copy_text)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
            animation = QPropertyAnimation(card, b"windowOpacity", self)
            animation.setDuration(120)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def add_project(self) -> None:
        dialog = ProjectEditorDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        project = dialog.project()
        project.mark_modified()
        self.vault.model.key_projects.append(project)
        if not self._persist():
            self.vault.model.key_projects = [
                item for item in self.vault.model.key_projects if item.id != project.id
            ]
            return
        self.refresh()
        self.status_message.emit(f"Saved project {project.name}")

    def edit_project(self, project_id: str) -> None:
        project = self._project_by_id(project_id)
        if not project:
            return
        dialog = ProjectEditorDialog(self, project=project)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.project()
        previous = (
            project.name,
            project.description,
            project.public_asc,
            project.notes,
            list(project.keys),
            project.modified_at,
        )
        project.name = updated.name
        project.description = updated.description
        project.public_asc = updated.public_asc
        project.notes = updated.notes
        project.keys = updated.keys
        project.mark_modified()
        if not self._persist():
            (
                project.name,
                project.description,
                project.public_asc,
                project.notes,
                project.keys,
                project.modified_at,
            ) = previous
            return
        self.refresh()
        self.status_message.emit(f"Updated project {project.name}")

    def delete_project(self, project_id: str) -> None:
        project = self._project_by_id(project_id)
        if not project:
            return
        answer = QMessageBox.question(
            self,
            "Delete project",
            f"Delete project “{project.name}” and all of its stored keys?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        previous = list(self.vault.model.key_projects)
        self.vault.model.key_projects = [
            item for item in self.vault.model.key_projects if item.id != project_id
        ]
        if not self._persist():
            self.vault.model.key_projects = previous
            return
        self.refresh()
        self.status_message.emit("Project deleted")

    def copy_project_public(self, project_id: str) -> None:
        project = self._project_by_id(project_id)
        if not project:
            return
        if not project.public_asc.strip():
            QMessageBox.information(self, "No public key", "This project has no public .asc stored.")
            return
        self._copy_text(project.public_asc)

    def export_project_public(self, project_id: str) -> None:
        project = self._project_by_id(project_id)
        if not project:
            return
        if not project.public_asc.strip():
            QMessageBox.information(self, "No public key", "This project has no public .asc stored.")
            return
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in project.name) or "project"
        path_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export project public .asc",
            f"{safe}-public.asc",
            "Public key files (*.asc);;All files (*)",
        )
        if not path_name:
            return
        path = Path(path_name)
        if path.suffix.lower() != ".asc":
            path = path.with_suffix(".asc")
        content = project.public_asc
        try:
            path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", f"Could not write file:\n{exc}")
            return
        self.status_message.emit(f"Exported public key to {path.name}")
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    def view_role_key(self, project_id: str, key_id: str) -> None:
        project = self._project_by_id(project_id)
        if not project:
            return
        key = next((item for item in project.keys if item.id == key_id), None)
        if not key or not key.has_key_file:
            QMessageBox.information(self, "No key file", "That role has no .key file stored.")
            return
        try:
            raw = key.key_file_bytes()
        except Exception as exc:
            QMessageBox.warning(self, "View failed", f"Could not decode the stored key file:\n{exc}")
            return
        text, note = _key_bytes_as_text(raw)
        role = normalize_role(key.role)
        filename = key.key_filename or f"{role.lower()}.key"
        title = f"View Key — {project.name} ({role})"
        if note:
            text = f"{note}\n\n{text}"
        dialog = KeyTextViewer(title, filename, text, self._copy_text, self)
        dialog.exec()

    def export_role_key(self, project_id: str, key_id: str) -> None:
        project = self._project_by_id(project_id)
        if not project:
            return
        key = next((item for item in project.keys if item.id == key_id), None)
        if not key or not key.has_key_file:
            QMessageBox.information(self, "No key file", "That role has no .key file stored.")
            return
        role = normalize_role(key.role).lower()
        default_name = key.key_filename or f"{role}.key"
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
            path.write_bytes(key.key_file_bytes())
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", f"Could not write file:\n{exc}")
            return
        self.status_message.emit(f"Exported {path.name}")
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    def _project_by_id(self, project_id: str) -> KeyProject | None:
        return next((item for item in self.vault.model.key_projects if item.id == project_id), None)

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


def _field_button(label: str) -> QPushButton:
    button = QPushButton(label)
    button.setObjectName("FieldActionButton")
    button.setFixedWidth(92)
    button.setMinimumHeight(34)
    return button


def _format_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.astimezone().strftime("%Y-%m-%d %I:%M %p")


def _key_bytes_as_text(raw: bytes) -> tuple[str, str]:
    """Return (display_text, optional_note) for a stored .key file."""
    if not raw:
        return "", "Key file is empty."
    try:
        return raw.decode("utf-8"), ""
    except UnicodeDecodeError:
        pass
    # Prefer a lossless text form for binary keys so Copy All stays useful.
    note = (
        "Note: this .key file is binary (not plain UTF-8 text). "
        "Showing Base64 so you can still copy it. Prefer Export Key for the original bytes."
    )
    return base64.b64encode(raw).decode("ascii"), note

