"""
NOVA Voice Assistant - Configuration
Loads settings from environment variables with sensible defaults.
All provider choices are configurable here to keep the architecture swappable.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key, "").lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default


@dataclass(frozen=True)
class STTConfig:
    provider: str = field(default_factory=lambda: _env("STT_PROVIDER", "google"))
    whisper_model: str = field(default_factory=lambda: _env("WHISPER_MODEL", "base"))
    language: str = field(default_factory=lambda: _env("RECOGNITION_LANGUAGE", "auto"))


@dataclass(frozen=True)
class TTSConfig:
    provider: str = field(default_factory=lambda: _env("TTS_PROVIDER", "edge-tts"))
    voice: str = field(default_factory=lambda: _env("TTS_VOICE", "en-US-AvaNeural"))
    rate: str = field(default_factory=lambda: _env("TTS_RATE", "+0%"))
    volume: str = field(default_factory=lambda: _env("TTS_VOLUME", "+0%"))


@dataclass(frozen=True)
class WakeWordConfig:
    enabled: bool = field(default_factory=lambda: _env_bool("WAKE_WORD_ENABLED", False))
    word: str = field(default_factory=lambda: _env("WAKE_WORD", "nova"))


@dataclass(frozen=True)
class NovaConfig:
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    debug: bool = field(default_factory=lambda: _env_bool("DEBUG", False))
    app_name: str = "NOVA"
    app_version: str = "0.1.0"


# Singleton config instance
config = NovaConfig()
