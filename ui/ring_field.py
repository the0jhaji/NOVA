"""
NOVA Voice Assistant - Energy Ring Field
Concentric circular energy rings surrounding the NOVA core.
Three rings with opposing rotation + small orbit dots.
Reads shared visuals from the NovaStateAnimator.
"""

import math

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QRadialGradient
from PyQt6.QtWidgets import QWidget


class EnergyRings(QWidget):
    def __init__(self, animator, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.animator = animator
        # Repaint when the shared clock advances
        animator.updated.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        a = self.animator
        cx, cy = self.width() / 2, self.height() / 2
        max_r = (min(self.width(), self.height()) / 2) - 8
        rot = math.radians(a.ring_angle)
        primary, secondary = a.primary, a.secondary

        # ---------------- Outer dashed ring (slow) ----------------
        ring_r = max_r * 0.98
        pen = QPen(QColor(secondary.red(), secondary.green(), secondary.blue(), 60))
        pen.setWidthF(1.0)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 6])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

        # ---------------- Middle segmented arc (clockwise) ----------------
        mid_r = max_r * 0.78
        rect = QRectF(cx - mid_r, cy - mid_r, mid_r * 2, mid_r * 2)
        pen = QPen(primary)
        pen.setWidthF(2.2)
        painter.setPen(pen)
        seg = 42  # segment length in degrees
        for off in (0, 120, 240):
            start = rot + math.radians(off)
            # two mirrored arcs per group for a "breathing brace" look
            painter.drawArc(rect, int(math.degrees(start)), seg)
            painter.drawArc(rect, int(math.degrees(start)) + 180, seg)

        # ---------------- Inner thin ring (counter-rotation) ----------------
        inner_r = max_r * 0.56
        pen2 = QPen(QColor(primary.red(), primary.green(), primary.blue(), 110))
        pen2.setWidthF(1.4)
        painter.setPen(pen2)
        painter.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        # Glow tips on the segments
        for off in (0, 120, 240):
            ang = rot + math.radians(off)
            px = cx + math.cos(ang) * mid_r
            py = cy + math.sin(ang) * mid_r
            g = QRadialGradient(px, py, 9)
            c1 = QColor(primary); c1.setAlpha(200)
            c2 = QColor(primary); c2.setAlpha(0)
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(g))
            painter.drawEllipse(QPointF(px, py), 9, 9)

        # ---------------- Orbit dots ----------------
        for k, rr in ((0, mid_r), (1, inner_r)):
            ang = rot + (0.0 if k == 0 else 2.0)
            dx = math.cos(ang + k * 1.7)
            dy = math.sin(ang + k * 1.7)
            ox = cx + dx * rr
            oy = cy + dy * rr
            col = QColor(secondary) if k == 0 else QColor(primary)
            col.setAlpha(220)
            r = 3.4 - k * 0.8
            painter.setBrush(QBrush(col))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(ox, oy), r, r)
            # soft halo
            halo = QRadialGradient(ox, oy, 7)
            hc = QColor(col); hc.setAlpha(90)
            hc2 = QColor(col); hc2.setAlpha(0)
            halo.setColorAt(0, hc)
            halo.setColorAt(1, hc2)
            painter.setBrush(QBrush(halo))
            painter.drawEllipse(QPointF(ox, oy), 7, 7)

        painter.end()