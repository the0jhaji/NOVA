"""
NOVA Voice Assistant - Edge TTS provider (Indian female voices)
Microsoft Edge neural voices — realistic, natural and free. Includes the
Indian female voices NOVA is built on:

  - en-IN-NeerjaNeural    (Indian English, female)
  - hi-IN-SwaraNeural     (Hindi, female — speaks Hinglish blends too)

The right voice is picked per utterance: Devanagari / Hinglish text is sent
to the Hindi voice, English to the Indian-English voice. Networks required;
falls back gracefully and logs clearly.
"""

import asyncio
import io
import threading

from config import config
from utils.logger import log
from voice.language import detect_lang
from voice.providers import VoiceProvider

# Default neural Indian female voices (can be overridden via VOICE_NAME).
_HIN_TTS = {
    "hi": "hi-IN-SwaraNeural",
    "hinglish": "hi-IN-SwaraNeural",
    "en": "en-IN-NeerjaNeural",
}


class EdgeVoiceProvider(VoiceProvider):
    name = "edge-tts"

    def __init__(self, voice: str = "", rate: str = "+0%",
                 volume: int = 100, speed: int = 0,
                 auto_detect: bool = True):
        self.voice = voice or config.voice.voice or _HIN_TTS["en"]
        self._rate = rate
        self._volume = max(0, min(100, volume))
        self._speed = max(-50, min(50, speed))
        self._auto_detect = auto_detect
        self._lock = threading.Lock()
        self._mixer_ok = False

    # ------------------------------------------------------------------ API
    def speak(self, text: str, lang: str = "auto") -> None:
        """Generate and play `text` via the configured neural voice."""
        try:
            import edge_tts
        except Exception as e:  # pragma: no cover - import guard
            log.error("edge-tts not installed: %s", e)
            return
        try:
            voice = self._pick_voice(text, lang)
            rate = self._rate_string()
            with self._lock:
                loop = asyncio.new_event_loop()
                try:
                    audio = loop.run_until_complete(
                        self._generate(edge_tts, text, voice, rate))
                finally:
                    loop.close()
                if not audio:
                    log.warning("Edge TTS returned empty audio for voice %s", voice)
                    return
                self._play(audio)
        except Exception as e:
            log.error("Edge TTS failed: %s", e)

    def apply(self, volume: int = 100, speed: int = 0) -> None:
        self._volume = max(0, min(100, volume))
        self._speed = max(-50, min(50, speed))

    def stop(self) -> None:
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.stop()
        except Exception:
            pass

    def voices(self) -> list[str]:
        return [self._pick_voice("", "en"), self._pick_voice("", "hi")]

    def describe(self) -> str:
        return f"Edge neural · {self.voice}"

    # ------------------------------------------------------------- internals
    @staticmethod
    async def _generate(edge_tts, text: str, voice: str, rate: str) -> bytes:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                data += chunk["data"]
        return data

    def _pick_voice(self, text: str, lang: str) -> str:
        if lang == "auto":
            lang = detect_lang(text)
        if lang not in _HIN_TTS and self.voice not in _HIN_TTS.values():
            return self.voice  # custom voice kept for non-Indian langs
        return _HIN_TTS.get(lang, self.voice or _HIN_TTS["en"])

    def _rate_string(self) -> str:
        if self._speed == 0:
            return self._rate
        sign = "+" if self._speed >= 0 else "-"
        return f"{sign}{abs(self._speed)}%"

    def _play(self, audio: bytes) -> None:
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            sound = pygame.mixer.Sound(io.BytesIO(audio))
            sound.set_volume(self._volume / 100.0)
            sound.play()
            while pygame.mixer.get_busy():
                pygame.time.wait(50)
        except Exception as e:  # pragma: no cover - audio device issues
            log.warning("Audio playback unavailable: %s", e)


class NullVoiceProvider(VoiceProvider):
    """Silent stub used when VOICE_ENABLED=false or provider 'none'."""

    name = "none"

    def speak(self, text: str, lang: str = "auto") -> None:  # noqa: ARG002
        pass

    def describe(self) -> str:
        return "voice disabled"