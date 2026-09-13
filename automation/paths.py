"""
NOVA Voice Assistant - Windows Path Helpers
Resolves spoken locations (Desktop, Downloads, ...) to real Windows paths via
the Shell Known Folders API, with environment-variable fallbacks.
"""

import ctypes
import os
from ctypes import wintypes
from typing import Optional

# ---------------------------------------------------------------------------
# Known folders via SHGetKnownFolderPath (FOLDERID_*)
# ---------------------------------------------------------------------------

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


def _guid(data1: int, data2: int, data3: int, data4: bytes) -> GUID:
    g = GUID()
    g.Data1 = data1
    g.Data2 = data2
    g.Data3 = data3
    g.Data4 = (ctypes.c_byte * 8).from_buffer_copy(data4)
    return g


# FOLDERID_* GUIDs (b8{split}...)
_FOLDER_IDS: dict[str, GUID] = {
    "desktop": _guid(0xB4BFCC3A, 0xDB2C, 0x424C, bytes([0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41])),
    "downloads": _guid(0x374DE290, 0x123F, 0x4565, bytes([0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B])),
    "documents": _guid(0xFDD39AD0, 0x238F, 0x46AF, bytes([0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7])),
    "pictures": _guid(0x33E28130, 0x4E1E, 0x4676, bytes([0x83, 0x5A, 0x98, 0x39, 0x5C, 0x3B, 0xC3, 0xBB])),
    "music": _guid(0x4BD8D571, 0x6D19, 0x48D3, bytes([0xBE, 0x97, 0x42, 0x22, 0x20, 0x08, 0x0E, 0x43])),
    "videos": _guid(0x18989B1D, 0x99B5, 0x455B, bytes([0x84, 0x1C, 0xAB, 0x7C, 0x74, 0xE4, 0xDD, 0xFC])),
}

# Spoken aliases -> normalized key
FOLDER_ALIASES = {
    "desktop": "desktop",
    "downloads": "downloads",
    "download": "downloads",
    "documents": "documents",
    "document": "documents",
    "pictures": "pictures",
    "mypictures": "pictures",
    "my pictures": "pictures",
    "music": "music",
    "videos": "videos",
    "video": "videos",
}


def known_folder(key: str) -> Optional[str]:
    """Return the absolute path of a well-known user folder."""
    gid = _FOLDER_IDS.get(key.lower())
    if gid is None:
        return None
    try:
        buf = ctypes.c_wchar_p()
        hr = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(gid), 0, None, ctypes.byref(buf)
        )
        if hr == 0 and buf.value:
            result = buf.value
            ctypes.windll.ole32.CoTaskMemFree(buf)  # type: ignore[attr-defined]
            return result
    except Exception:
        pass
    return None


def default_folder(key: str) -> str:
    """Known folder path or a safe fallback under the user profile."""
    got = known_folder(key)
    if got:
        return got
    home = os.path.expanduser("~")
    return {
        "desktop": os.path.join(home, "Desktop"),
        "downloads": os.path.join(home, "Downloads"),
        "documents": os.path.join(home, "Documents"),
        "pictures": os.path.join(home, "Pictures"),
        "music": os.path.join(home, "Music"),
        "videos": os.path.join(home, "Videos"),
    }.get(key.lower(), home)


def user_home() -> str:
    return os.path.expanduser("~")


# ---------------------------------------------------------------------------
# Spoken-location resolution
# ---------------------------------------------------------------------------

def resolve_location(text: str) -> Optional[str]:
    """
    Find a location token in spoken text and return its path.

    Recognizes: Desktop, Downloads/Documents, Pictures, Music, Videos
    (English + Latin/Hinglish spellings). Returns None if none mentioned.
    """
    lowered = (text or "").lower()
    for alias, key in FOLDER_ALIASES.items():
        if lowered == alias or alias in lowered.split():
            return default_folder(key)
    for canonical in ("desktop", "downloads", "documents", "pictures",
                      "music", "videos"):
        if canonical in lowered:
            return default_folder(canonical)
    return None


def resolve_user_path(raw: str, base: Optional[str] = None) -> str:
    """
    Turn a user-supplied path fragment into an absolute Windows path.
    - Quoted strings are stripped.
    - ~ and %USERPROFILE% expand.
    - Relative paths resolve against `base` (default: Desktop).
    """
    text = str(raw or "").strip().strip('"').strip("'")
    if not text:
        return (base or default_folder("desktop"))
    if text.startswith("%"):
        text = os.path.expandvars(text)
    if text == "~":
        text = os.path.expanduser("~")
    if os.path.isabs(text):
        return os.path.abspath(text)
    base = base or default_folder("desktop")
    return os.path.abspath(os.path.join(base, text))


def ensure_dir(path: str) -> str:
    """Create the directory chain if missing and return the absolute path."""
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)