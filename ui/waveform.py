"""
NOVA Voice Assistant - Waveform
Mirrored spectrum bars below the orb.
Reacts to microphone level (LISTENING), a simulated speech envelope
(SPEAKING), computing pulses (PROCESSING), task energy (EXECUTING)
and stays calm elsewhere. Colors follow the shared animator.
"""

import math

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient
from PyQt6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    def __init__(self, animator, parent=None, width: int = 470, height: int = 52):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.animator = animator
        animator.updated.connect(self.update)

        # Mirrored bar count (half, mirrored across center)
        self._bars = 26
        # Smoothed per-bar values for organic motion
        self._levels = [0.12] * self._bars

    @property
    def state(self) -> str:
        return self.animator.state

    @state.setter
    def state(self, new_state: str):
        self.animator.set_state(new_state)

    def set_audio_level(self, level: float):
        self.animator.set_audio_level(level)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        a = self.animator
        mode = a.mode
        w, h = self.width(), self.height()
        cx = w / 2

        # ---- Build envelopes from animator state ----
        for i in range(self._bars):
            t = i / self._bars
            if mode == "listen":
                target = 0.15 + a.audio_level * 0.55
                target += 0.06 * math.sin(a.time * 9.0 + i * 0.55) * (1.0 - t)
            elif mode == "speak":
                target = 0.18 + a.speech_env * 0.52
                target += 0.07 * math.sin(a.time * 11.0 + i * 0.7)
            elif mode == "process":
                target = 0.30 + 0.34 * abs(math.sin(a.time * 6.0 + i * 0.4))
            elif mode == "execute":
                target = 0.34 + 0.26 * math.sin(a.time * 3.5 + i * 0.3)
            elif mode == "error":
                target = 0.10 + 0.10 * abs(math.sin(a.time * 14.0 + i * 0.9))
            else:
                target = 0.14 + 0.08 * math.sin(a.time * 1.4 + i * 0.35)
            # taper toward edges
            target *= 0.72 + 0.28 * math.sin(math.pi * t)
            self._levels[i] += (target - self._levels[i]) * 0.22

        primary, secondary = a.primary, a.secondary

        step = (w - 30) / (self._bars * 2 - 1)
        bar_w = max(step * 0.46, 2.0)

        # subtle baseline
        pen = QPen(QColor(primary.red(), primary.green(), primary.blue(), 36))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawLine(15, h - 3, w - 15, h - 3)

        for i in range(self._bars):
            level = self._levels[i]
            bh = max(level * (h - 12), 3.0)
            for sign in (-1, 1):
                x = cx + sign * (i * step + step * 0.5)
                rect = QRectF(x - bar_w / 2, (h - bh) / 2, bar_w, bh)
                t = i / self._bars

                grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
                c_top = QColor(primary); c_top.setAlpha(int(180 + 75 * level))
                c_bot = QColor(secondary); c_bot.setAlpha(int(90 + 45 * level))
                grad.setColorAt(0.0, c_top if sign > 0 else c_bot)
                grad.setColorAt(1.0, c_bot if sign > 0 else c_top)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawRoundedRect(rect, bar_w / 2, bar_w / 2)

        painter.end()