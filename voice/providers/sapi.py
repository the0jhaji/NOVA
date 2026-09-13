"""
NOVA Voice Assistant - Windows SAPI provider (offline fallback)
Uses the installed Windows SAPI 5 voices through pywin32. Best for fully
offline operation. On this machine the catalogue is usually David/Zira;
prefer `VOICE_SAPI_NAME` to select an installed voice (e.g. an Indian SAPI
voice if one has been installed system-wide).
"""

import threading

from config import config
from utils.logger import log
from voice.providers import VoiceProvider


class WindowsSAPIVoiceProvider(VoiceProvider):
    name = "windows-sapi"

    def __init__(self, voice_name: str = "", volume: int = 100,
                 speed: int = 0):
        self.voice_name = voice_name or config.voice.sapi_name
        self._volume = max(0, min(100, volume))
        self._speed = max(-50, min(50, speed))
        self._engine = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ API
    def _ensure(self):
        if self._engine is None:
            import win32com.client
            self._engine = win32com.client.Dispatch("SAPI.SpVoice")
            self._apply_props()
            if self.voice_name:
                self._select_voice(self.voice_name)
        return self._engine

    def speak(self, text: str, lang: str = "auto") -> None:  # noqa: ARG002
        try:
            engine = self._ensure()
            with self._lock:
                engine.Speak(text)
        except Exception as e:
            log.error("SAPI TTS failed: %s", e)

    def apply(self, volume: int = 100, speed: int = 0) -> None:
        self._volume = max(0, min(100, volume))
        self._speed = max(-50, min(50, speed))
        if self._engine is not None:
            self._apply_props()

    def stop(self) -> None:
        try:
            if self._engine is not None:
                self._engine.Speak("", 3)  # SVSFlagsAsync|SVSFPurgeBeforeSpeak
        except Exception:
            pass

    def voices(self) -> list[str]:
        try:
            engine = self._ensure()
            return [v.GetDescription() for v in engine.GetVoices()]
        except Exception:
            return []

    def describe(self) -> str:
        chosen = self.voice_name or "system default"
        return f"Windows SAPI · {chosen}"

    # ------------------------------------------------------------- internals
    def _apply_props(self):
        try:
            self._engine.Rate = int(self._speed * 1.4)  # SAPI range -10..10
            self._engine.Volume = self._volume
        except Exception:
            pass

    def _select_voice(self, name: str):
        low = name.lower()
        for v in self._engine.GetVoices():
            desc = v.GetDescription()
            if low in desc.lower():
                self._engine.Voice = v
                log.info("SAPI voice selected: %s", desc)
                return
        log.warning("SAPI voice %r not found; using default.", name)