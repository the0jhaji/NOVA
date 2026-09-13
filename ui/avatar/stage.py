"""
NOVA Voice Assistant - Avatar Stage
Backdrop FX layer around NOVA's character (halo rings, orbiting particles,
state-themed glows, wake speech bubble). Hosts the `AnimeFace` on top.
Renders purely from the shared `NovaStateAnimator` clock + theme.
"""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QLinearGradient, QPainter,
                         QPainterPath, QPen, QRadialGradient)
from PyQt6.QtWidgets import QWidget

from ui.avatar.face import AnimeFace, STATE_ACCENT, W as FW, H as FH
from utils.logger import log

SW, SH = 560, 470
FACE_X, FACE_Y = (SW - FW) // 2, (SH - FH) // 2 - 8


class AvatarStage(QWidget):
    """NOVA's character + state FX. `state`, `audio_level` and
    `speech_envelope` are read live from the animator each frame."""

    def __init__(self, animator, parent=None):
        super().__init__(parent)
        self.animator = animator
        self.setFixedSize(SW, SH)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.face = AnimeFace(animator, self)
        self.face.move(FACE_X, FACE_Y)
        self.animator.updated.connect(self.update)

    # ------------------------------------------------------------- helpers
    def _state(self) -> str:
        raw = str(getattr(self.animator, "state", "IDLE")).upper()
        if raw == "PROCESSING":
            raw = "THINKING"
        return raw if raw in STATE_ACCENT else "IDLE"

    def _accent(self) -> QColor:
        return STATE_ACCENT[self._state()]

    def _t(self) -> float:
        return float(getattr(self.animator, "time", 0.0) or 0.0)

    def _rot(self) -> float:
        return float(getattr(self.animator, "rotation", 0.0) or 0.0)

    def _progress(self) -> float:
        return float(getattr(self.animator, "progress", 0.0) or 0.0)

    def _audio(self) -> float:
        return float(getattr(self.animator, "audio_level", 0.0) or 0.0)

    # ------------------------------------------------------------- painting
    def paintEvent(self, _event):
        try:
            self._paint()
        except Exception:
            log.exception("AvatarStage paint failed")

    def _paint(self):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            head = QPointF(SW / 2, FACE_Y + 190)
            accent = self._accent()
            state = self._state()
            t = self._t()

            self._glow(p, head, accent)
            self._halo(p, head, accent)
            self._particles(p, head, accent)
            if state == "LISTENING":
                self._listen_rings(p, head, accent)
            if state == "THINKING":
                self._thinking_dots(p, head, accent)
            if state == "EXECUTING":
                self._progress_arc(p, head, accent)
            if state == "SUCCESS":
                self._burst(p, head, accent)
            if state == "ERROR":
                self._glitch_bars(p, accent)
            self._wake_bubble(p, accent)
        finally:
            p.end()

    def _glow(self, p: QPainter, head: QPointF, accent: QColor):
        pulse = float(getattr(self.animator, "pulse", 0.0) or 0.0)
        r = 178 + 14 * math.sin(self._t() * 1.4) + 8 * pulse
        g = QRadialGradient(head, r)
        c = accent
        g.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), 56))
        g.setColorAt(0.55, QColor(c.red(), c.green(), c.blue(), 22))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(g)
        p.drawEllipse(head, r, r)

    def _halo(self, p: QPainter, head: QPointF, accent: QColor):
        rot = self._rot()
        for i, (rad, a, w) in enumerate(
                ((150, 34, 5), (196, 18, 3), (242, 10, 1.6))):
            color = QColor(accent.red(), accent.green(), accent.blue(), a)
            pen = QPen(color, w, cap=Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            arc = QPainterPath()
            start = rot + i * 47 + 90
            arc.moveTo(head.x() + rad * math.cos(math.radians(start)),
                       head.y() + rad * math.sin(math.radians(start)))
            for deg in range(1, 201, 8):
                a_ = math.radians(start + deg)
                arc.lineTo(head.x() + rad * math.cos(a_),
                           head.y() + rad * math.sin(a_))
            p.drawPath(arc)

    def _particles(self, p: QPainter, head: QPointF, accent: QColor):
        t = self._t()
        for i in range(12):
            base = i * 30 + self._rot() * 0.7
            rad = 214 + 14 * math.sin(t * 1.3 + i * 1.7)
            ang = math.radians(base)
            x = head.x() + rad * math.cos(ang)
            y = head.y() + rad * math.sin(ang)
            a = int(110 + 90 * math.sin(t * 2.4 + i * 2.0))
            p.setPen(QPen(QColor(0, 0, 0, 0)))
            p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), a))
            p.drawEllipse(QPointF(x, y), 2.4, 2.4)

    def _listen_rings(self, p: QPainter, head: QPointF, accent: QColor):
        audio = self._audio()
        t = self._t()
        for k in range(3):
            rad = 120 + k * 26 + audio * 26 + 6 * math.sin(t * 3.1 + k)
            a = int(26 + (30.0 / (k + 1)))
            pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), a),
                       2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(head, rad, rad)

    def _thinking_dots(self, p: QPainter, head: QPointF, accent: QColor):
        p.setFont(QFont("Segoe UI", 26, 700))
        p.setPen(_with_alpha(accent, 230))
        x = head.x() - 34
        y = head.y() - 190
        for i in range(3):
            lift = 12 * math.sin(self._t() * 4.0 - i * 1.2)
            p.drawText(QRectF(x + i * 30, y - lift, 30, 30),
                       Qt.AlignmentFlag.AlignCenter, "·")
        p.setPen(Qt.PenStyle.NoPen)

    def _progress_arc(self, p: QPainter, head: QPointF, accent: QColor):
        prog = self._progress()
        pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 90),
                   20, cap=Qt.PenCapStyle.RoundCap)
        pen.setDashPattern([1, 8])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(head, 172, 172)
        if prog > 0:
            pen2 = QPen(accent, 20, cap=Qt.PenCapStyle.RoundCap)
            p.setPen(pen2)
            arc = QPainterPath()
            arc.moveTo(head.x() + 172 * math.cos(math.radians(-90)),
                       head.y() + 172 * math.sin(math.radians(-90)))
            sweep = int(360 * prog)
            for deg in range(8, sweep + 1, 8):
                a = math.radians(-90 + deg)
                arc.lineTo(head.x() + 172 * math.cos(a),
                           head.y() + 172 * math.sin(a))
            p.drawPath(arc)
            # head tip
            a = math.radians(-90 + sweep)
            p.setBrush(accent)
            p.setPen(QPen(QColor(0, 0, 0, 0)))
            p.drawEllipse(
                QPointF(head.x() + 172 * math.cos(a),
                        head.y() + 172 * math.sin(a)), 6, 6)

    def _burst(self, p: QPainter, head: QPointF, accent: QColor):
        t = self._t()
        for i in range(16):
            ang = math.radians(i * 22.5 + t * 8)
            rad = 190 + 34 * math.sin(t * 3.4 + i * 2.1)
            x = head.x() + rad * math.cos(ang)
            y = head.y() + rad * math.sin(ang)
            a = int(150 + 90 * math.sin(t * 5 + i))
            p.setPen(QPen(QColor(0, 0, 0, 0)))
            p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), a))
            p.drawEllipse(QPointF(x, y), 2, 2)

    def _glitch_bars(self, p: QPainter, accent: QColor):
        t = self._t()
        for i in range(5):
            if math.sin(t * 7 + i * 3) < 0:
                continue
            y = int(20 + i * 24 + 6 * math.sin(t * 9 + i))
            x = int(24 + 12 * math.sin(t * 11 + i * 2))
            w = int(150 + 60 * math.sin(t * 13 + i * 5))
            p.setPen(QPen(QColor(0, 0, 0, 0)))
            p.setBrush(QColor(accent.red(), accent.green(), accent.blue(),
                              int(40 + 30 * math.sin(t * 12 + i))))
            p.drawRect(QRectF(x, y, w, 5))

    # ------------------------------------------------------- wake bubble
    def _wake_bubble(self, p: QPainter, accent: QColor):
        text = str(getattr(self.animator, "orb_text", "") or "").strip()
        if not text:
            return
        bw, bh = 176, 52
        bx, by = SW - bw - 28, 16
        bubble = QPainterPath()
        bubble.addRoundedRect(QRectF(bx, by, bw, bh), 18, 18)
        tail = QPainterPath()
        tail.moveTo(bx + 46, by + bh - 2)
        tail.lineTo(bx + 66, by + bh + 16)
        tail.lineTo(bx + 92, by + bh - 2)
        bubble.addPath(tail)
        g = QLinearGradient(QPointF(bx, by), QPointF(bx, by + bh))
        g.setColorAt(0.0, QColor(24, 28, 50, 250))
        g.setColorAt(1.0, QColor(14, 18, 34, 250))
        p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 160),
                      1.4))
        p.setBrush(g)
        p.drawPath(bubble)
        p.setPen(QColor(235, 240, 255))
        p.setFont(QFont("Segoe UI", 13, 600))
        p.drawText(QRectF(bx, by + 8, bw, bh - 8),
                   Qt.AlignmentFlag.AlignCenter, text)


def _with_alpha(color: QColor, alpha: int) -> QColor:
    return QColor(color.red(), color.green(), color.blue(), alpha)