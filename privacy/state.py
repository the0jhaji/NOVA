"""
NOVA Voice Assistant - Runtime Privacy State
Mutable privacy flags that live for the session AND persist to .env.

`config` is deliberately frozen; runtime toggles (Cloud AI, screen
awareness, telemetry) go through this object so the whole app sees the
same current state. Everything defaults to private.
"""

from config import config, write_env
from utils.logger import log

# Valid network modes handled by the NetworkManager.
NETWORK_LOCAL_ONLY = "local-only"
NETWORK_USER_APPROVED_CLOUD = "user-approved-cloud"
NETWORK_BLOCKED = "blocked"

_NETWORK_MODES = (NETWORK_LOCAL_ONLY, NETWORK_USER_APPROVED_CLOUD, NETWORK_BLOCKED)


class PrivacyState:
    def __init__(self):
        self.cloud_enabled: bool = config.ai.cloud_enabled       # CLOUD_AI_ENABLED
        self.cloud_approved: bool = False                        # explicit user confirmation
        self.network_mode: str = self._normalize(config.privacy.network_mode)
        self.screen_awareness: bool = config.privacy.screen_awareness
        self.telemetry_enabled: bool = config.privacy.telemetry_enabled
        self.conversation_retention: str = config.privacy.conversation_retention
        self.auto_delete_temp: bool = config.privacy.auto_delete_temp

    @staticmethod
    def _normalize(mode: str) -> str:
        mode = (mode or NETWORK_LOCAL_ONLY).lower()
        return mode if mode in _NETWORK_MODES else NETWORK_LOCAL_ONLY

    # ------------------------------------------------------------------- get
    def is_cloud_active(self) -> bool:
        """Cloud AI is usable only when enabled AND explicitly approved."""
        return self.cloud_enabled and self.cloud_approved

    def can_use_local_ai(self) -> bool:
        return self.network_mode != NETWORK_BLOCKED

    def is_local_mode(self) -> bool:
        return not self.is_cloud_active()

    # ----------------------------------------------------------------- set
    def enable_cloud(self, approved: bool = False) -> None:
        self.cloud_enabled = True
        self.cloud_approved = bool(approved)
        if approved:
            self.network_mode = NETWORK_USER_APPROVED_CLOUD
        else:
            self.network_mode = self._normalize(self.network_mode)
        write_env("CLOUD_AI_ENABLED", "true")
        write_env("PRIVACY_NETWORK_MODE", self.network_mode)
        log.warning("Cloud AI reporting enabled")  # never logs credentials

    def disable_cloud(self) -> None:
        self.cloud_enabled = False
        self.cloud_approved = False
        if self.network_mode == NETWORK_USER_APPROVED_CLOUD:
            self.network_mode = NETWORK_LOCAL_ONLY
        write_env("CLOUD_AI_ENABLED", "false")
        write_env("PRIVACY_NETWORK_MODE", self.network_mode)
        log.info("Cloud AI disabled — back to local mode")

    def set_screen_awareness(self, on: bool) -> None:
        self.screen_awareness = bool(on)
        write_env("PRIVACY_SCREEN_AWARENESS", "true" if on else "false")

    def set_telemetry(self, on: bool) -> None:
        self.telemetry_enabled = bool(on)
        write_env("PRIVACY_TELEMETRY_ENABLED", "true" if on else "false")

    def set_network_mode(self, mode: str) -> None:
        self.network_mode = self._normalize(mode)
        write_env("PRIVACY_NETWORK_MODE", self.network_mode)

    def set_conversation_retention(self, mode: str) -> None:
        if mode not in ("session", "disk", "none"):
            mode = "session"
        self.conversation_retention = mode
        write_env("PRIVACY_CONVERSATION_RETENTION", mode)

    # ----------------------------------------------------------------- export
    def snapshot(self) -> dict:
        return {
            "network_mode": self.network_mode,
            "cloud_enabled": self.cloud_enabled,
            "cloud_approved": self.cloud_approved,
            "cloud_active": self.is_cloud_active(),
            "screen_awareness": self.screen_awareness,
            "telemetry_enabled": self.telemetry_enabled,
            "conversation_retention": self.conversation_retention,
            "auto_delete_temp": self.auto_delete_temp,
        }


privacy_state = PrivacyState()