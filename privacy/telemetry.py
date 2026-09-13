"""
NOVA Voice Assistant - Telemetry
NOVA has NO built-in telemetry. Diagnostics are:

  - OFF BY DEFAULT
  - EXPLICITLY OPT-IN

When enabled, only safe, aggregate fields are recorded (events, counts,
durations, provider names). Never: voice recordings, transcripts,
screenshots, commands, file contents, or personal information.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

from privacy.state import privacy_state
from utils.logger import log

# Fields an event may carry. Everything else is dropped.
_ALLOWED_FIELDS = {
    "event", "duration_ms", "count", "provider", "state", "tool",
}

_EVENTS: Dict[str, dict] = {}


def _sanitize(fields: dict) -> dict:
    return {k: v for k, v in fields.items() if k in _ALLOWED_FIELDS}


def record(event: str, **fields) -> None:
    """Record a safe diagnostic event. No-op unless opt-in."""
    if not privacy_state.telemetry_enabled:
        return
    entry = _sanitize(fields)
    entry["event"] = event
    entry["ts"] = datetime.now().isoformat()
    _EVENTS.setdefault(event, [])
    if len(_EVENTS[event]) < 200:
        _EVENTS[event].append(entry)


def is_opt_in() -> bool:
    return privacy_state.telemetry_enabled


def explain_policy() -> str:
    return ("Telemetry is OFF by default and never collects recordings, "
            "transcripts, screenshots, commands, file contents or personal "
            "information. When enabled it records only safe aggregate events.")