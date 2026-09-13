"""
NOVA Voice Assistant - System Tools
volume_control — set / adjust / mute the master volume via Core Audio (pycaw).
"""

from typing import Optional

from utils.logger import log
from automation.result import ToolResult
from automation.verifier import volume_level


def _get_volume_interface():
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    devices = AudioUtilities.GetSpeakers()
    if devices is None:
        raise RuntimeError("No audio endpoint found")
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return interface.QueryInterface(IAudioEndpointVolume)


def _set_percent(percent: float) -> bool:
    interface = _get_volume_interface()
    scalar = max(0.0, min(1.0, percent / 100.0))
    interface.SetMasterVolumeLevelScalar(scalar, None)
    return True


def _toggle_mute(state: bool) -> bool:
    interface = _get_volume_interface()
    interface.SetMute(1 if state else 0, None)
    return True


def volume_control(action: str = "set", value: Optional[float] = None,
                   mute: Optional[bool] = None) -> ToolResult:
    """
    Actions:
      set        -> set to value% (value 0..100)
      up/down    -> adjust by value points from the current level
      mute/unmute-> toggle mute
    """
    try:
        if mute is not None:
            _toggle_mute(mute)
            return ToolResult(
                tool="volume_control", success=True,
                verified=volume_level() is not None,
                message="Volume muted." if mute else "Volume unmuted.",
                details={"muted": mute},
            )

        current = volume_level()
        clamp = lambda v: max(0.0, min(100.0, v))

        if action == "set":
            if value is None:
                return ToolResult(
                    tool="volume_control", success=False, verified=False,
                    message="I couldn't set the volume — no level given.",
                )
            _set_percent(clamp(value))
            target = clamp(value)
        elif action == "up":
            base = (current or 0.0) * 100.0
            target = clamp(base + (value or 10))
            _set_percent(target)
        elif action == "down":
            base = (current or 0.0) * 100.0
            target = clamp(base - (value or 10))
            _set_percent(target)
        else:
            return ToolResult(
                tool="volume_control", success=False, verified=False,
                message="I couldn't change the volume.",
            )
    except Exception as e:
        log.error("volume_control failed: %s", e)
        return ToolResult(
            tool="volume_control", success=False, verified=False,
            message="I couldn't change the volume right now.",
            details={"error": str(e)},
        )

    readback = volume_level()
    verified = readback is not None and abs(readback * 100.0 - target) <= 3.0
    return ToolResult(
        tool="volume_control", success=True, verified=verified,
        message=f"Volume is now {target:.0f} percent." if not verified else
                f"Volume is now {target:.0f} percent.",
        details={"target": target, "readback": readback},
    )