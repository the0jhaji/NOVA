"""
NOVA Voice Assistant - Anime Girl (procedural QPainter face)
NOVA's character: an original young-adult AI girl with big anime eyes,
futuristic violet hair, a headset, and a teal sci-fi jacket. Every part of
the face is drawn every frame from its `NovaStateAnimator` clock, so no
animation state is stored between frames:

  - eyes       blink on the animator clock, gaze follows the mode,
               iris + highlights, focus glint while executing
  - brows      worry / raise / lower per state
  - mouth      smile, thinking "o", or lip-synced to the speech envelope
  - hair       top mass + fringe + long side locks that sway with the head
  - accessories headset with pulsing LEDs, collar badge
  - motion     subtle head sway / tilt + breathing bob
"""

import math

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath,
                         QPen, QRadialGradient)
from PyQt6.QtWidgets import QWidget

from utils.logger import log

W, H = 400, 440
CX = W // 2
# face anchors
FACE_Y = 200      # face oval centre
EYE_Y = 180       # eye centres
MOUTH_Y = 276
NECK_Y = 292

SKIN = QColor(255, 226, 205)
SKIN_SHADE = QColor(247, 199, 174)
LINER = QColor(56, 42, 72)
BROW = QColor(78, 58, 100)
HAIR_TOP = QColor(64, 46, 100)
HAIR_MID = QColor(98, 70, 138)
HAIR_BOT = QColor(70, 52, 112)
HAIR_GLOSS = QColor(176, 138, 224)
JACKET = QColor(30, 37, 66)
JACKET_DK = QColor(22, 28, 52)
IRIS_DK = QColor(18, 110, 145)
IRIS_BRIGHT = QColor(90, 200, 215)
TEAL = QColor(40, 200, 196)

# fixed accents per state so the character never depends on internal
# animator colour plumbing
STATE_ACCENT = {
    "IDLE": QColor(40, 200, 196),
    "LISTENING": QColor(94, 214, 120),
    "THINKING": QColor(170, 120, 230),
    "SPEAKING": QColor(40, 200, 196),
    "EXECUTING": QColor(244, 172, 66),
    "SUCCESS": QColor(94, 214, 120),
    "ERROR": QColor(238, 96, 110),
}


class AnimeFace(QWidget):
    """The animated character. Reads the shared animator every frame."""

    def __init__(self, animator, parent=None):
        super().__init__(parent)
        self.animator = animator
        self.setFixedSize(W, H)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.animator.updated.connect(self.update)

    # ------------------------------------------------------------ animation
    def _state(self) -> str:
        raw = str(getattr(self.animator, "state", "IDLE")).upper()
        if raw == "PROCESSING":
            raw = "THINKING"
        return raw if raw in STATE_ACCENT else "IDLE"

    def _accent(self) -> QColor:
        return STATE_ACCENT[self._state()]

    def _t(self) -> float:
        return float(getattr(self.animator, "time", 0.0) or 0.0)

    def _blink(self) -> float:
        """Open 0..1; quick close/reopen on the shared clock."""
        c = (self._t() % 3.2) / 3.2
        if c < 0.045:
            return max(0.0, 1.0 - c / 0.045)
        if c < 0.09:
            return (c - 0.045) / 0.045
        return 1.0

    def _gaze(self):
        t = self._t()
        s = self._state()
        a = {  # (ox, oy) pixel offsets
            "IDLE": (1.6 * math.sin(t * 0.9), 1.2 * math.sin(t * 1.4)),
            "LISTENING": (2.0 * math.sin(t * 2.1), -2.0 + 1.4 * math.sin(t * 2.4)),
            "THINKING": (5.0, -6.0 + 1.2 * math.sin(t * 1.1)),
            "SPEAKING": (0, 0),
            "EXECUTING": (-2.0 + math.sin(t * 2.0), -1.0),
            "SUCCESS": (1.0 * math.sin(t * 0.8), -2.0),
            "ERROR": (0, 2.0),
        }[s]
        return int(a[0]), int(a[1])

    def _tilt(self) -> float:
        t = self._t()
        return {
            "IDLE": 0.5 * math.sin(t * 0.7),
            "LISTENING": 0.6 * math.sin(t * 1.1),
            "THINKING": -4.0 + 0.7 * math.sin(t * 1.3),
            "SPEAKING": 0.9 * math.sin(t * 2.2),
            "EXECUTING": -1.4 * math.sin(t * 1.7),
            "SUCCESS": 1.2 * math.sin(t * 0.9),
            "ERROR": -0.6,
        }[self._state()]

    def _bob(self) -> float:
        t = self._t()
        b = math.sin(t * 1.6) * 1.7
        if self._state() == "SPEAKING":
            b += 1.2 * math.sin(t * 2.9)
        return b

    def _brows(self):
        s = self._state()
        if s == "THINKING":
            return 0.26, -0.10   # left raised
        if s == "EXECUTING":
            return -0.14, -0.12  # both lowered, focused
        if s == "ERROR":
            return 0.20, 0.20
        if s == "SUCCESS":
            return 0.10, 0.10
        if s == "LISTENING":
            return 0.04, 0.04
        return -0.03, -0.05

    def _mouth_params(self):
        """(open 0..1, kind) where kind drives the lip shape."""
        s = self._state()
        if s == "SPEAKING":
            env = float(getattr(self.animator, "speech_env", 0.0) or 0.0)
            return min(1.0, max(0.0, env * 1.35)), "talk"
        if s == "THINKING":
            return 0.0, "o"
        if s == "ERROR":
            return 0.12, "frown"
        if s == "SUCCESS":
            return 0.30, "grin"
        if s == "EXECUTING":
            return 0.08, "line"
        if s == "LISTENING":
            return 0.14, "smile"
        return 0.32, "smile"

    def _eye_open(self) -> float:
        s = self._state()
        if s == "THINKING":
            return 0.82
        if s == "ERROR":
            return 0.66
        if s == "EXECUTING":
            return 0.86
        if s == "SUCCESS":
            return 0.95
        return 1.0

    def _hair_sway(self) -> float:
        t = self._t()
        return 2.6 * math.sin(t * 1.1) + 3.2 * math.sin(t * 0.6 + 1.2)

    # ---------------------------------------------------------------- paint
    def paintEvent(self, _event):
        try:
            self._paint()
        except Exception:
            log.exception("AnimeFace paint failed")

    def _paint(self):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            self._paint_body(p)
            # -------- head (rotated around the neck) --------
            tilt = math.radians(self._tilt())
            p.save()
            p.translate(CX, FACE_Y + 55)
            p.rotate(self._tilt())
            p.translate(-CX, -(FACE_Y + 55))
            self._paint_head_back(p)
            self._paint_ears(p)
            self._paint_face(p)
            self._paint_bangs(p)
            self._paint_side_locks(p)
            self._paint_eye(p, CX - 38)
            self._paint_eye(p, CX + 38)
            self._paint_brows(p)
            self._paint_nose(p)
            self._paint_blush(p)
            self._paint_mouth(p)
            self._paint_headset(p)
            self._paint_hair_clip(p)
            p.restore()
        finally:
            p.end()

    # ---------------------------------------------------------------- body
    def _paint_body(self, p: QPainter):
        bob = self._bob()
        p.save()
        p.translate(0, bob)

        # neck
        neck = QPainterPath()
        neck.moveTo(CX - 15, NECK_Y + 30)
        neck.quadTo(CX, NECK_Y + 44, CX + 15, NECK_Y + 30)
        neck.lineTo(CX + 13, H - 40)
        neck.lineTo(CX - 13, H - 40)
        neck.closeSubpath()
        p.fillPath(neck, SKIN_SHADE)

        # jacket body
        jacket = QPainterPath()
        jacket.moveTo(CX - 146, 344)
        jacket.cubicTo(CX - 128, 372, CX - 96, 404, CX - 40, 436)
        jacket.lineTo(CX + 40, 436)
        jacket.cubicTo(CX + 96, 404, CX + 128, 372, CX + 146, 344)
        jacket.cubicTo(CX + 108, 358, CX + 56, 366, CX, 366)
        jacket.cubicTo(CX - 56, 366, CX - 108, 358, CX - 146, 344)
        jacket.closeSubpath()
        g = QLinearGradient(QPointF(CX, 344), QPointF(CX, 436))
        g.setColorAt(0.0, JACKET)
        g.setColorAt(1.0, JACKET_DK)
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(g)
        p.drawPath(jacket)

        # collar V + teal trim
        collar = QPainterPath()
        collar.moveTo(CX - 64, 392)
        collar.quadTo(CX, 352, CX + 64, 392)
        collar.quadTo(CX, 414, CX - 64, 392)
        p.fillPath(collar, QColor(22, 26, 48))
        p.setPen(QPen(QColor(TEAL.red(), TEAL.green(), TEAL.blue(), 150), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        collar_t = QPainterPath()
        collar_t.moveTo(CX - 62, 391)
        collar_t.quadTo(CX, 354, CX + 62, 391)
        p.drawPath(collar_t)

        # collar badge: small glowing NOVA core
        glow = 0.55 + 0.45 * math.sin(self._t() * 2.6)
        core = QPointF(CX, 374)
        rg = QRadialGradient(core, 22)
        c = self._accent()
        a = QColor(c.red(), c.green(), c.blue(), int(70 + 60 * glow))
        rg.setColorAt(0.0, a)
        rg.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(rg)
        p.drawEllipse(core, 22, 22)
        p.setBrush(QColor(20, 24, 40))
        p.drawEllipse(core, 7, 7)
        p.setBrush(QColor(c.red(), c.green(), c.blue(), 220))
        p.drawEllipse(core, 2.6, 2.6)

        # shoulder seams (teal stitch lines)
        seam = QPen(QColor(TEAL.red(), TEAL.green(), TEAL.blue(), 90), 1.5)
        p.setPen(seam)
        p.setBrush(Qt.BrushStyle.NoBrush)
        s1 = QPainterPath()
        s1.moveTo(CX - 128, 376)
        s1.quadTo(CX - 84, 398, CX - 58, 420)
        p.drawPath(s1)
        s2 = QPainterPath()
        s2.moveTo(CX + 128, 376)
        s2.quadTo(CX + 84, 398, CX + 58, 420)
        p.drawPath(s2)
        p.restore()

    # -------------------------------------------------------------- head
    def _paint_head_back(self, p: QPainter):
        sway = self._hair_sway()
        g = QLinearGradient(QPointF(CX - 110, 20), QPointF(CX + 90, 350))
        g.setColorAt(0.0, HAIR_TOP)
        g.setColorAt(0.55, HAIR_MID)
        g.setColorAt(1.0, HAIR_BOT)
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(g)
        back = QPainterPath()
        back.moveTo(CX - 96 + sway * 0.3, 96)
        back.cubicTo(CX - 132 + sway * 0.4, 168, CX - 122, 244, CX - 96, 300)
        back.quadTo(CX - 60, 344, CX - 40, 384)
        back.quadTo(CX, 406, CX + 40, 384)
        back.quadTo(CX + 60, 344, CX + 96, 300)
        back.cubicTo(CX + 122, 244, CX + 132, 168, CX + 96 + sway * 0.3, 96)
        back.closeSubpath()
        p.drawPath(back)

    def _paint_ears(self, p: QPainter):
        for side in (-1, 1):
            ex = CX + side * 86
            p.setPen(QPen(QColor(0, 0, 0, 0)))
            p.setBrush(SKIN)
            p.drawEllipse(QPointF(ex, 208), 20, 24)
            p.setPen(QPen(QColor(0, 0, 0, 0)))
            p.setBrush(SKIN_SHADE)
            p.drawEllipse(QPointF(ex + side * 5, 210), 9, 12)
            # teal stud earring
            er = QRadialGradient(QPointF(ex + side * 2, 234), 7)
            er.setColorAt(0.0, QColor(150, 250, 246))
            er.setColorAt(1.0, QColor(20, 140, 150))
            p.setBrush(er)
            p.drawEllipse(QPointF(ex + side * 2, 234), 5, 5)

    def _paint_face(self, p: QPainter):
        face = QPainterPath()
        face.moveTo(CX, FACE_Y - 100)
        face.cubicTo(CX + 88, FACE_Y - 88, CX + 84, FACE_Y + 68,
                     CX + 72, FACE_Y + 88)
        face.cubicTo(CX + 46, FACE_Y + 112, CX - 46, FACE_Y + 112,
                     CX - 72, FACE_Y + 88)
        face.cubicTo(CX - 84, FACE_Y + 68, CX - 88, FACE_Y - 88,
                     CX, FACE_Y - 100)
        face.closeSubpath()
        g = QLinearGradient(QPointF(CX, FACE_Y - 100), QPointF(CX, FACE_Y + 110))
        g.setColorAt(0.0, QColor(255, 233, 214))
        g.setColorAt(0.6, SKIN)
        g.setColorAt(1.0, SKIN_SHADE)
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(g)
        p.drawPath(face)

        # subtle jaw shadow
        p.setPen(QPen(QColor(120, 84, 96, 40), 3, cap=Qt.PenCapStyle.RoundCap))
        sh = QPainterPath()
        sh.moveTo(CX - 58, FACE_Y + 78)
        sh.quadTo(CX, FACE_Y + 104, CX + 58, FACE_Y + 78)
        p.drawPath(sh)

        # chin highlight
        p.setPen(QPen(QColor(255, 255, 255, 60), 2, cap=Qt.PenCapStyle.RoundCap))
        ch = QPainterPath()
        ch.moveTo(CX - 20, FACE_Y + 92)
        ch.quadTo(CX, FACE_Y + 99, CX + 20, FACE_Y + 92)
        p.drawPath(ch)

    def _paint_bangs(self, p: QPainter):
        g = QLinearGradient(QPointF(CX, 14), QPointF(CX, 200))
        g.setColorAt(0.0, HAIR_TOP)
        g.setColorAt(0.5, HAIR_MID)
        g.setColorAt(1.0, HAIR_BOT)
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(g)
        bangs = QPainterPath()
        bangs.moveTo(CX - 96, 130)
        bangs.cubicTo(CX - 112, 58, CX - 60, 20, CX, 24)
        bangs.cubicTo(CX + 60, 20, CX + 112, 58, CX + 96, 130)
        # five fringe scallops over the forehead
        for i in range(5):
            sx = CX - 76 + i * 38
            tip = 150 + (14 if i % 2 else 24)  # zig-zag fringe tips
            bangs.quadTo(sx + 19, tip, sx + 38, 130)
        bangs.closeSubpath()
        p.drawPath(bangs)

        # glossy streak
        p.setPen(QPen(QColor(HAIR_GLOSS.red(), HAIR_GLOSS.green(),
                             HAIR_GLOSS.blue(), 70), 6,
                      cap=Qt.PenCapStyle.RoundCap))
        st = QPainterPath()
        st.moveTo(CX + 6, 44)
        st.quadTo(CX + 40, 66, CX + 46, 108)
        p.drawPath(st)

    def _paint_side_locks(self, p: QPainter):
        sway = self._hair_sway()
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(QColor(84, 60, 124))
        for side in (-1, 1):
            lock = QPainterPath()
            lock.moveTo(CX + side * 92, 130)
            lock.cubicTo(CX + side * 128, 216,
                         CX + side * (96 + sway), 300,
                         CX + side * 70, 366)
            lock.cubicTo(CX + side * 60, 380, CX + side * 44, 388,
                         CX + side * 40, 372)
            lock.cubicTo(CX + side * 62, 330, CX + side * 92, 240,
                         CX + side * 84, 150)
            lock.closeSubpath()
            p.drawPath(lock)

    def _paint_eye(self, p: QPainter, ex: int):
        open_ = self._blink() * self._eye_open()
        gx, gy = self._gaze()
        s = self._state()

        # eye socket shadow
        p.setPen(QPen(QColor(142, 96, 120, 40), 0))
        p.setBrush(QColor(226, 178, 160, 90))
        p.drawEllipse(QPointF(ex + gx, EYE_Y + gy), 24, 15)

        # lid/lash (upper)
        lash = QPainterPath()
        lash.moveTo(ex - 22, EYE_Y - 2)
        lash.cubicTo(ex - 12, EYE_Y - 16, ex + 12, EYE_Y - 16,
                     ex + 22, EYE_Y - 2)
        lid_h = 26 * open_
        lash.cubicTo(ex + 14, EYE_Y - 10, ex - 14, EYE_Y - 10,
                     ex - 22, EYE_Y - 2)
        lash.closeSubpath()
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(LINER)
        p.drawPath(lash)

        eye_h = max(3.0, 23 * open_)
        white = QPainterPath()
        white.moveTo(ex - 22, EYE_Y - 2)
        white.cubicTo(ex - 20, EYE_Y - eye_h * 0.35, ex - 6,
                      EYE_Y - eye_h, ex, EYE_Y - eye_h)
        white.cubicTo(ex + 6, EYE_Y - eye_h, ex + 20, EYE_Y - eye_h * 0.35,
                      ex + 22, EYE_Y - 2)
        white.cubicTo(ex + 16, EYE_Y + eye_h * 0.45, ex - 16,
                      EYE_Y + eye_h * 0.45, ex - 22, EYE_Y - 2)
        white.closeSubpath()
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(QColor(250, 250, 252))
        p.drawPath(white)

        if open_ > 0.12:
            # iris
            ir = QRadialGradient(QPointF(ex + gx, EYE_Y + gy - 1),
                                 16 + 18 * (1 - open_) * 0.5)
            ir.setColorAt(0.0, IRIS_BRIGHT)
            ir.setColorAt(0.65, QColor(36, 128, 172))
            ir.setColorAt(1.0, IRIS_DK)
            p.setPen(QPen(QColor(24, 30, 60, 220), 1.2))
            p.setBrush(ir)
            p.drawEllipse(QPointF(ex + gx, EYE_Y + gy - 1),
                          10 + 2 * open_, 10 + 3 * open_)

            # pupil
            p.setPen(QPen(QColor(0, 0, 0, 0)))
            p.setBrush(QColor(20, 26, 44))
            p.drawEllipse(QPointF(ex + 2 + gx, EYE_Y + 2 + gy), 4.2, 5.2)

            # big highlight (top-left)
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawEllipse(QPointF(ex - 4 + gx, EYE_Y - 6 + gy), 3.6, 3.6)
            # small glint (bottom-right)
            p.setBrush(QColor(255, 255, 255, 160))
            p.drawEllipse(QPointF(ex + 6 + gx, EYE_Y + 5 + gy), 1.8, 1.8)

            # focus ring while executing
            if s == "EXECUTING":
                ring = QPainterPath()
                ring.addEllipse(QPointF(ex + gx, EYE_Y + gy - 1),
                                13, 15)
                p.setPen(QPen(self._accent(), 1.6))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(ring)

        # lower lash line
        p.setPen(QPen(QColor(120, 90, 120, 80), 1.2))
        low = QPainterPath()
        low.moveTo(ex - 18, EYE_Y - 1)
        low.cubicTo(ex - 8, EYE_Y + 8, ex + 8, EYE_Y + 8,
                    ex + 18, EYE_Y - 1)
        p.drawPath(low)

        # happy squint crease when smiling
        if open_ < 0.55 and self._state() == "LISTENING":
            p.setPen(QPen(QColor(160, 110, 120, 90), 1.4,
                          cap=Qt.PenCapStyle.RoundCap))
            cr = QPainterPath()
            cr.moveTo(ex - 16, EYE_Y - 10)
            cr.quadTo(ex, EYE_Y - 18, ex + 16, EYE_Y - 10)
            p.drawPath(cr)

    def _paint_brows(self, p: QPainter):
        bL, bR = self._brows()
        for side, ang in ((0, bL), (1, bR)):
            bx = CX - 38 + side * 76
            by = EYE_Y - 22
            p.save()
            p.translate(bx, by)
            p.rotate(math.degrees(ang))
            p.setPen(QPen(BROW, 3.6, cap=Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            brow = QPainterPath()
            brow.moveTo(-15, 0)
            brow.quadTo(0, -5, 15, 0)
            p.drawPath(brow)
            p.restore()

    def _paint_nose(self, p: QPainter):
        p.setPen(QPen(QColor(188, 142, 148, 150), 1.6,
                      cap=Qt.PenCapStyle.RoundCap))
        n = QPainterPath()
        n.moveTo(CX, FACE_Y + 30)
        n.quadTo(CX - 4, FACE_Y + 44, CX, FACE_Y + 50)
        p.drawPath(n)

    def _paint_blush(self, p: QPainter):
        for side in (-1, 1):
            bx = CX + side * 54
            by = FACE_Y + 66
            t = self._t()
            strength = 0.5
            s = self._state()
            if s in ("LISTENING", "SUCCESS", "SPEAKING"):
                strength = 0.85
            if s in ("THINKING", "ERROR"):
                strength = 0.35
            alpha = int(30 + 45 * strength)
            p.setPen(QPen(QColor(244, 140, 150, alpha), 0))
            p.setBrush(QColor(244, 140, 150, alpha))
            p.drawEllipse(QPointF(bx + 2 * math.sin(t * 2.0), by), 13, 8)

    def _paint_mouth(self, p: QPainter):
        open_, kind = self._mouth_params()
        s = self._state()

        if kind == "talk":
            self._paint_mouth_open(p, open_)
            return
        if kind == "o":
            p.setPen(QPen(QColor(0, 0, 0, 0)))
            p.setBrush(QColor(150, 70, 90, 210))
            p.drawEllipse(QPointF(CX, MOUTH_Y - 8), 7, 12)
            p.setPen(QPen(QColor(190, 92, 116, 180), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(CX, MOUTH_Y - 8), 7, 12)
            return
        if kind == "frown":
            p.setPen(QPen(QColor(148, 66, 86, 230), 3,
                          cap=Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            f = QPainterPath()
            f.moveTo(CX - 17, MOUTH_Y - 4)
            f.quadTo(CX, MOUTH_Y + 8, CX + 17, MOUTH_Y - 4)
            p.drawPath(f)
            return
        if kind == "grin":
            self._paint_mouth_open(p, 0.55, grin=True)
            return
        if kind == "line":
            p.setPen(QPen(QColor(168, 84, 104, 230), 2.6,
                          cap=Qt.PenCapStyle.RoundCap))
            l = QPainterPath()
            l.moveTo(CX - 12, MOUTH_Y)
            l.quadTo(CX, MOUTH_Y + 3, CX + 12, MOUTH_Y)
            p.drawPath(l)
            return
        # smile / listening
        p.setPen(QPen(QColor(160, 76, 96, 235), 3,
                      cap=Qt.PenCapStyle.RoundCap))
        m = QPainterPath()
        m.moveTo(CX - 15, MOUTH_Y - 2)
        m.quadTo(CX, MOUTH_Y + 8 + open_ * 6, CX + 15, MOUTH_Y - 2)
        p.drawPath(m)

    def _paint_mouth_open(self, p: QPainter, open_, grin=False):
        h = 10 + 24 * open_
        w = 24 + 10 * open_
        # lip outline
        p.setPen(QPen(QColor(176, 86, 108, 230), 2,
                      cap=Qt.PenCapStyle.RoundCap))
        p.setBrush(QColor(156, 62, 86, 235))
        inner = QPainterPath()
        inner.moveTo(CX - w / 2, MOUTH_Y - 4)
        inner.cubicTo(CX - w / 2 + 8, MOUTH_Y - 4 - h * 0.3,
                      CX + w / 2 - 8, MOUTH_Y - 4 - h * 0.3,
                      CX + w / 2, MOUTH_Y - 4)
        inner.cubicTo(CX + w / 2 - 6, MOUTH_Y + h * 0.55,
                      CX - w / 2 + 6, MOUTH_Y + h * 0.55,
                      CX - w / 2, MOUTH_Y - 4)
        inner.closeSubpath()
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(QColor(120, 42, 66, 235))
        p.drawPath(inner)

        # tongue hint
        p.setBrush(QColor(204, 96, 116, 170))
        p.drawEllipse(QPointF(CX, MOUTH_Y + h * 0.22), 6, 4)

        # upper + lower lip lines
        p.setPen(QPen(QColor(192, 96, 118, 220), 2.4,
                      cap=Qt.PenCapStyle.RoundCap))
        up = QPainterPath()
        up.moveTo(CX - w / 2, MOUTH_Y - 5)
        up.quadTo(CX, MOUTH_Y - 5 - h * 0.22, CX + w / 2, MOUTH_Y - 5)
        p.drawPath(up)
        low = QPainterPath()
        low.moveTo(CX - w / 2 + 4, MOUTH_Y + h * 0.3)
        low.quadTo(CX, MOUTH_Y + h * 0.42, CX + w / 2 - 4, MOUTH_Y + h * 0.3)
        p.drawPath(low)

    def _paint_headset(self, p: QPainter):
        t = self._t()
        accent = self._accent()
        # band over the top of the hair
        band = QPainterPath()
        band.moveTo(CX - 100, 84)
        band.cubicTo(CX - 120, 196, CX + 120, 196, CX + 100, 84)
        p.setPen(QPen(QColor(28, 30, 52, 230), 4, cap=Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(band)

        # earpiece (left) hugging the ear with a boom mic toward the mouth
        ex = CX - 88
        p.setBrush(QColor(30, 33, 56))
        p.drawEllipse(QPointF(ex, 208), 16, 20)
        boom = QPainterPath()
        boom.moveTo(ex + 6, 206)
        boom.quadTo(ex - 34, 236, CX - 22, MOUTH_Y - 20)
        p.setPen(QPen(QColor(40, 44, 72), 3, cap=Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(boom)
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.setBrush(QColor(44, 48, 76))
        p.drawEllipse(QPointF(CX - 22, MOUTH_Y - 22), 3.4, 3.4)

        # mic LED near the cheek
        led = QColor(accent.red(), accent.green(), accent.blue(),
                     int(120 + 120 * (0.5 + 0.5 * math.sin(t * 5.0))))
        rg = QRadialGradient(QPointF(CX - 22, MOUTH_Y - 22), 9)
        rg.setColorAt(0.0, led)
        rg.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(rg)
        p.setPen(QPen(QColor(0, 0, 0, 0)))
        p.drawEllipse(QPointF(CX - 22, MOUTH_Y - 22), 9, 9)

        # right earpiece glow
        rx = CX + 88
        p.setBrush(QColor(30, 33, 56))
        p.drawEllipse(QPointF(rx, 208), 16, 20)
        rg2 = QRadialGradient(QPointF(rx, 208), 10)
        rg2.setColorAt(0.0, led)
        rg2.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(rg2)
        p.drawEllipse(QPointF(rx, 208), 10, 10)

    def _paint_hair_clip(self, p: QPainter):
        accent = self._accent()
        t = self._t()
        # small hair-clip nodes on the fringe seam
        for i, off in enumerate((-64, -26, 26, 66)):
            cx = CX + off
            cy = 118 + 6 * (i % 2)
            a = int(120 + 110 * (0.5 + 0.5 * math.sin(t * 3.2 + i * 1.3)))
            p.setPen(QPen(QColor(0, 0, 0, 0)))
            p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), a))
            p.drawEllipse(QPointF(cx, cy), 2.6, 2.6)