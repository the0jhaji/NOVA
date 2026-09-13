"""
NOVA Voice Assistant - Central Orb (Aurora Core)
The animated heart of the interface.

Draws a multi-layered energy core:
- Soft ambient glow
- Rotating conic "energy mantle"
- Radial body (primary -> secondary gradient)
- Focal bright core
- Filament arcs that bind the core
- Expanding burst arcs during PROCESSING
- Progress arc during EXECUTING
- Error glyph glitch during ERROR

All motion reads from the shared NovaStateAnimator so every element
stays in sync and no per-widget timer is needed.
"""

import math

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QRadialGradient, QConicalGradient, QFont,
)
from PyQt6.QtWidgets import QWidget


class NovaOrb(QWidget):
    """State-and-audio-reactive core orb; only repaints when the animator ticks."""

    state_changed = pyqtSignal(str)

    def __init__(self, animator, parent=None, size: int = 230):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.animator = animator
        animator.updated.connect(self.update)

        self._state = "IDLE"
        self.animator.set_state("IDLE")

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, new_state: str):
        if new_state != self._state:
            self._state = new_state
            self.animator.set_state(new_state)
            self.state_changed.emit(new_state)

    def set_audio_level(self, level: float):
        self.animator.set_audio_level(level)

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        a = self.animator
        cx, cy = self.width() / 2, self.height() / 2
        base_r = (min(self.width(), self.height()) / 2) - 12

        # Pulse: breathing base + mic/speech influence per mode
        pulse = a.pulse_amp
        if a.mode == "listen":
            pulse += a.audio_level * 0.10
        elif a.mode == "speak":
            pulse += a.speech_env * 0.10
        elif a.mode == "error":
            pulse += 0.03 * (1.0 if int(a.time * 3) % 2 == 0 else 0.0)
        r = base_r * pulse

        primary, secondary = a.primary, a.secondary
        rot = math.radians(a.rotation)

        # ---------------- Ambient glow ----------------
        glow_r = r * 1.42
        g = QRadialGradient(QPointF(cx, cy), glow_r)
        c = QColor(primary); c.setAlpha(40 + int(30 * a.pulse_amp))
        c2 = QColor(primary); c2.setAlpha(0)
        g.setColorAt(0.0, c)
        g.setColorAt(1.0, c2)
        painter.setBrush(QBrush(g))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        # ---------------- Energy mantle (rotating conic ring) ----------------
        ring_r = r * 0.90
        ring_rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
        cone = QConicalGradient(QPointF(cx, cy), math.degrees(rot))
        cone.setColorAt(0.0, primary)
        cone.setColorAt(0.45, secondary)
        cone.setColorAt(0.78, QColor(primary.red(), primary.green(), primary.blue(), 60))
        cone.setColorAt(1.0, primary)
        pen = QPen(QBrush(cone), 2.6)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring_rect)

        # ---------------- Orb body ----------------
        body_r = r * 0.78
        body = QRadialGradient(QPointF(cx - body_r * 0.25, cy - body_r * 0.25), body_r * 1.15)
        body.setColorAt(0.0, QColor(255, 255, 255, 50))
        body.setColorAt(0.22, primary)
        body.setColorAt(0.62, secondary)
        body.setColorAt(1.0, QColor(2, 4, 12, 140))
        painter.setBrush(QBrush(body))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), body_r, body_r)

        # ---------------- Focal bright core ----------------
        core_r = body_r * 0.44
        core = QRadialGradient(QPointF(cx, cy), core_r)
        core.setColorAt(0.0, QColor(236, 248, 255, 235))
        core.setColorAt(0.55, QColor(primary.red(), primary.green(), primary.blue(), 180))
        core.setColorAt(1.0, QColor(primary.red(), primary.green(), primary.blue(), 0))
        painter.setBrush(QBrush(core))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)

        # ---------------- Filament arcs binding the core ----------------
        fila_r = body_r * 0.62
        fila_rect = QRectF(cx - fila_r, cy - fila_r, fila_r * 2, fila_r * 2)
        for i in range(6):
            start = math.degrees(rot) + i * 60
            pen = QPen(QColor(secondary.red(), secondary.green(), secondary.blue(), 110))
            pen.setWidthF(1.2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(fila_rect, int(start), 34)

        # ---------------- Expanding burst arcs (PROCESSING) ----------------
        if a.mode in ("process", "execute"):
            for i in range(3):
                t = ((a.time * 0.9 + i / 3.0) % 1.0)
                burst_r = ring_r + t * (r * 0.55)
                rect = QRectF(cx - burst_r, cy - burst_r, burst_r * 2, burst_r * 2)
                pen = QPen(QColor(primary.red(), primary.green(), primary.blue(),
                                 int(190 * (1.0 - t))))
                pen.setWidthF(1.6)
                painter.setPen(pen)
                painter.drawArc(rect, int(math.degrees(rot) + i * 120), 46)

        # ---------------- Progress arc (EXECUTING) ----------------
        if a.mode == "execute":
            prog_r = ring_r * 1.04
            rect = QRectF(cx - prog_r, cy - prog_r, prog_r * 2, prog_r * 2)
            pen = QPen(primary)
            pen.setWidthF(3.2)
            painter.setPen(pen)
            painter.drawArc(rect, -90, int(-360 * a.progress))

        # ---------------- Error glitch bars ----------------
        if a.mode == "error":
            glitch_r = body_r * 0.9
            for i in range(2):
                y = cy + (i - 0.5) * glitch_r * 0.5
                pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 150))
                pen.setWidthF(1.4)
                painter.setPen(pen)
                painter.drawLine(QPointF(cx - glitch_r, y),
                                 QPointF(cx + glitch_r, y))

        # ---------------- Orbiting particles (deterministic) ----------------
        particle_count = 10 if a.mode not in ("idle", "error") else 6
        for i in range(particle_count):
            ang = rot + i * (math.tau / particle_count) + a.time * (0.4 + i * 0.03)
            pr = ring_r * (0.78 + 0.2 * math.sin(ang * 1.3 + i))
            px = cx + math.cos(ang) * pr
            py = cy + math.sin(ang) * pr
            col = QColor(primary if i % 2 == 0 else secondary)
            col.setAlpha(150)
            painter.setBrush(QBrush(col))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(px, py), 2.2, 2.2)

        # ---------------- Center text ----------------
        text = a.orb_text
        if text:
            painter.setPen(QPen(QColor(240, 250, 255, 235)))
            font = QFont("Segoe UI Semibold", 15)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(cx - body_r, cy - 16, body_r * 2, 32),
                             Qt.AlignmentFlag.AlignCenter, text)

        painter.end()