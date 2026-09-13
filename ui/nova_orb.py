"""
NOVA Voice Assistant - Central Orb Widget
Custom-painted animated orb representing NOVA's core.
Changes color, pulse speed, and particle effects based on state.
"""

import math
import random

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QRadialGradient,
    QConicalGradient, QFont,
)
from PyQt6.QtWidgets import QWidget

from utils.logger import log


# State color themes: (primary, secondary, glow)
STATE_COLORS = {
    "IDLE":       (QColor(0, 180, 216), QColor(0, 119, 182),  QColor(0, 180, 216, 40)),
    "LISTENING":  (QColor(0, 255, 136), QColor(0, 200, 100),  QColor(0, 255, 136, 60)),
    "PROCESSING": (QColor(167, 99, 236), QColor(124, 58, 237), QColor(167, 99, 236, 60)),
    "SPEAKING":   (QColor(255, 107, 157), QColor(236, 72, 153), QColor(255, 107, 157, 60)),
    "EXECUTING":  (QColor(255, 193, 7),   QColor(255, 152, 0),  QColor(255, 193, 7, 60)),
    "ERROR":      (QColor(255, 82, 82),   QColor(211, 47, 47),  QColor(255, 82, 82, 60)),
}

# Pulse speed per state (radians per frame)
STATE_PULSE_SPEED = {
    "IDLE": 0.02,
    "LISTENING": 0.05,
    "PROCESSING": 0.08,
    "SPEAKING": 0.06,
    "EXECUTING": 0.07,
    "ERROR": 0.03,
}


class NovaOrb(QWidget):
    """
    Animated central orb widget.
    
    Renders a multi-layered glowing orb with:
    - Outer glow ring
    - Rotating conical gradient (spinning energy)
    - Inner radial gradient core
    - Floating particles
    - Pulsing animation
    
    All visual properties respond to the current state.
    """

    state_changed = pyqtSignal(str)

    def __init__(self, parent=None, size: int = 200):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._state = "IDLE"
        self._pulse_angle = 0.0
        self._particles: list[dict] = []
        self._text = ""
        self._audio_level = 0.0

        # Animation timer — 60fps
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(16)

        self._init_particles()

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, new_state: str):
        if new_state != self._state:
            self._state = new_state
            self._init_particles()
            self.state_changed.emit(new_state)

    def set_text(self, text: str):
        """Text to display inside the orb (e.g., 'YES?')."""
        self._text = text

    def set_audio_level(self, level: float):
        """Audio input level 0.0-1.0 for reactive effects."""
        self._audio_level = max(0.0, min(1.0, level))

    def _init_particles(self):
        """Create floating particles for the current state."""
        self._particles = []
        count = 12 if self._state != "IDLE" else 6
        for _ in range(count):
            self._particles.append({
                "angle": random.uniform(0, 2 * math.pi),
                "distance": random.uniform(0.55, 0.9),
                "speed": random.uniform(0.003, 0.012),
                "size": random.uniform(1.5, 3.5),
                "alpha": random.randint(80, 200),
                "orbit_speed": random.uniform(0.005, 0.02),
            })

    def _animate(self):
        self._pulse_angle += STATE_PULSE_SPEED.get(self._state, 0.03)
        for p in self._particles:
            p["angle"] += p["orbit_speed"]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2
        base_r = min(self.width(), self.height()) / 2 - 10

        primary, secondary, glow_color = STATE_COLORS.get(
            self._state, STATE_COLORS["IDLE"]
        )

        # Pulse factor
        pulse = 1.0 + 0.04 * math.sin(self._pulse_angle)
        if self._audio_level > 0:
            pulse += self._audio_level * 0.15
        r = base_r * pulse

        # --- Outer glow ---
        glow_r = r * 1.35
        glow = QRadialGradient(QPointF(cx, cy), glow_r)
        glow.setColorAt(0.0, QColor(glow_color))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        # --- Rotating ring ---
        ring_rect = QRectF(cx - r, cy - r, r * 2, r * 2)
        ring_gradient = QConicalGradient(QPointF(cx, cy), self._pulse_angle * 30)
        ring_gradient.setColorAt(0.0, primary)
        ring_gradient.setColorAt(0.5, secondary)
        ring_gradient.setColorAt(1.0, primary)
        painter.setPen(QPen(QBrush(ring_gradient), 2.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring_rect)

        # --- Orb body ---
        body_r = r * 0.82
        body_gradient = QRadialGradient(
            QPointF(cx - body_r * 0.2, cy - body_r * 0.2), body_r
        )
        body_gradient.setColorAt(0.0, QColor(255, 255, 255, 40))
        body_gradient.setColorAt(0.3, primary)
        body_gradient.setColorAt(0.7, secondary)
        body_gradient.setColorAt(1.0, QColor(0, 0, 0, 100))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(body_gradient))
        painter.drawEllipse(QPointF(cx, cy), body_r, body_r)

        # --- Inner highlight ---
        highlight_r = body_r * 0.5
        highlight = QRadialGradient(
            QPointF(cx - highlight_r * 0.3, cy - highlight_r * 0.4), highlight_r
        )
        highlight.setColorAt(0.0, QColor(255, 255, 255, 50))
        highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(highlight))
        painter.drawEllipse(QPointF(cx, cy - body_r * 0.1), highlight_r, highlight_r)

        # --- Floating particles ---
        for p in self._particles:
            px = cx + math.cos(p["angle"]) * r * p["distance"]
            py = cy + math.sin(p["angle"]) * r * p["distance"]
            particle_color = QColor(primary)
            particle_color.setAlpha(int(p["alpha"] * pulse))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(particle_color))
            painter.drawEllipse(QPointF(px, py), p["size"], p["size"])

        # --- Center text ---
        if self._text:
            painter.setPen(QPen(QColor(255, 255, 255, 200)))
            font = QFont("Segoe UI", 14, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QRectF(cx - body_r, cy - 15, body_r * 2, 30),
                             Qt.AlignmentFlag.AlignCenter, self._text)
