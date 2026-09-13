"""
NOVA Voice Assistant - Voice Provider Abstraction
A swappable voice layer. The whole app talks to a `VoiceProvider`; concrete
providers (edge-tts neural voices, Windows SAPI) implement the same
interface. NOVA can be extended with new voices without touching UI or brain.
"""

from abc import ABC, abstractmethod


class VoiceProvider(ABC):
    """Interface every NOVA voice must implement.

    - `speak(text, lang)`     — speak in the given language ("en", "hi",
                                "hinglish", or "auto"). Blocks until done, so
                                callers run it in a worker thread.
    - `apply(volume, speed)`  — live voice adjustments (settings panel).
    - `stop()`                — best-effort silent the current utterance.
    - `voices()`              — human descriptions of available voices.
    """

    name = "unknown"

    @abstractmethod
    def speak(self, text: str, lang: str = "auto") -> None:
        ...

    def apply(self, volume: int = 100, speed: int = 0) -> None:
        """volume 0..100, speed -50..+50. Default: no-op."""

    def stop(self) -> None:
        ...

    def voices(self) -> list[str]:
        return []

    def describe(self) -> str:
        return self.name