"""
NOVA Voice Assistant - Waveform Visualization
Dynamic audio-reactive waveform displayed below the orb.
"""

import math
import random

from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
from PyQt6.QtWidgets import QWidget

from ui.nova_orb import STATE_COLORS


class WaveformWidget(QWidget):
    """
    Animated waveform visualization.
    
    Renders bars or a smooth wave that reacts to audio input
    and changes color based on NOVA's current state.
    """

    def __init__(self, parent=None, width: int = 400, height: int = 60):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setMinimumWidth(width)

        self._state = "IDLE"
        self._audio_level = 0.0
        self._bars: list[float] = []
        self._bar_count = 40
        self._time = 0.0

        # Initialize bar heights
        for i in range(self._bar_count):
            self._bars.append(random.uniform(0.1, 0.3))

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(33)  # ~30fps

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, new_state: str):
        self._state = new_state

    def set_audio_level(self, level: float):
        self._audio_level = max(0.0, min(1.0, level))

    def _animate(self):
        self._time += 0.1
        speed = 0.15 if self._audio_level < 0.1 else 0.05

        for i in range(self._bar_count):
            if self._state == "IDLE":
                # Gentle breathing animation
                target = 0.15 + 0.1 * math.sin(self._time * 0.5 + i * 0.3)
            elif self._state == "LISTENING":
                # Responsive to audio level
                noise = random.uniform(-0.1, 0.1)
                target = 0.2 + self._audio_level * 0.6 + noise
                # Add wave pattern
                target += 0.1 * math.sin(self._time * 2 + i * 0.5)
            elif self._state == "PROCESSING":
                # Pulsing wave
                target = 0.3 + 0.3 * math.sin(self._time * 3 + i * 0.4)
            elif self._state == "SPEAKING":
                # Simulated voice waveform
                target = 0.2 + 0.5 * abs(math.sin(self._time * 4 + i * 0.6))
                target += random.uniform(-0.1, 0.1)
            elif self._state == "EXECUTING":
                target = 0.4 + 0.3 * math.sin(self._time * 2 + i * 0.3)
            elif self._state == "ERROR":
                target = 0.1 + 0.15 * abs(math.sin(self._time * 5 + i * 0.8))
            else:
                target = 0.15

            # Smooth interpolation
            self._bars[i] += (target - self._bars[i]) * speed

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        primary, secondary, _ = STATE_COLORS.get(self._state, STATE_COLORS["IDLE"])

        w = self.width()
        h = self.height()
        bar_w = max(w / self._bar_count - 2, 2)
        gap = (w - bar_w * self._bar_count) / (self._bar_count + 1)

        for i in range(self._bar_count):
            bar_h = max(self._bars[i] * h * 0.9, 2)
            x = gap + i * (bar_w + gap)
            y = (h - bar_h) / 2

            # Color gradient per bar
            t = i / self._bar_count
            color = QColor(primary)
            color.setAlpha(180 + int(75 * self._bars[i]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), bar_w / 3, bar_w / 3)

        painter.end()
