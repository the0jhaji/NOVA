"""
NOVA Voice Assistant - Glass UI helpers
Small reusable futuristic widgets: glass panels, section titles,
status rows, and a pill chip for one-shot status flashes.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel


class GlassPanel(QFrame):
    """Translucent rounded panel with a hairline border."""

    def __init__(self, parent=None, object_name: str = "glass_panel"):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class SectionTitle(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("section_title")


def status_row(key: str, value: str, key_color: str | None = None) -> QWidget:
    """A key/value row for the system status panels."""
    row_w = QWidget()
    lay = QHBoxLayout(row_w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    k = QLabel(key)
    k.setObjectName("sys_key")
    v = QLabel(value)
    v.setObjectName("sys_value")
    lay.addWidget(k)
    lay.addStretch()
    lay.addWidget(v)
    if key_color:
        v.setStyleSheet(f"color: {key_color}; font-size: 12px; font-weight: 600;")
    return row_w


class FlashChip(QLabel):
    """
    A short-lived status pill (e.g. success/failure/notice).
    Show it with `show()`/`hide()`; it keeps a fixed height so the
    layout around it does not jump.
    """

    def __init__(self, parent=None, height: int = 26):
        super().__init__("", parent)
        self.setObjectName("flash_chip")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(height)
        self.hide()

    def flash(self, text: str, color: str):
        self.setText(text)
        self.setStyleSheet(
            f"QLabel#flash_chip {{ color: {color}; font-size: 12px; "
            f"font-weight: 600; letter-spacing: 0.5px; "
            f"background-color: rgba(255,255,255,0.04); "
            f"border: 1px solid {color}; border-radius: 13px; }}"
        )
        self.show()


def make_column(*items, spacing: int = 8, margins=(0, 0, 0, 0)) -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for it in items:
        if it is None:
            lay.addStretch()
        elif isinstance(it, str):
            lay.addSpacing(int(it))
        else:
            lay.addWidget(it, 1)
    return lay