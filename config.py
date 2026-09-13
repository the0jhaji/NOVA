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
class AIConfig:
    """
    Local-first AI brain settings.

    - ai_provider:      "ollama" (default, local) | "cloud" | "none".
    - local_model:      Ollama model tag. Default qwen3:8b (Apache-2.0,
                        strong Hindi + English + Hinglish, tool calling).
                        Change freely — never hard-coded permanently.
    - local_base_url:   Model runtime endpoint (localhost by default). NOVA
                        only talks to loopback for the local provider unless
                        allow_remote_local_model is explicitly true.
    - cloud_enabled:    CLOUD_AI master switch. FALSE BY DEFAULT. Enabling
                        requires explicit user confirmation in Privacy settings.
    - cloud_provider:   "openai-compatible" (generic OpenAI-style endpoint).
    - cloud_api_key:    Stored in .env, NEVER logged and NEVER injected into
                        prompts (see privacy/redactor.py).
    """
    ai_provider: str = field(default_factory=lambda: _env("AI_PROVIDER", "ollama"))
    local_model: str = field(default_factory=lambda: _env("LOCAL_MODEL", "qwen3:8b"))
    local_base_url: str = field(default_factory=lambda: _env("LOCAL_AI_BASE_URL", "http://localhost:11434"))
    local_timeout: int = field(default_factory=lambda: int(_env("LOCAL_AI_TIMEOUT", "90")))
    allow_remote_local_model: bool = field(default_factory=lambda: _env_bool("LOCAL_AI_ALLOW_REMOTE", False))
    cloud_enabled: bool = field(default_factory=lambda: _env_bool("CLOUD_AI_ENABLED", False))
    cloud_provider: str = field(default_factory=lambda: _env("CLOUD_AI_PROVIDER", "openai-compatible"))
    cloud_base_url: str = field(default_factory=lambda: _env("CLOUD_AI_BASE_URL", ""))
    cloud_model: str = field(default_factory=lambda: _env("CLOUD_AI_MODEL", ""))
    cloud_api_key: str = field(default_factory=lambda: _env("CLOUD_AI_KEY", ""))


@dataclass(frozen=True)
class PrivacyConfig:
    """
    Privacy boundary defaults (all local-first, private by default).

    - network_mode:         "local-only" (default) | "user-approved-cloud" |
                            "blocked". Every external network operation is
                            decided by the NetworkManager, not the caller.
    - telemetry_enabled:    FALSE BY DEFAULT. Diagnostics are opt-in only.
    - screen_awareness:     Screen capture may only happen on request / for a
                            task / when this opt-in flag is enabled.
    - conversation_retention: "session" (default, in-memory only) | "none" |
                            "disk" (explicit opt-in persistence).
    - auto_delete_temp:     Automatically remove temporary artifacts when they
                            are no longer required.
    """
    network_mode: str = field(default_factory=lambda: _env("PRIVACY_NETWORK_MODE", "local-only").lower())
    telemetry_enabled: bool = field(default_factory=lambda: _env_bool("PRIVACY_TELEMETRY_ENABLED", False))
    screen_awareness: bool = field(default_factory=lambda: _env_bool("PRIVACY_SCREEN_AWARENESS", False))
    conversation_retention: str = field(default_factory=lambda: _env("PRIVACY_CONVERSATION_RETENTION", "session").lower())
    auto_delete_temp: bool = field(default_factory=lambda: _env_bool("PRIVACY_AUTO_DELETE_TEMP", True))


@dataclass(frozen=True)
class NovaConfig:
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    automation: AutomationConfig = field(default_factory=AutomationConfig)
    debug: bool = field(default_factory=lambda: _env_bool("DEBUG", False))
    app_name: str = "NOVA"
    app_version: str = "0.4.0"


# Singleton config instance
config = NovaConfig()
