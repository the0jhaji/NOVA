"""
NOVA Voice Assistant - Speech-to-Text
Provider-based STT with support for Google (free) and Whisper (local).
Each provider implements the same interface for swappability.
"""

import io
import abc
import threading
from typing import Optional

import speech_recognition as sr

from config import config
from utils.logger import log


class STTProvider(abc.ABC):
    """Abstract base for speech-to-text providers."""

    @abc.abstractmethod
    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        ...


class GoogleSTT(STTProvider):
    """Google Web Speech API (free, requires internet)."""

    def __init__(self, language: str = "en-US"):
        self.recognizer = sr.Recognizer()
        # "auto" tries English first; fallback handled at caller level
        self.language = None if language == "auto" else language

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        try:
            audio = sr.AudioData(audio_data, sample_rate, 2)
            lang = self.language or "en-US"
            text = self.recognizer.recognize_google(audio, language=lang)
            return text
        except sr.UnknownValueError:
            log.debug("Google STT: could not understand audio")
            return None
        except sr.RequestError as e:
            log.error("Google STT request failed: %s", e)
            return None


class WhisperSTT(STTProvider):
    """OpenAI Whisper local model (offline, requires whisper package)."""

    def __init__(self, model_size: str = "base"):
        self.model = None
        self.model_size = model_size
        self._lock = threading.Lock()

    def _ensure_model(self):
        if self.model is None:
            import whisper
            log.info("Loading Whisper model (%s)...", self.model_size)
            self.model = whisper.load_model(self.model_size)

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        try:
            import numpy as np
            import tempfile, os, wave

            with self._lock:
                self._ensure_model()

            # Write audio to temp WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
                with wave.open(f, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_data)

            result = self.model.transcribe(tmp_path)
            os.unlink(tmp_path)
            text = result.get("text", "").strip()
            return text if text else None
        except Exception as e:
            log.error("Whisper STT failed: %s", e)
            return None


def create_stt_provider() -> STTProvider:
    """Factory: create the configured STT provider."""
    cfg = config.stt
    if cfg.provider == "whisper":
        return WhisperSTT(model_size=cfg.whisper_model)
    return GoogleSTT(language=cfg.language)
