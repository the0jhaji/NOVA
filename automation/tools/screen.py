"""
NOVA Voice Assistant - Screenshot Tool
take_screenshot — captures the screen to PNG using Pillow's ImageGrab.
"""

import os
from datetime import datetime

from config import config
from utils.logger import log
from automation.result import ToolResult
from automation.verifier import path_is_file
from automation.paths import ensure_dir


def _screenshot_dir() -> str:
    if config.automation.screenshot_dir:
        return ensure_dir(config.automation.screenshot_dir)
    from automation.paths import known_folder
    base = known_folder("pictures") or os.path.expanduser("~/Pictures")
    return ensure_dir(os.path.join(base, "NOVA Screenshots"))


def take_screenshot() -> ToolResult:
    try:
        from PIL import ImageGrab
        image = ImageGrab.grab(all_screens=True)
        if image is None:
            raise RuntimeError("ImageGrab returned no image")
    except Exception as e:
        log.error("screenshot capture failed: %s", e)
        return ToolResult(
            tool="take_screenshot", success=False, verified=False,
            message="I couldn't take a screenshot right now.",
            details={"error": str(e)},
        )
    folder = _screenshot_dir()
    filename = "nova_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
    path = os.path.join(folder, filename)
    try:
        image.save(path, format="PNG")
    except Exception as e:
        log.error("screenshot save failed: %s", e)
        return ToolResult(
            tool="take_screenshot", success=False, verified=False,
            message="I captured the screen but couldn't save it.",
            details={"error": str(e)},
        )
    ok = path_is_file(path) and os.path.getsize(path) > 0
    return ToolResult(
        tool="take_screenshot", success=ok, verified=ok,
        message=f"Screenshot saved to {os.path.basename(folder)}.",
        details={"path": path},
    )