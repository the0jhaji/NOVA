"""
NOVA Voice Assistant - NetworkManager
Every external network operation in NOVA passes through this decision
service. Nothing is "just sent" — each request is classified and either
allowed to the local runtime, allowed to an approved cloud scope, or
blocked. Failure to classify = blocked (fail-closed).

Modes
- local-only:            loopback to a local model runtime only.
- user-approved-cloud:   loopback + explicitly approved cloud scopes.
- blocked:               no external traffic (local runtime also denied).
"""

import enum
import ipaddress
import re
from urllib.parse import urlparse

from privacy.state import privacy_state, NETWORK_LOCAL_ONLY, NETWORK_USER_APPROVED_CLOUD

# Scopes a user can explicitly approve (cloud AI models today).
_APPROVED_SCOPES = {"ai", "llm", "model"}


class NetworkDecision(enum.Enum):
    ALLOWED_LOCAL = "allowed-local"
    ALLOWED_CLOUD = "allowed-cloud"
    BLOCKED = "blocked"


_LOOPBACK = re.compile(r"^(127\.\d{1,3}\.\d{1,3}\.\d{1,3}|localhost|\[::1\]|::1)$", re.I)


def is_loopback(url: str) -> bool:
    """True for a URL pinned to the user's own machine (localhost / 127.*)."""
    host = urlparse(url).hostname or ""
    if _LOOPBACK.match(host):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class NetworkManager:
    """Fail-closed gate for all outbound network calls."""

    def __init__(self):
        self.approved_scopes: set[str] = set()

    # ------------------------------------------------------------------ API
    def request(self, *, url: str = "", scope: str = "ai") -> NetworkDecision:
        """Decide whether a network call may proceed."""
        if is_loopback(url):
            if privacy_state.network_mode == NETWORK_USER_APPROVED_CLOUD:
                return NetworkDecision.ALLOWED_LOCAL
            return NetworkDecision.ALLOWED_LOCAL
        return self.request_cloud(scope)

    def request_cloud(self, scope: str = "ai") -> NetworkDecision:
        """Decide whether a non-local (cloud) call may proceed."""
        if privacy_state.network_mode == "blocked":
            return NetworkDecision.BLOCKED
        if privacy_state.network_mode != NETWORK_USER_APPROVED_CLOUD:
            return NetworkDecision.BLOCKED
        if not privacy_state.is_cloud_active():
            return NetworkDecision.BLOCKED
        if scope not in _APPROVED_SCOPES and scope not in self.approved_scopes:
            return NetworkDecision.BLOCKED
        return NetworkDecision.ALLOWED_CLOUD

    def approve_scope(self, scope: str) -> None:
        """Mark a scope as user-approved (called after explicit confirmation)."""
        if scope in _APPROVED_SCOPES:
            self.approved_scopes.add(scope)

    def revoke_scopes(self) -> None:
        self.approved_scopes.clear()

    def is_cloud_allowed(self, scope: str = "ai") -> bool:
        return self.request_cloud(scope) == NetworkDecision.ALLOWED_CLOUD


# Singleton the whole app uses.
network = NetworkManager()