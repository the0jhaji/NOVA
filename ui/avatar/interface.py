"""
NOVA Voice Assistant - Avatar System
A decoupled character layer. The UI only talks to `AvatarHost`, so the
procedural QPainter face shipped here can later be swapped for a Live2D
model, sprite rig, or 3D avatar without touching the rest of NOVA.

Facial / animation states: IDLE, LISTENING, THINKING (PROCESSING), SPEAKING,
EXECUTING, SUCCESS, ERROR — each maps to an expression plus FX.
"""

from abc import ABC, abstractmethod


class AvatarHost(ABC):
    """Anything that renders NOVA's character for the UI."""
    state = "IDLE"

    @abstractmethod
    def set_state(self, state: str) -> None:
        """Switch the character's facial state (IDLE/LISTENING/...)."""

    @abstractmethod
    def set_audio_level(self, level: float) -> None:
        """Live microphone level 0..1 (listening animation)."""

    @abstractmethod
    def react_to_speech(self, envelope: float) -> None:
        """Speech envelope 0..1 for lip-sync / mouth animation."""