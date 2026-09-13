"""
NOVA Voice Assistant - Verification Helpers
Small, non-shell utilities used by tools to check whether an action actually
succeeded (process existence, path state, volume readback).
"""

import subprocess
import time
from typing import Optional

from utils.logger import log


def process_exists(process_name: str, timeout: float = 4.0) -> bool:
    """
    True if a process with the given image name is running.

    Uses tasklist (no shell, no admin rights needed). The name is matched
    against OUR fixed image-name parameter, never user shell input.
    """
    name = process_name.lower().rstrip(".exe") + ".exe"
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
            capture_output=True, text=True, timeout=timeout,
        )
        return name.lower() in out.stdout.lower()
    except Exception as e:
        log.warning("process_exists(%s) failed: %s", name, e)
        return False


def wait_for_process(process_name: str, tries: int = 10, delay: float = 0.25) -> bool:
    """Poll tasklist for a process to appear. Returns True when found."""
    for _ in range(tries):
        if process_exists(process_name, timeout=2.0):
            return True
        time.sleep(delay)
    return False


def wait_for_process_gone(process_name: str, tries: int = 8, delay: float = 0.3) -> bool:
    """Poll tasklist for a process to disappear. Returns True when gone."""
    for _ in range(tries):
        if not process_exists(process_name, timeout=2.0):
            return True
        time.sleep(delay)
    return not process_exists(process_name, timeout=2.0)


def path_is_dir(path: str) -> bool:
    import os
    return os.path.isdir(path)


def path_is_file(path: str) -> bool:
    import os
    return os.path.isfile(path)


def path_gone(path: str) -> bool:
    import os
    return not os.path.exists(path)


def volume_level() -> Optional[float]:
    """
    Current master volume scalar 0..1 via the Core Audio COM API (pycaw).
    Returns None when unavailable.
    """
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        if devices is None:
            return None
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        return float(volume.GetMasterVolumeLevelScalar())
    except Exception as e:
        log.warning("volume_level() failed: %s", e)
        return None