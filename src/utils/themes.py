from __future__ import annotations


DEFAULT_THEME_NAME = "Dark"
THEME_OPTIONS = [
    DEFAULT_THEME_NAME,
    "Light",
    "Dark +",
    "Terminal",
]


PALETTES: dict[str, dict[str, str]] = {
    DEFAULT_THEME_NAME: {
        "bg": "#101216",
        "sidebar": "#171a21",
        "card": "#191d25",
        "panel": "#181d25",
        "field": "#181d25",
        "field_focus": "#202632",
        "button": "#252c38",
        "button_hover": "#303847",
        "button_pressed": "#3a4456",
        "primary": "#2e6bff",
        "primary_border": "#4c80ff",
        "primary_text": "#f7f9fc",
        "text": "#f2f4f8",
        "muted": "#9ba6b8",
        "border": "#2b313d",
        "field_border": "#2c3442",
        "focus": "#5a91ff",
        "danger": "#6f3038",
        "danger_border": "#99414c",
    },
    "Light": {
        "bg": "#f7f8fa",
        "sidebar": "#eef2ff",
        "card": "#ffffff",
        "panel": "#ffffff",
        "field": "#ffffff",
        "field_focus": "#ffffff",
        "button": "#ffffff",
        "button_hover": "#eef2ff",
        "button_pressed": "#e5e7eb",
        "primary": "#111827",
        "primary_border": "#111827",
        "primary_text": "#ffffff",
        "text": "#111827",
        "muted": "#6b7280",
        "border": "#d1d5db",
        "field_border": "#d1d5db",
        "focus": "#2563eb",
        "danger": "#b71c1c",
        "danger_border": "#991b1b",
    },
    "Dark +": {
        "bg": "#1a1a1a",
        "sidebar": "#0d0d0d",
        "card": "#222222",
        "panel": "#222222",
        "field": "#1a1a1a",
        "field_focus": "#222222",
        "button": "#2e2e2e",
        "button_hover": "#383838",
        "button_pressed": "#444444",
        "primary": "#e86926",
        "primary_border": "#e86926",
        "primary_text": "#ffffff",
        "text": "#ececec",
        "muted": "#888888",
        "border": "#3a3a3a",
        "field_border": "#3a3a3a",
        "focus": "#e86926",
        "danger": "#74312c",
        "danger_border": "#f07070",
    },
    "Terminal": {
        "bg": "#000000",
        "sidebar": "#0b0b0d",
        "card": "#0b0b0d",
        "panel": "#0b0b0d",
        "field": "#111113",
        "field_focus": "#151518",
        "button": "#1a1a1d",
        "button_hover": "#242428",
        "button_pressed": "#2b2b30",
        "primary": "#facc15",
        "primary_border": "#facc15",
        "primary_text": "#111111",
        "text": "#f5f5f5",
        "muted": "#d6b84a",
        "border": "#2e2e33",
        "field_border": "#2e2e33",
        "focus": "#facc15",
        "danger": "#4a1f25",
        "danger_border": "#ff6b7a",
    },
}


def theme_stylesheet(theme_name: str) -> str:
    palette = PALETTES.get(theme_name, PALETTES[DEFAULT_THEME_NAME])
    return _build_stylesheet(palette)


def _build_stylesheet(p: dict[str, str]) -> str:
    return f"""
* {{
    font-family: "Segoe UI", "Inter", Arial, sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog, QWidget {{
    background: {p["bg"]};
    color: {p["text"]};
}}
QFrame#Sidebar {{
    background: {p["sidebar"]};
    border-right: 1px solid {p["border"]};
}}
QFrame#Card {{
    background: {p["card"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
}}
QFrame#GeneratorPanel {{
    background: {p["panel"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
}}
QLineEdit, QTextEdit, QComboBox, QSpinBox {{
    background: {p["field"]};
    border: 1px solid {p["field_border"]};
    border-radius: 8px;
    color: {p["text"]};
    padding: 8px 10px;
    selection-background-color: {p["focus"]};
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    background: {p["field_focus"]};
    border-color: {p["focus"]};
}}
QLineEdit#GeneratedPassword {{
    background: {p["field"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    color: {p["text"]};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 16px;
    padding: 12px;
}}
QLineEdit#LengthInput, QLineEdit#SecondsInput {{
    background: {p["field"]};
    max-width: 72px;
    min-height: 30px;
    padding: 6px 8px;
}}
QPushButton {{
    background: {p["button"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    color: {p["text"]};
    padding: 8px 12px;
}}
QPushButton:hover {{
    background: {p["button_hover"]};
    border-color: {p["focus"]};
}}
QPushButton:pressed {{
    background: {p["button_pressed"]};
}}
QPushButton#PrimaryButton {{
    background: {p["primary"]};
    border-color: {p["primary_border"]};
    color: {p["primary_text"]};
}}
QPushButton#DangerButton {{
    background: {p["danger"]};
    border-color: {p["danger_border"]};
}}
QPushButton#ActionButton, QPushButton#FieldActionButton {{
    background: {p["button"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 6px 10px;
}}
QPushButton#ActionButton:hover, QPushButton#FieldActionButton:hover {{
    background: {p["button_hover"]};
    border-color: {p["focus"]};
}}
QPushButton#ActionButton:pressed, QPushButton#FieldActionButton:pressed {{
    background: {p["button_pressed"]};
}}
QPushButton#FieldActionButton {{
    padding: 5px 8px;
}}
QPushButton#StepperButton {{
    background: {p["button"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    font-size: 16px;
    font-weight: 700;
    min-width: 38px;
    max-width: 38px;
    min-height: 34px;
    padding: 0;
}}
QPushButton#StepperButton:hover {{
    background: {p["button_hover"]};
    border-color: {p["focus"]};
}}
QPushButton#StepperButton:pressed {{
    background: {p["button_pressed"]};
}}
QPushButton#SidebarButton {{
    border: 0;
    border-radius: 8px;
    text-align: left;
    padding: 10px 12px;
}}
QPushButton#SidebarButton:hover {{
    background: {p["button_hover"]};
}}
QLabel#Muted {{
    color: {p["muted"]};
}}
QLabel#Title {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#CardTitle {{
    font-size: 16px;
    font-weight: 700;
}}
QLabel#StrengthLabel {{
    color: {p["text"]};
    min-width: 120px;
}}
QScrollArea {{
    border: 0;
}}
QCheckBox {{
    spacing: 8px;
}}
QProgressBar {{
    background: {p["button"]};
    border: 1px solid {p["border"]};
    border-radius: 5px;
    min-height: 10px;
}}
QProgressBar::chunk {{
    border-radius: 4px;
}}
QToolTip {{
    background: {p["field"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    padding: 6px;
}}
"""


DARK_THEME = theme_stylesheet(DEFAULT_THEME_NAME)
