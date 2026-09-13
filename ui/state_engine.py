"""
NOVA Voice Assistant - State Animation Engine
A single shared animation clock that drives every visual element.

Why one engine?
- Ensures the orb, rings, waveform and status bar move in sync.
- Smooths color/speed transitions between states with damping
  (frame-rate independent), so state changes feel graceful instead
  of snapping.
- Central noise generator simulates a speech envelope so the waveform
  visibly "talks" during TTS without tapping the actual audio stream.

Performance: one 30 ms timer (~33 fps), no per-widget timers. Widgets
simply repaint when `updated` fires and read current values in paint().
"""

import math
import random

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor

from ui import theming
from ui.theming import STATE_DEFS, lerp


class NovaStateAnimator(QObject):
    """Central animator: owns the animation clock and smoothed state visuals."""

    updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "IDLE"
        self._time = 0.0
        self._dt = 0.0

        # Lerped color channels: current -> target on every tick.
        self._cur = _defaults(STATE_DEFS["IDLE"])
        self._tgt = _defaults(STATE_DEFS["IDLE"])

        self._rot = 0.0          # orb rotation angle (deg)
        self._ring = 0.0         # ring rotation angle (deg)
        self._pulse = 0.0        # smoothed base pulse amplitude 0..1
        self._audio = 0.0        # smoothed mic input level 0..1
        self._speech = 0.0       # simulated TTS envelope 0..1
        self._progress = 0.0     # executing task progress 0..1
        self._orb_text = ""      # override text shown inside orb

        self._phases = {}        # deterministic per-particle phases

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    # ------------------------------------------------------------------ API
    @property
    def state(self) -> str:
        return self._state

    @property
    def time(self) -> float:
        return self._time

    @property
    def dt(self) -> float:
        return self._dt

    @property
    def rotation(self) -> float:
        return self._rot

    @property
    def ring_angle(self) -> float:
        return self._ring

    @property
    def pulse_amp(self) -> float:
        return self._pulse

    @property
    def audio_level(self) -> float:
        return self._audio

    @property
    def speech_env(self) -> float:
        return self._speech

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def mode(self) -> str:
        return STATE_DEFS[self._state]["mode"]

    @property
    def primary(self) -> QColor:
        return QColor(
            int(self._cur["cr"]), int(self._cur["cg"]),
            int(self._cur["cb"]), int(self._cur["ca"]),
        )

    @property
    def secondary(self) -> QColor:
        return QColor(
            int(self._cur["sr"]), int(self._cur["sg"]),
            int(self._cur["sb"]), int(self._cur["sa"]),
        )

    @property
    def orb_text(self) -> str:
        return self._orb_text or self._target_text

    @property
    def _target_text(self) -> str:
        return STATE_DEFS[self._state]["orb_text"]

    def set_state(self, state: str):
        if state not in STATE_DEFS:
            log_fallback(state)
            state = "ERROR"
        if state == self._state:
            return
        self._state = state
        self._tgt = _defaults(STATE_DEFS[state])
        if state != "EXECUTING":
            self._progress = 0.0
        self.updated.emit()

    def set_audio_level(self, level: float):
        """Live mic input 0..1 (LISTENING waveform reaction)."""
        self._audio_level_in = max(0.0, min(1.0, level))

    def set_progress(self, value: float):
        """Task progress 0..1 (EXECUTING ring)."""
        self._progress = max(0.0, min(1.0, value))

    def set_orb_text(self, text: str):
        self._orb_text = text
        self.updated.emit()

    def clear_orb_text(self):
        self._orb_text = ""

    def phase_for(self, key: int, salt: float) -> float:
        """Deterministic pseudo-phase per key, used for particle orbits."""
        return self._phases.get(key, key * 2.399963 + salt * self._time)

    # ------------------------------------------------------------------ loop
    def _tick(self):
        self._time += 0.030
        self._dt = 0.030

        state = STATE_DEFS[self._state]
        damp = 1.0 - math.exp(-self._dt * 9.0)

        # Lerp color channels toward current state target (smooth transitions).
        # Note: tuples are unpacked first — smooth_key only accepts scalars.
        cr, cg, cb = state["primary"]
        sr, sg, sb = state["secondary"]
        for key, target in (
            ("cr", cr), ("cg", cg), ("cb", cb),
            ("sr", sr), ("sg", sg), ("sb", sb),
        ):
            smooth_key(key, target, self._cur, self._tgt, damp)
        smooth_key("ca", 235, self._cur, self._tgt, damp)
        smooth_key("sa", 235, self._cur, self._tgt, damp)

        # Continuous rotation driven by the state's angular speed.
        self._rot = (self._rot + state["rotation"] * self._dt) % 360.0
        self._ring = (self._ring + state["ring_speed"] * self._dt) % 360.0

        # Pulse amplitude: base breathing + state speed.
        pulse_target = (
            state["base_pulse"]
            + state["pulse_amp"] * math.sin(math.radians(state["pulse_speed"]) * self._time)
        )
        self._pulse += (pulse_target - self._pulse) * damp

        # Smooth the mic audio level.
        val = getattr(self, "_audio_level_in", 0.0)
        self._audio += (val - self._audio) * (1.0 - math.exp(-self._dt * 14.0))

        # Speech envelope: animated pseudo-signal while speaking, else decays.
        if self._state == "SPEAKING":
            target = 0.35 + 0.65 * abs(math.sin(self._time * 7.0))
            target = max(0.05, min(1.0, target * (0.6 + 0.4 * random.random())))
            self._speech += (target - self._speech) * (1.0 - math.exp(-self._dt * 20.0))
        else:
            self._speech += (0.0 - self._speech) * (1.0 - math.exp(-self._dt * 10.0))

        self.updated.emit()


def _defaults(defn: dict) -> dict:
    r, g, b = defn["primary"]
    sr, sg, sb = defn["secondary"]
    return {
        "cr": r, "cg": g, "cb": b, "ca": 0.0,
        "sr": sr, "sg": sg, "sb": sb, "sa": 0.0,
    }


def smooth_key(key: str, target, cur: dict, tgt: dict, damp: float):
    """Move one visual channel toward its target value."""
    cur[key] = lerp(cur[key], target, damp)


def log_fallback(state: str):
    from utils.logger import log
    log.warning("Unknown UI state %r, falling back to ERROR", state)