"""
NOVA Voice Assistant - Folder Tools
open_folder / create_folder
"""

import os

from utils.logger import log
from automation.result import ToolResult
from automation.paths import resolve_user_path, ensure_dir, known_folder
from automation.verifier import path_is_dir


def open_folder(folder_path: str) -> ToolResult:
    """Open a folder in File Explorer (supports shell CLSID views)."""
    raw = str(folder_path or "").strip()
    if raw.startswith("::{"):
        try:
            os.startfile(raw)
        except Exception as e:
            log.error("open_folder (clsid) failed: %s", e)
            return ToolResult(
                tool="open_folder", success=False, verified=False,
                message="I couldn't open that location.",
                details={"error": str(e), "path": raw},
            )
        return ToolResult(
            tool="open_folder", success=True, verified=None,
            message="Opening that location.",
            details={"path": raw},
        )
    path = resolve_user_path(folder_path)
    if not path_is_dir(path):
        return ToolResult(
            tool="open_folder", success=False, verified=False,
            message=f"I couldn't open that folder because {path} doesn't exist.",
            details={"path": path},
        )
    try:
        os.startfile(path)
    except Exception as e:
        log.error("open_folder failed: %s", e)
        return ToolResult(
            tool="open_folder", success=False, verified=False,
            message=f"I couldn't open {os.path.basename(path)}.",
            details={"error": str(e), "path": path},
        )
    return ToolResult(
        tool="open_folder", success=True, verified=None,
        message=f"Opening {os.path.basename(path)}.",
        details={"path": path},
    )


def create_folder(name: str, location: str = "") -> ToolResult:
    """Create a folder. `location` may be a known-folder token or a path."""
    base = location or known_folder("desktop") or os.path.expanduser("~/Desktop")
    path = resolve_user_path(name, base=base)
    try:
        ensure_dir(path)
    except Exception as e:
        log.error("create_folder failed: %s", e)
        return ToolResult(
            tool="create_folder", success=False, verified=False,
            message=f"I couldn't create that folder.",
            details={"error": str(e), "path": path},
        )
    return ToolResult(
        tool="create_folder", success=True, verified=path_is_dir(path),
        message=f"Folder {os.path.basename(path)} is ready.",
        details={"path": path},
    )