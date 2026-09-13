"""
NOVA Voice Assistant - Voice Controller
Runtime voice settings + speech orchestration.

- Chooses the provider (edge neural Indian voices by default).
- Applies language mode (AUTO/ENGLISH/HINDI/HINGLISH) per utterance.
- Applies volume / speed live and persists choices to .env.
- Auto-detects the user's language and lets the reply follow naturally.

All speech runs on a worker thread so the UI never blocks.
"""

import threading
from typing import Optional

from config import config, write_env
from utils.logger import log
from voice.language import effective_language
from voice.providers import VoiceProvider
from voice.providers.edge import EdgeVoiceProvider, NullVoiceProvider
from voice.providers.sapi import WindowsSAPIVoiceProvider


class VoiceController:
    """Central voice control surface used by the UI and the brain hooks."""

    def __init__(self, provider: Optional[VoiceProvider] = None,
                 enabled: bool = True, volume: int = 100, speed: int = 0,
                 language_mode: str = "AUTO", auto_detect: bool = True):
        self.provider = provider or _build_provider()
        self.enabled = enabled
        self.volume = volume
        self.speed = speed
        self.language_mode = (language_mode or "AUTO").upper()
        self.auto_detect = auto_detect
        self.provider.apply(volume=volume, speed=speed)

    # ------------------------------------------------------------- speaking
    def speak(self, text: str, user_lang: str = "auto") -> None:
        """Speak asynchronously. `user_lang` is the detected user language."""
        if not self.enabled or not text or not text.strip():
            return
        lang = effective_language(user_lang, self.language_mode, self.auto_detect)
        threading.Thread(
            target=self._run_speak, args=(text, lang), daemon=True,
        ).start()

    def _run_speak(self, text: str, lang: str):
        try:
            self.provider.speak(text, lang=lang)
        except Exception as e:
            log.error("voice failed: %s", e)

    # ------------------------------------------------------------- settings
    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        write_env("VOICE_ENABLED", "true" if enabled else "false")

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, int(volume)))
        self.provider.apply(volume=self.volume, speed=self.speed)
        write_env("VOICE_VOLUME", str(self.volume))

    def set_speed(self, speed: int) -> None:
        self.speed = max(-50, min(50, int(speed)))
        self.provider.apply(volume=self.volume, speed=self.speed)
        write_env("VOICE_SPEED", str(self.speed))

    def set_language_mode(self, mode: str) -> None:
        mode = (mode or "AUTO").upper()
        if mode not in ("AUTO", "ENGLISH", "HINDI", "HINGLISH"):
            mode = "AUTO"
        self.language_mode = mode
        write_env("VOICE_LANGUAGE", mode)

    def set_auto_detect(self, detect: bool) -> None:
        self.auto_detect = detect
        write_env("VOICE_AUTO_LANGUAGE", "true" if detect else "false")

    def set_provider(self, provider: str) -> None:
        """Switch the active voice provider at runtime and persist it."""
        self.provider = _build_provider(provider=provider)
        self.provider.apply(volume=self.volume, speed=self.speed)
        write_env("VOICE_PROVIDER", provider)

    def stop(self) -> None:
        try:
            self.provider.stop()
        except Exception:
            pass

    def test(self, text: str = "Namaste! Main NOVA hun. Sure, Chrome open kar rahi hoon.") -> None:
        log.info("Voice test: %s", text)
        self.speak(text, user_lang="hinglish")

    def describe(self) -> str:
        return (f"{self.provider.describe()} · {self.language_mode} · "
                f"vol {self.volume} · speed {self.speed:+d}")


def _build_provider(provider: str = "") -> VoiceProvider:
    v = config.voice
    provider = (provider or v.provider or "edge-tts").lower()
    if not v.enabled or provider in ("none", "off", "disabled"):
        return NullVoiceProvider()
    if provider in ("windows-sapi", "sapi", "sapi5", "pyttsx3"):
        return WindowsSAPIVoiceProvider(
            voice_name=v.sapi_name, volume=v.volume, speed=v.speed)
    # default: edge-tts (natural neural Indian female voices)
    return EdgeVoiceProvider(
        voice=v.voice, rate=v.rate, volume=v.volume, speed=v.speed,
        auto_detect=v.auto_language_detect)


# Convenience singleton created at import time (no audio side effects).
try:
    voice = VoiceController(
        provider=_build_provider(),
        enabled=config.voice.enabled,
        volume=config.voice.volume,
        speed=config.voice.speed,
        language_mode=config.voice.language_mode,
        auto_detect=config.voice.auto_language_detect,
    )
except Exception as e:  # pragma: no cover - never let this crash startup
    log.error("voice controller init failed: %s", e)
    voice = VoiceController(provider=NullVoiceProvider(), enabled=False)