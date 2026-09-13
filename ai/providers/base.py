"""
NOVA Voice Assistant - AIProvider interface
Every provider (local or cloud) implements this contract. Providers never
see secrets: the caller redacts prompts before they arrive here.
"""

from abc import ABC, abstractmethod
from typing import Optional


class AIUnavailable(Exception):
    """The model runtime is not reachable / the model is missing.
    Callers MUST NOT silently fall back to a cloud provider."""


class AIBlocked(Exception):
    """The privacy firewall refused the outbound call (fail-closed)."""


class AIProvider(ABC):
    name: str = "provider"
    kind: str = "local"          # "local" | "cloud"

    @abstractmethod
    def available(self) -> bool:
        """Is the model runtime + configured model available right now?
        Must not raise; returns False on any error."""

    @abstractmethod
    def chat(self, text: str, system: str = "", history: Optional[list] = None,
             temperature: float = 0.4) -> str:
        """Generate a text reply to `text`. Raises AIUnavailable/AIBlocked."""

    def plan(self, text: str) -> Optional[dict]:
        """Ask the model to classify `text` into a structured action.
        Returns None when the model produced no valid action."""
        if not self.available():
            raise AIUnavailable(self.name)
        from ai.prompts import PLAN_SYSTEM, plan_messages, parse_action_json
        raw = self.chat(text, system=PLAN_SYSTEM, temperature=0.1)
        if not raw:
            return None
        return parse_action_json(raw)

    def status(self) -> str:
        return f"{self.name}/{self.kind}"