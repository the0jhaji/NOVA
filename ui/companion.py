"""
NOVA - Companion & Minimal display modes.
Small floating presence while you work:

- COMPANION:  frameless, translucent window showing the anime character
  (head + shoulders crop) plus a live status caption. Drag anywhere.
- MINIMAL:    a tiny pulsing orb that uses almost no screen space.
  Double-click to come back to the full window.

Both views share the MainWindow's NovaStateAnimator, so the avatar, orb and
full window always show the same emotional state at the same time.
"""

from typing import Optional

from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QRadialGradient, QPainter, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

from ui.theming import STATE_DEFS
from ui.avatar import AvatarStage
from ui.avatar.stage import SW, SH
from utils.logger import log

COMPANION_W, COMPANION_H = 372, 468
COMPANION_CROP_W, COMPANION_CROP_H = 332, 380
COMPANION_CROP_X, COMPANION_CROP_Y = -116, 0


class _Caption(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = "Ready for your command"
        self._color = QColor(154, 180, 206)

    def set_state(self, state: str, caption: str):
        self._text = caption
        self._color = QColor(*STATE_DEFS.get(state, STATE_DEFS["IDLE"])["primary"])
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(self._color)
            f = QFont("Segoe UI", 9)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)
        finally:
            p.end()


class CompanionWindow(QWidget):
    """Floating anime character. Signals let the main window orchestrate."""

    restore_full_requested = pyqtSignal()
    minimal_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, animator, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._animator = animator
        self._drag_offset: Optional[tuple[int, int]] = None

        self.setFixedSize(COMPANION_W, COMPANION_H)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 10)
        outer.setSpacing(4)

        # Head + shoulders crop of the full stage (shared animator).
        crop = QWidget()
        crop.setFixedSize(COMPANION_CROP_W, COMPANION_CROP_H)
        self.stage = AvatarStage(animator)
        self.stage.setParent(crop)
        self.stage.move(COMPANION_CROP_X, COMPANION_CROP_Y)
        outer.addWidget(crop, 0, Qt.AlignmentFlag.AlignHCenter)

        self.caption = _Caption()
        self.caption.setFixedHeight(26)
        outer.addWidget(self.caption, 0, Qt.AlignmentFlag.AlignHCenter)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        dot = QLabel("▓")
        dot.setObjectName("companion_dot")
        dot.setStyleSheet(
            "color:#00E9CB; font-size:9px; padding:0px 2px 0px 0px;")
        controls.addWidget(dot)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("companion_btn")
        btn_close.setToolTip("Close companion")
        btn_close.clicked.connect(self.close_requested.emit)
        controls.addWidget(btn_close)

        btn_min = QPushButton("◉")
        btn_min.setObjectName("companion_btn")
        btn_min.setToolTip("Minimize to orb")
        btn_min.clicked.connect(self.minimal_requested.emit)
        controls.addWidget(btn_min)

        btn_full = QPushButton("⛶")
        btn_full.setObjectName("companion_btn")
        btn_full.setToolTip("Restore full window")
        btn_full.clicked.connect(self.restore_full_requested.emit)
        controls.addWidget(btn_full)

        controls.addStretch()
        outer.addLayout(controls)

    # ------------------------------------------------------------- bridge
    def on_state(self, state: str, caption: str):
        self.caption.set_state(state, caption)

    # ------------------------------------------------------------- window
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                int(event.globalPosition().x()) - self.x(),
                int(event.globalPosition().y()) - self.y(),
            )

    def mouseMoveEvent(self, event):
        if self._drag_offset:
            self.move(
                int(event.globalPosition().x()) - self._drag_offset[0],
                int(event.globalPosition().y()) - self._drag_offset[1],
            )

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    def mouseDoubleClickEvent(self, event):
        self.restore_full_requested.emit()


class MinimalOrb(QWidget):
    """Tiny presence dot; double-click to restore the full window."""

    restore_full_requested = pyqtSignal()

    def __init__(self, animator, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._animator = animator
        self._color = QColor(*STATE_DEFS["IDLE"]["primary"])
        self._pulse = 0.0
        self.setFixedSize(112, 112)
        self.setToolTip("NOVA is here — double-click to open")

    def _refresh(self):
        state = self._animator.state
        base = STATE_DEFS.get(state, STATE_DEFS["IDLE"])["primary"]
        self._color = QColor(*base)
        self._pulse = 0.5 + 0.3 * (self._animator.audio_level or 0.0)
        self.update()

    def paintEvent(self, event):
        self._refresh()
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            cx = self.width() / 2
            cy = self.height() / 2
            r = 26.0 + 6.0 * self._pulse
            grad = QRadialGradient(cx, cy - 6, r * 2.2)
            c = self._color
            grad.setColorAt(0.0, c.lighter(155))
            grad.setColorAt(0.55, c)
            grad.setColorAt(1.0, c.darker(180))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.setPen(QColor(255, 255, 255, 90))
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QPointF(cx - 4.5, cy - 9), 4.5, 4.5)
            p.drawEllipse(QPointF(cx - 4.5, cy + 5), 4.5, 4.5)
        finally:
            p.end()

    def mouseDoubleClickEvent(self, event):
        self.restore_full_requested.emit()