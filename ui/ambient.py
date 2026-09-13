"""
NOVA Voice Assistant - Ambient Background
Full-window deep-space atmosphere behind the command center.

Visuals:
- Very deep navy to near-black vertical gradient (cached to a pixmap).
- Three large soft "aurora" glows that slowly drift and breathe.
- A subtle static star field with slow twinkle.

Performance notes:
- The base gradient is rendered once per resize and cached.
- Glows are cheap radial fills; the star field updates on a slow timer.
- Total: one 35 ms background timer — negligible CPU.
"""

import math
import random

from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QBrush, QLinearGradient, QPixmap, QPen
from PyQt6.QtWidgets import QWidget

from ui.theming import PALETTE


class AmbientBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._t = 0.0
        self._base: QPixmap | None = None

        # Aurora glows: (color, rel pos x, rel pos y, radius factor(int), drift speed, amp)
        self._glows = [
            ((0, 233, 203), 0.32, 0.28, 0.55, 0.10, 0.020),
            ((88, 80, 236), 0.74, 0.22, 0.50, 0.07, 0.018),
            ((30, 90, 200), 0.55, 0.88, 0.60, 0.05, 0.014),
        ]

        # Star field: (x, y, size, base alpha, twinkle phase, twinkle speed)
        rng = random.Random(7)  # fixed seed -> stable field
        self._stars = [
            (rng.random(), rng.random(),
             rng.uniform(0.5, 1.6),
             rng.randint(40, 160),
             rng.uniform(0, math.tau),
             rng.uniform(0.5, 2.0))
            for _ in range(90)
        ]

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.timeout.connect(self._animate)
        self._timer.start(35)

    def _animate(self):
        self._t += 0.035
        self.update()

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event):
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        if self._base is None or self._base.width() != w or self._base.height() != h:
            self._render_base(w, h)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.drawPixmap(0, 0, self._base)

        # Slow drifting aurora glows
        for (color, rx, ry, radius_f, drift, amp) in self._glows:
            px = (rx + amp * math.sin(self._t * drift + rx * 7.0)) * w
            py = (ry + amp * math.cos(self._t * drift * 0.8 + ry * 5.0)) * h
            r = max(w, h) * radius_f * (1.0 + 0.06 * math.sin(self._t * 0.3))

            g = QRadialGradient(px, py, r)
            c = QColor(*color)
            c.setAlpha(14 + int(6 * math.sin(self._t * 0.5 + rx)))
            g.setColorAt(0.0, c)
            c2 = QColor(*color)
            c2.setAlpha(0)
            g.setColorAt(1.0, c2)
            painter.setBrush(QBrush(g))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(px, py), r, r)

        # Star field with gentle twinkle
        for (sx, sy, size, alpha, phase, speed) in self._stars:
            tw = 0.65 + 0.35 * math.sin(self._t * speed + phase)
            col = QColor(220, 234, 255, int(alpha * tw))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col))
            painter.drawEllipse(int(sx * w), int(sy * h), int(size), int(size))

        painter.end()

    def _render_base(self, w: int, h: int):
        """Cache the base gradient so it is not rebuilt every frame."""
        pm = QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor(*PALETTE["bg_top"]))
        g.setColorAt(0.55, QColor(*PALETTE["bg_mid"]))
        g.setColorAt(1.0, QColor(*PALETTE["bg_bottom"]))
        p.fillRect(0, 0, w, h, QBrush(g))
        p.end()
        self._base = pm