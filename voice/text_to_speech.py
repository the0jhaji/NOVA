"""
NOVA Voice Assistant - Text-to-Speech
Provider-based TTS with support for edge-tts (high quality) and pyttsx3 (offline).
"""

import abc
import asyncio
import io
import threading
from typing import Optional

from config import config
from utils.logger import log


class TTSProvider(abc.ABC):
    """Abstract base for text-to-speech providers."""

    @abc.abstractmethod
    def speak(self, text: str) -> None:
        """Block until speech is finished."""
        ...


class EdgeTTS(TTSProvider):
    """Microsoft Edge TTS - free, high quality neural voices."""

    def __init__(self, voice: str, rate: str = "+0%", volume: str = "+0%"):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self._lock = threading.Lock()

    def speak(self, text: str) -> None:
        with self._lock:
            try:
                import edge_tts
                import pygame

                # Run the async edge-tts in a new event loop for this thread
                async def _generate():
                    communicate = edge_tts.Communicate(
                        text, self.voice, rate=self.rate, volume=self.volume
                    )
                    audio_bytes = b""
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_bytes += chunk["data"]
                    return audio_bytes

                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                try:
                    audio_bytes = loop.run_until_complete(_generate())
                finally:
                    loop.close()

                if not audio_bytes:
                    log.warning("Edge TTS returned empty audio")
                    return

                # Play with pygame
                if not pygame.mixer.get_init():
                    pygame.mixer.init()

                sound = pygame.mixer.Sound(io.BytesIO(audio_bytes))
                sound.play()
                # Wait for playback to finish
                while pygame.mixer.get_busy():
                    pygame.time.wait(50)

            except Exception as e:
                log.error("Edge TTS failed: %s", e)
                # Fall back to pyttsx3
                log.info("Falling back to pyttsx3 TTS")
                Pyttsx3TTS().speak(text)


class Pyttsx3TTS(TTSProvider):
    """Offline TTS using pyttsx3 (SAPI5 on Windows)."""

    def __init__(self):
        self._lock = threading.Lock()

    def speak(self, text: str) -> None:
        with self._lock:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", 175)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception as e:
                log.error("pyttsx3 TTS failed: %s", e)


def create_tts_provider() -> TTSProvider:
    """Factory: create the configured TTS provider."""
    cfg = config.tts
    if cfg.provider == "edge-tts":
        return EdgeTTS(voice=cfg.voice, rate=cfg.rate, volume=cfg.volume)
    return Pyttsx3TTS()
