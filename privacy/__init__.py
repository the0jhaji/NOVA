"""NOVA Voice Assistant - Privacy Boundary (local-first, private by default).

- privacy.redactor          secret redaction before any model/log sink
- privacy.state             runtime privacy flags + .env persistence
- privacy.network_manager   fail-closed gate for all outbound network calls
- privacy.telemetry         opt-in-only diagnostics (no default telemetry)
- privacy.retention         data retention + Clear NOVA Data
"""

from privacy.redactor import redact_secrets, looks_sensitive
from privacy.state import privacy_state, NETWORK_LOCAL_ONLY, NETWORK_BLOCKED
from privacy.network_manager import network, NetworkDecision, is_loopback
from privacy.retention import clear_nova_data, retention_mode

__all__ = [
    "redact_secrets",
    "looks_sensitive",
    "privacy_state",
    "network",
    "NetworkDecision",
    "is_loopback",
    "clear_nova_data",
    "retention_mode",
]