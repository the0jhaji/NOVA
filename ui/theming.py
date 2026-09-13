"""
NOVA Voice Assistant - Visual Theme
Single source of truth for NOVA's visual identity.

Palette: "Aurora Core" — deep space blues with a teal/cyan energy core,
violet processing light, and warm amber/rose for action and voice.

All widgets read state visuals from here through the shared animation
engine (see state_engine.py), so colors and motion stay consistent
across the orb, rings, waveform, and status readouts.
"""

from PyQt6.QtGui import QColor

# ---------------------------------------------------------------------------
# Core palette
# ---------------------------------------------------------------------------
PALETTE = {
    "bg_top":        (4, 7, 16),        # deepest space
    "bg_mid":        (7, 11, 24),
    "bg_bottom":     (12, 16, 34),
    "glass":         (13, 19, 38),
    "glass_border":  (122, 200, 255),
    "text_primary":  "#EAF4FF",
    "text_secondary": "#9FB4CE",
    "text_muted":    "#6B7E99",
    "accent":        (0, 233, 203),     # aurora teal
    "accent_blue":   (56, 189, 248),
    "success":       (52, 211, 153),
    "warning":       (251, 191, 36),
    "danger":        (248, 113, 113),
    "violet":        (167, 139, 250),
    "rose":          (251, 113, 133),
}

# ---------------------------------------------------------------------------
# Per-state visual definitions.
# Motion params use degrees per second; widgets derive their own patterns
# from state + the animator's shared clock (time, rotation, audio levels).
# ---------------------------------------------------------------------------
STATE_DEFS = {
    "IDLE": {
        "primary":  (0, 233, 203),
        "secondary": (56, 189, 248),
        "base_pulse": 1.0,
        "pulse_amp": 0.045,
        "pulse_speed": 40.0,      # gentle breathing
        "rotation": 12.0,
        "ring_speed": 6.0,
        "orb_text": "",
        "mode": "idle",
    },
    "LISTENING": {
        "primary":  (52, 211, 153),   # emerald - audio is live
        "secondary": (16, 185, 129),
        "base_pulse": 1.06,
        "pulse_amp": 0.09,
        "pulse_speed": 150.0,
        "rotation": 18.0,
        "ring_speed": 12.0,
        "orb_text": "",
        "mode": "listen",
    },
    "PROCESSING": {
        "primary":  (167, 139, 250),  # violet - computing
        "secondary": (124, 58, 237),
        "base_pulse": 1.02,
        "pulse_amp": 0.06,
        "pulse_speed": 240.0,
        "rotation": 52.0,
        "ring_speed": 32.0,
        "orb_text": "…",
        "mode": "process",
    },
    "SPEAKING": {
        "primary":  (251, 113, 133),  # rose - voice
        "secondary": (225, 29, 72),
        "base_pulse": 1.04,
        "pulse_amp": 0.10,
        "pulse_speed": 140.0,
        "rotation": 16.0,
        "ring_speed": 9.0,
        "orb_text": "",
        "mode": "speak",
    },
    "EXECUTING": {
        "primary":  (251, 191, 36),   # amber - action in progress
        "secondary": (245, 158, 11),
        "base_pulse": 1.05,
        "pulse_amp": 0.06,
        "pulse_speed": 190.0,
        "rotation": 26.0,
        "ring_speed": 22.0,
        "orb_text": "",
        "mode": "execute",
    },
    "SUCCESS": {
        "primary":  (52, 211, 153),   # emerald - task finished
        "secondary": (16, 185, 129),
        "base_pulse": 1.08,
        "pulse_amp": 0.10,
        "pulse_speed": 120.0,
        "rotation": 30.0,
        "ring_speed": 16.0,
        "orb_text": "",
        "mode": "success",
    },
    "ERROR": {
        "primary":  (248, 113, 113),
        "secondary": (220, 38, 38),
        "base_pulse": 0.98,
        "pulse_amp": 0.14,
        "pulse_speed": 70.0,
        "rotation": 6.0,
        "ring_speed": 3.0,
        "orb_text": "!",
        "mode": "error",
    },
}

# Legacy alias kept so any external reference to STATE_COLORS still works.
STATE_COLORS = {
    name: (QColor(*d["primary"]), QColor(*d["secondary"]), QColor(*d["primary"]))
    for name, d in STATE_DEFS.items()
}

# ---------------------------------------------------------------------------
# Color math helpers
# ---------------------------------------------------------------------------
def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_tuple(a, b, t):
    return (
        lerp(a[0], b[0], t),
        lerp(a[1], b[1], t),
        lerp(a[2], b[2], t),
    )


def lerp_color(a, b, t) -> QColor:
    r, g, bl = lerp_tuple(a, b, t)
    return QColor(int(r), int(g), int(bl))


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def rgba(*args) -> str:
    """Format an rgba() QSS string from (r,g,b,a) or a tuple."""
    if isinstance(args[0], (tuple, list)):
        args = args[0]
    return "rgba(" + ",".join(str(int(x)) for x in args) + ")"