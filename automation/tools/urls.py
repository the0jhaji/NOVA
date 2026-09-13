"""
NOVA Voice Assistant - URL Tool
open_url — opens a web URL in the default browser via ShellExecute.
"""

import re

from utils.logger import log
from automation.result import ToolResult

_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)


def normalise_url(url: str) -> str:
    text = (url or "").strip().strip('"')
    if not text:
        return ""
    if " " in text and not _SCHEME_RE.match(text):
        # Treat as a search query -> default search engine
        from urllib.parse import quote
        return "https://www.google.com/search?q=" + quote(text)
    if not _SCHEME_RE.match(text):
        return "https://" + text
    return text


def open_url(url: str) -> ToolResult:
    target = normalise_url(url)
    if not target:
        return ToolResult(
            tool="open_url", success=False, verified=False,
            message="I couldn't open that because no address was recognised.",
        )
    try:
        import ctypes
        result = ctypes.windll.shell32.ShellExecuteW(None, "open", target, None, None, 5)
        if result <= 32:
            raise RuntimeError(f"ShellExecuteW returned {result}")
    except Exception as e:
        log.error("open_url failed (%s): %s", target, e)
        return ToolResult(
            tool="open_url", success=False, verified=False,
            message="I couldn't open that page.",
            details={"error": str(e), "url": target},
        )
    return ToolResult(
        tool="open_url", success=True, verified=None,
        message=f"Opening {target.replace('https://', '')}.",
        details={"url": target},
    )