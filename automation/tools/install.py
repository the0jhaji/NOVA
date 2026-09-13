"""
NOVA Voice Assistant - Software Installation Tool
install_software — installs a package with winget (Windows Package Manager).
Always CONFIRMATION_REQUIRED; never runs silently.
"""

import subprocess
from typing import Optional

from utils.logger import log
from automation.result import ToolResult


def install_software(package: str) -> ToolResult:
    name = (package or "").strip().strip('"')
    if not name:
        return ToolResult(
            tool="install_software", success=False, verified=False,
            message="I couldn't install that — no package name was given.",
        )
    try:
        # winget resolves the name; we never pass a command line, only the name.
        proc = subprocess.run(
            ["winget", "install", "--name", name,
             "--accept-source-agreements", "--accept-package-agreements"],
            capture_output=True, text=True, timeout=420,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            tool="install_software", success=False, verified=False,
            message="The installation timed out.",
            details={"package": name},
        )
    except Exception as e:
        log.error("winget install failed: %s", e)
        return ToolResult(
            tool="install_software", success=False, verified=False,
            message=f"I couldn't install {name} because winget isn't available.",
            details={"error": str(e)},
        )

    verified = _is_installed_width_winget(name)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode == 0 and verified:
        return ToolResult(
            tool="install_software", success=True, verified=True,
            message=f"{name} has been installed.",
            details={"package": name},
        )
    if proc.returncode == 0:
        return ToolResult(
            tool="install_software", success=True, verified=None,
            message=f"winget finished installing {name}.",
            details={"package": name},
        )
    return ToolResult(
        tool="install_software", success=False, verified=False,
        message=f"I couldn't install {name}. " +
                ("The package may need a different name." if "No package found" in out else "winget reported an error."),
        details={"package": name, "tail": out.strip()[-500:]},
    )


def _is_installed_width_winget(name: str) -> bool:
    try:
        proc = subprocess.run(
            ["winget", "list", "--name", name, "--accept-source-agreements"],
            capture_output=True, text=True, timeout=60,
        )
        return name.lower() in proc.stdout.lower()
    except Exception:
        return False