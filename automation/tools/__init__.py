"""
NOVA Voice Assistant - Tool Implementations
Registry mapping tool names to their audited implementations.

Every entry is a callable `fn(params: dict) -> ToolResult`. The registry is
plain data, so tests can swap any tool for a mock.
"""

from typing import Callable

from automation.result import ToolResult
from automation.tools import apps as _apps, folders as _folders, files as _files
from automation.tools import urls as _urls, screen as _screen
from automation.tools import input_tools as _input, systools as _systools
from automation.tools import install as _install


def _dispatch(params: dict) -> ToolResult:
    """Route a single params dict to the matching audited tool function."""
    tool = params.get("tool", "")
    if tool == "open_application":
        return _apps.open_application(params.get("name", ""))
    if tool == "close_application":
        return _apps.close_application(params.get("name", ""))
    if tool == "open_url":
        return _urls.open_url(params.get("url", ""))
    if tool == "open_folder":
        return _folders.open_folder(params.get("path", ""))
    if tool == "create_folder":
        return _folders.create_folder(
            params.get("name", ""),
            params.get("location", "") or params.get("path", ""),
        )
    if tool == "create_file":
        return _files.create_file(
            params.get("name", ""),
            params.get("location", ""),
            params.get("content", ""),
        )
    if tool == "move_file":
        return _files.move_file(params.get("source", ""), params.get("destination", ""))
    if tool == "copy_file":
        return _files.copy_file(params.get("source", ""), params.get("destination", ""))
    if tool == "rename_file":
        return _files.rename_file(params.get("source", ""), params.get("new_name", ""))
    if tool == "search_files":
        return _files.search_files(params.get("query", "*"), params.get("location", ""))
    if tool == "delete_file":
        return _files.delete_file(params.get("path", ""), bool(params.get("is_dir", False)))
    if tool == "take_screenshot":
        return _screen.take_screenshot()
    if tool == "type_text":
        return _input.type_text(params.get("text", ""))
    if tool == "press_key":
        return _input.press_key(params.get("keys") or [])
    if tool == "mouse_click":
        return _input.mouse_click(
            params.get("x"), params.get("y"), bool(params.get("double", False))
        )
    if tool == "volume_control":
        return _systools.volume_control(
            params.get("action", "set"), params.get("value"), params.get("mute")
        )
    if tool == "install_software":
        return _install.install_software(params.get("package", ""))
    return ToolResult(
        tool=tool or "unknown", success=False, verified=False,
        message="That tool is not available.",
    )


def build_registry() -> dict[str, Callable[[dict], ToolResult]]:
    """Return a fresh registry: tool name -> callable(params) -> ToolResult."""
    return {name: _dispatch for name in _ALL_TOOLS}


_ALL_TOOLS = [
    "open_application", "close_application",
    "open_url", "open_folder", "create_folder",
    "create_file", "move_file", "copy_file", "rename_file",
    "search_files", "delete_file", "take_screenshot",
    "type_text", "press_key", "mouse_click",
    "volume_control", "install_software",
]


__all__ = ["build_registry", "_ALL_TOOLS"]