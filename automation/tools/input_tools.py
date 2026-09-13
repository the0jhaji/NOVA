"""
NOVA Voice Assistant - Input Tools
type_text / press_key / mouse_click

These inject keystrokes and clicks into whatever window currently has focus.
They run only when the user issued a specific command for them.
"""

from typing import Optional

from utils.logger import log
from automation.result import ToolResult

# Failsafe: pyautogui normally aborts when it hits the screen corner.
_SAFE_INTERVAL = 0.02

_KEY_ALIASES = {
    "enter": "enter", "return": "enter",
    "esc": "esc", "escape": "esc",
    "space": "space", "spaces": "space",
    "tab": "tab",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "ctrl": "ctrl", "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "win": "win", "windows": "win", "winleft": "winleft", "winright": "winright",
    "delete": "delete", "del": "delete",
    "backspace": "backspace", "back": "backspace",
    "home": "home", "end": "end",
    "pageup": "pageup", "pagedown": "pagedown",
    "pgup": "pageup", "pgdn": "pagedown",
    "printscreen": "printscreen", "prtsc": "printscreen",
    "capslock": "capslock", "numlock": "numlock",
    "plus": "+", "minus": "-",
}
_MODIFIERS = {"ctrl", "alt", "shift", "win", "winleft", "winright"}


def _normalise_key(token: str) -> Optional[str]:
    t = token.strip().lower()
    if t.isdigit():
        return t
    if t.startswith("f") and 1 <= int(t[1:]) <= 24:
        return t.upper()
    return _KEY_ALIASES.get(t)


def _parse_keys(chord: str) -> Optional[list[str]]:
    """'ctrl+s' / 'ctrl plus s' / 'alt tab' -> ['ctrl','s']"""
    parts = [p for p in chord.replace(" plus ", "+").split("+") if p.strip()]
    keys = [_normalise_key(p) for p in parts]
    if not keys or any(k is None for k in keys):
        return None
    return keys  # type: ignore[return-value]


def type_text(text: str) -> ToolResult:
    """Type text into the focused window (clipboard fallback for Unicode)."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        if text.isascii():
            pyautogui.write(text, interval=_SAFE_INTERVAL)
        else:
            import subprocess
            # clipboard via PowerShell (native, no extra dependency)
            encoded = text.replace("'", "''")
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Set-Clipboard -Value ('" + encoded + "')"],
                capture_output=True, timeout=15,
            )
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("right")
    except Exception as e:
        log.error("type_text failed: %s", e)
        return ToolResult(
            tool="type_text", success=False, verified=False,
            message="I couldn't type that into the current window.",
            details={"error": str(e)},
        )
    return ToolResult(
        tool="type_text", success=True, verified=None,
        message="Typed it into the current window.",
    )


def press_key(keys: list[str]) -> ToolResult:
    """Send one keystroke or a chord (e.g. ctrl+n, alt+tab)."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        names = []
        mods = []
        for k in keys:
            if k in _MODIFIERS:
                mods.append(k)
            else:
                names.append(k)
        if not names:
            mods and mods.pop()
            names = [mods.pop()] if mods else ["enter"]
        if len(names) == 1 and mods:
            pyautogui.hotkey(*mods, names[0])
        else:
            for n in names:
                pyautogui.press(n)
            for m in mods:
                pyautogui.press(m)
    except Exception as e:
        log.error("press_key failed: %s", e)
        return ToolResult(
            tool="press_key", success=False, verified=False,
            message="I couldn't send that key.",
            details={"error": str(e)},
        )
    return ToolResult(
        tool="press_key", success=True, verified=None,
        message="Key pressed.",
    )


def mouse_click(x: Optional[int] = None, y: Optional[int] = None,
                double: bool = False) -> ToolResult:
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        if double:
            pyautogui.doubleClick(x, y) if (x is not None and y is not None) else pyautogui.doubleClick()
        else:
            pyautogui.click(x, y) if (x is not None and y is not None) else pyautogui.click()
    except Exception as e:
        log.error("mouse_click failed: %s", e)
        return ToolResult(
            tool="mouse_click", success=False, verified=False,
            message="I couldn't perform that click.",
            details={"error": str(e)},
        )
    return ToolResult(
        tool="mouse_click", success=True, verified=None,
        message="Clicked.",
    )