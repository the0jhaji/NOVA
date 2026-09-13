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


def write_env(key: str, value: str) -> None:
    """
    Persist a key/value pair into .env, preserving every other line.
    Called by the voice settings UI so choices survive a restart.
    """
    path = _env_path
    lines = []
    found = False
    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:
            raw = ""
        for ln in raw.splitlines():
            if ln.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(ln)
    if not found:
        lines.append(f"{key}={value}")
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


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
class VoiceConfig:
    """
    NOVA's spoken identity.

    - provider:          edge-tts (natural neural voices, incl. Indian) or
                         windows-sapi (offline fallback).
    - voice:             default voice name (edge voices like en-IN-NeerjaNeural).
    - language_mode:     AUTO | ENGLISH | HINDI | HINGLISH — bias for the
                         response + TTS voice selection.
    - enabled:           master voice switch (disables speech playback).
    - auto_language_detect: follow the user's language (AUTO mode) vs a
                         fixed mode.
    - volume:            0..100 speech volume.
    - speed:             -50..+50 speaking rate shift.
    - sapi_name:         optional SAPI voice name to prefer on Windows.
    Legacy variables TTS_PROVIDER / TTS_VOICE / TTS_RATE / TTS_VOLUME are
    still honoured when the VOICE_* equivalents are absent.
    """
    provider: str = field(default_factory=lambda: _env("VOICE_PROVIDER", _env("TTS_PROVIDER", "edge-tts")))
    voice: str = field(default_factory=lambda: _env("VOICE_NAME", _env("TTS_VOICE", "en-IN-NeerjaNeural")))
    rate: str = field(default_factory=lambda: _env("TTS_RATE", "+0%"))
    volume_str: str = field(default_factory=lambda: _env("TTS_VOLUME", "+0%"))
    language_mode: str = field(default_factory=lambda: _env("VOICE_LANGUAGE", "AUTO").upper())
    enabled: bool = field(default_factory=lambda: _env_bool("VOICE_ENABLED", True))
    auto_language_detect: bool = field(default_factory=lambda: _env_bool("VOICE_AUTO_LANGUAGE", True))
    volume: int = field(default_factory=lambda: int(_env("VOICE_VOLUME", "100")))
    speed: int = field(default_factory=lambda: int(_env("VOICE_SPEED", "0")))
    sapi_name: str = field(default_factory=lambda: _env("VOICE_SAPI_NAME", ""))


@dataclass(frozen=True)
class AutomationConfig:
    """
    Windows automation layer settings.

    - auto_confirm:      if True, CONFIRMATION_REQUIRED actions run without an
                         explicit spoken "yes". Default False (safest).
    - allow_high_risk:   if True, HIGH_RISK actions *may* run after explicit
                         confirmation. No high-risk tools ship in this phase,
                         so this is effectively a guard for future tools.
    - screenshot_dir:    where screenshot PNGs are saved (default:
                         Pictures\\NOVA Screenshots).
    - apps_config:       JSON file with custom app launch commands.
    - search_root:       default folder to search files in (default: user home).
    """
    auto_confirm: bool = field(default_factory=lambda: _env_bool("AUTOMATION_AUTO_CONFIRM", False))
    allow_high_risk: bool = field(default_factory=lambda: _env_bool("AUTOMATION_ALLOW_HIGH_RISK", False))
    screenshot_dir: str = field(default_factory=lambda: _env("SCREENSHOT_DIR", ""))
    apps_config: str = field(default_factory=lambda: _env("APPS_CONFIG_FILE", "apps_config.json"))
    search_root: str = field(default_factory=lambda: _env("SEARCH_ROOT", ""))


@dataclass(frozen=True)
class NovaConfig:
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    automation: AutomationConfig = field(default_factory=AutomationConfig)
    debug: bool = field(default_factory=lambda: _env_bool("DEBUG", False))
    app_name: str = "NOVA"
    app_version: str = "0.3.0"


# Singleton config instance
config = NovaConfig()
