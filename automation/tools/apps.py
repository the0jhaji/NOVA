"""
NOVA Voice Assistant - Application Tools
open_application / close_application
"""

import json
import os
import shutil
import subprocess
from typing import Optional

from config import config
from utils.logger import log
from automation.result import ToolResult
from automation.verifier import wait_for_process, wait_for_process_gone, process_exists

# ---------------------------------------------------------------------------
# Known applications
# ---------------------------------------------------------------------------

# exe  -> fixed image name used only for verification.
# paths -> candidate absolute locations (checked in order, first existing wins).
# urn  -> store / shell applications launched via ShellExecuteW.
KNOWN_APPS: dict[str, dict] = {
    "chrome": {"exe": "chrome.exe", "paths": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]},
    "google chrome": {"exe": "chrome.exe", "paths": []},
    "edge": {"exe": "msedge.exe", "paths": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]},
    "microsoft edge": {"exe": "msedge.exe", "paths": []},
    "notepad": {"exe": "notepad.exe", "paths": [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "notepad.exe")]},
    "calculator": {"exe": "calc.exe", "paths": [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "calc.exe")]},
    "paint": {"exe": "mspaint.exe", "paths": [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "mspaint.exe")]},
    "wordpad": {"exe": "write.exe", "paths": []},
    "file explorer": {"exe": "explorer.exe", "paths": []},
    "explorer": {"exe": "explorer.exe", "paths": []},
    "command prompt": {"exe": "cmd.exe", "paths": [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "cmd.exe")]},
    "cmd": {"exe": "cmd.exe", "paths": []},
    "powershell": {"exe": "powershell.exe", "paths": [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")]},
    "terminal": {"exe": "WindowsTerminal.exe", "paths": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "WindowsTerminal.exe"),
    ]},
    "vs code": {"exe": "Code.exe", "paths": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ]},
    "vscode": {"exe": "Code.exe", "paths": []},
    "visual studio code": {"exe": "Code.exe", "paths": []},
    "word": {"exe": "WINWORD.EXE", "paths": []},
    "excel": {"exe": "EXCEL.EXE", "paths": []},
    "powerpoint": {"exe": "POWERPNT.EXE", "paths": []},
    "outlook": {"exe": "OUTLOOK.EXE", "paths": []},
    "control panel": {"exe": "control.exe", "paths": [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "control.exe")]},
    "snipping tool": {"exe": "SnippingTool.exe", "paths": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "SnippingTool.exe"),
    ]},
    "settings": {"urn": "ms-settings:"},
    "windows settings": {"urn": "ms-settings:"},
    "photos": {"urn": "ms-photos:"},
}

# Devanagari / romanised aliases for spoken names
APP_ALIASES = {
    "क्रोम": "chrome",
    "नोटपैड": "notepad",
    "कैलकुलेटर": "calculator",
    "पेंट": "paint",
    "वर्ड": "word",
    "एक्सेल": "excel",
    "पावरपॉइंट": "powerpoint",
    "वी": "vs code",
    "वीएस कोड": "vs code",
    "कोड": "vs code",
    "स्निपिंग टूल": "snipping tool",
    "टर्मिनल": "terminal",
    "कमांड प्रॉम्प्ट": "command prompt",
    "फाइल एक्सप्लोरर": "file explorer",
    "फोटो": "photos",
    "सेटिंग्स": "settings",
    "एज": "edge",
    "एडज": "edge",
}

# Process names that NOVA refuses to close, even on SAFE classification.
PROTECTED_PROCESSES = {
    "explorer.exe", "svchost.exe", "winlogon.exe", "csrss.exe",
    "services.exe", "taskhostw.exe", "dwm.exe", "system",
    "lsass.exe", "wininit.exe",
}

_CUSTOM_APPS: Optional[dict] = None


def _load_custom_apps() -> dict:
    """Load user app overrides from APPS_CONFIG_FILE (JSON)."""
    global _CUSTOM_APPS
    if _CUSTOM_APPS is not None:
        return _CUSTOM_APPS
    _CUSTOM_APPS = {}
    try:
        path = config.automation.apps_config
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            _CUSTOM_APPS = {str(k).lower(): v for k, v in (data.get("apps") or {}).items()}
    except Exception as e:
        log.warning("Could not load apps config: %s", e)
    return _CUSTOM_APPS


def normalise_app_name(name: str) -> str:
    return (name or "").strip().lower()

def resolve_app(name: str) -> Optional[dict]:
    """
    Resolve a spoken app name to a launch spec:
      {"spec": "exe",  "cmd": [...tokens], "verify": "<image>.exe"}  -> Popen
      {"spec": "urn",  "urn": "ms-settings:",          "verify": None}
      {"spec": "path", "path": "C:\\...",              "verify": "<image>.exe"}
    """
    key = normalise_app_name(name)
    key = APP_ALIASES.get(key, key)
    if not key:
        return None

    custom = _load_custom_apps().get(key)
    if custom:
        if isinstance(custom, str):
            custom = {"cmd": custom.split(" ")[:1]}
        cmd = custom.get("cmd") or custom.get("command")
        verify = custom.get("verify")
        if isinstance(cmd, str):
            cmd = [cmd]
        if cmd:
            return {"spec": "exe", "cmd": cmd, "verify": verify or os.path.basename(cmd[0])}

    known = KNOWN_APPS.get(key)
    if known:
        if known.get("urn"):
            return {"spec": "urn", "urn": known["urn"], "verify": None}
        exe = known.get("exe")
        for cand in known.get("paths") or []:
            if os.path.isfile(cand):
                return {"spec": "path", "path": cand, "verify": known.get("verify") or (exe or os.path.basename(cand))}
        if exe:
            located = shutil.which(exe)
            if located:
                return {"spec": "path", "path": located, "verify": known.get("verify") or exe}
            return {"spec": "exe", "cmd": [exe], "verify": known.get("verify") or exe}

    # Generic fallback: an executable on PATH (gated by name validity).
    safe = key
    if any(ch in safe for ch in "\\/:\"'<>|*?;") or " " in safe.strip():
        return None
    located = shutil.which(safe)
    if located:
        return {"spec": "path", "path": located, "verify": os.path.basename(located)}
    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def _launch_spec(spec: dict) -> None:
    if spec["spec"] == "urn":
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(None, "open", spec["urn"], None, None, 5)
        return
    if spec["spec"] == "path":
        # start a detached process, no shell
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [spec["path"]],
            close_fds=True,
            creationflags=flags,
            cwd=os.path.expanduser("~"),
        )
        return
    # spec == "exe"
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    DETACHED_PROCESS = 0x00000008
    subprocess.Popen(
        spec["cmd"],
        close_fds=True,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        cwd=os.path.expanduser("~"),
    )


def _verified_name(spec: dict, app_name: str) -> Optional[str]:
    verify = spec.get("verify")
    return verify if verify else None


def open_application(app_name: str) -> ToolResult:
    """Open a named application. Launches the existing binary; never a shell."""
    spec = resolve_app(app_name)
    if spec is None:
        return ToolResult(
            tool="open_application", success=False,
            message=f"I know how to open {app_name!r} — add it to the apps configuration.",
            verified=False,
        )
    try:
        _launch_spec(spec)
    except Exception as e:
        log.error("Failed to launch %s: %s", app_name, e)
        return ToolResult(
            tool="open_application", success=False,
            message=f"I couldn't open {app_name} because it could not be started.",
            verified=False, details={"error": str(e)},
        )
    verify = _verified_name(spec, app_name)
    if verify and wait_for_process(verify, tries=8, delay=0.25):
        return ToolResult(
            tool="open_application", success=True, verified=True,
            message=f"{app_name.title()} is now open.",
            details={"process": verify},
        )
    # Store apps (urn) or short-lived processes can't be confirmed via tasklist.
    return ToolResult(
        tool="open_application", success=True, verified=None,
        message=f"I opened {app_name}.",
        details={"best_effort": True},
    )


def close_application(app_name: str) -> ToolResult:
    """Close an application gracefully by its process image name."""
    spec = resolve_app(app_name)
    if spec is None:
        return ToolResult(
            tool="close_application", success=False,
            message=f"I don't recognise {app_name!r}, so I can't close it.",
            verified=False,
        )
    verify = spec.get("verify")
    if not verify:
        # URNs launch via shell; try a reasonable image name guess.
        return ToolResult(
            tool="close_application", success=False,
            message=f"I can't reliably close {app_name} from here.",
            verified=False,
        )
    if verify.lower() in PROTECTED_PROCESSES:
        return ToolResult(
            tool="close_application", success=False,
            message=f"I won't close {app_name} — it's a system process.",
            verified=False,
        )
    try:
        subprocess.run(
            ["taskkill", "/IM", verify, "/T"],
            capture_output=True, text=True, timeout=12,
        )
    except Exception as e:
        log.error("taskkill failed for %s: %s", verify, e)
        return ToolResult(
            tool="close_application", success=False,
            message=f"I couldn't close {app_name} because the close request failed.",
            verified=False, details={"error": str(e)},
        )
    if wait_for_process_gone(verify, tries=8, delay=0.3):
        return ToolResult(
            tool="close_application", success=True, verified=True,
            message=f"{app_name.title()} has been closed.",
            details={"process": verify},
        )
    return ToolResult(
        tool="close_application", success=False,
        message=f"{app_name.title()} is still running and may have unsaved work. Please close it manually.",
        verified=False,
        details={"process": verify},
    )


def known_app_basenames() -> list[str]:
    return sorted({v.get("exe", "") for v in KNOWN_APPS.values() if v.get("exe")})