"""
NOVA Voice Assistant - Automation Risk Model
Action classification into SAFE / CONFIRMATION_REQUIRED / HIGH_RISK.

High-risk actions must never execute silently. Confirmation-required actions
are parked and only run after the user explicitly confirms.
"""

import enum
import re
from typing import Optional

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class RiskLevel(enum.IntEnum):
    SAFE = 0
    CONFIRMATION_REQUIRED = 1
    HIGH_RISK = 2


# Default risk per tool. Individual tools may refine based on parameters.
TOOL_BASE_RISK = {
    "open_application": RiskLevel.SAFE,
    "close_application": RiskLevel.SAFE,
    "open_url": RiskLevel.SAFE,
    "open_folder": RiskLevel.SAFE,
    "create_folder": RiskLevel.SAFE,
    "create_file": RiskLevel.SAFE,
    "move_file": RiskLevel.SAFE,
    "copy_file": RiskLevel.SAFE,
    "rename_file": RiskLevel.SAFE,
    "search_files": RiskLevel.SAFE,
    "take_screenshot": RiskLevel.SAFE,
    "type_text": RiskLevel.SAFE,
    "press_key": RiskLevel.SAFE,
    "mouse_click": RiskLevel.SAFE,
    "volume_control": RiskLevel.SAFE,
    "delete_file": RiskLevel.CONFIRMATION_REQUIRED,
    "install_software": RiskLevel.CONFIRMATION_REQUIRED,
    # Browser: navigation/reading is safe; clicking and typing mutate the
    # live web page, so they always require explicit confirmation.
    "browser_open_url": RiskLevel.SAFE,
    "browser_search": RiskLevel.SAFE,
    "browser_read": RiskLevel.SAFE,
    "browser_scroll": RiskLevel.SAFE,
    "browser_click": RiskLevel.CONFIRMATION_REQUIRED,
    "browser_type": RiskLevel.CONFIRMATION_REQUIRED,
    # High-risk tools are *defined* for gating but none of the high-risk
    # operations are implemented. If ever wired up, these must remain
    # HIGH_RISK and respect AUTOMATION_ALLOW_HIGH_RISK.
    "format_disk": RiskLevel.HIGH_RISK,
    "change_partition": RiskLevel.HIGH_RISK,
    "delete_system_files": RiskLevel.HIGH_RISK,
    "modify_security_policy": RiskLevel.HIGH_RISK,
}

# Filesystem roots that are never modified by file tools, even on SAFE paths.
PROTECTED_ROOTS = (
    "C:\\WINDOWS",
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "C:\\$Recycle.Bin",
    "C:\\System Volume Information",
)

# Phrases that map to high-risk intents NOVA will never run automatically.
HIGH_RISK_PHRASES = [
    r"\bform[ai]t\b",                     # format (disk)
    r"\b(wipe|erase|destroy)\s+(?:the\s+)?(disk|drive|hd|hard\s+drive|ssd)\b",
    r"\bpartitions?\b",                    # partition changes
    r"(delete|remove)\s+(system\s+files?|windows\s+(files?|folder))\b",
    r"\b(firewall|uac|defender)\s+(off|disable|change)\b",
    r"\b(disable|turn\s+off)\s+(?:the\s+)?(firewall|uac|defender)\b",
    r"\b(registry|policy)\s+(change|edit|modify)\b",
    r"\b(change|edit|modify)\s+(the\s+)?(registry|security\s+policy)\b",
    r"\b(mbr|bios|uefi|bootloader)\b",
]

_high_risk_re = re.compile(
    "|".join(HIGH_RISK_PHRASES), re.IGNORECASE
)


def classify_text_high_risk(text: str) -> bool:
    """True if the requested intent references a high-risk operation."""
    return bool(_high_risk_re.search(text or ""))


def _path_in_protected(path: str) -> bool:
    lower = path.lower()
    return any(
        lower == root.lower() or lower.startswith(root.lower() + "\\")
        for root in PROTECTED_ROOTS
    )


def classify_step(tool: str, params: Optional[dict] = None) -> RiskLevel:
    """
    Decide the effective risk for a tool + parameters.

    Base risk comes from TOOL_BASE_RISK; parameter-aware refinements upgrade
    the level (never downgrade):
    - Deleting anything inside protected roots becomes HIGH_RISK.
    - File mutations targeting protected roots become HIGH_RISK.
    - Bulk file operations are treated as CONFIRMATION_REQUIRED.
    """
    params = params or {}
    base = TOOL_BASE_RISK.get(tool, RiskLevel.CONFIRMATION_REQUIRED)
    risk = base

    paths = [str(v) for v in params.values() if isinstance(v, str)]
    touched = any(_path_in_protected(p) for p in paths)

    if touched:
        risk = max(risk, RiskLevel.HIGH_RISK)

    if tool in ("delete_file", "move_file", "copy_file") and params.get("many"):
        risk = max(risk, RiskLevel.CONFIRMATION_REQUIRED)

    return risk


def classify(text: str, tool: str, params: Optional[dict] = None) -> RiskLevel:
    """
    Text-aware classification: HIGH_RISK phrases always win, then the
    parameter-aware tool classification.
    """
    if classify_text_high_risk(text):
        return RiskLevel.HIGH_RISK
    return classify_step(tool, params)