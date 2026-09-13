"""
NOVA Voice Assistant - Privacy Redactor
Strips secrets from text BEFORE it reaches any AI model or log sink.

Handles common credential shapes plus everything sensitive in this
machine's own .env (values are replaced with [REDACTED]).
"""

import re
from pathlib import Path
from typing import Dict, List

_REDACTED = "[REDACTED]"

# Common credential patterns.
_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?i)\b(sk-[A-Za-z0-9_-]{12,})\b"),                     # OpenAI-style
    re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),                               # AWS access key id
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b"),                     # GitHub tokens
    re.compile(r"\b(AIza[0-9A-Za-z_-]{20,})\b"),                         # Google API keys
    re.compile(r"\b(xox[baprs]-[0-9A-Za-z-]{10,})\b"),                   # Slack tokens
    re.compile(r"\b(eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})\b"),  # JWTs
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    re.compile(r"(?i)\b(bearer\s+[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=+-]{16,})\b"),
    re.compile(r"(?i)(password\s*[:=]\s*\S+)"),
    re.compile(r"(?i)(passwd|pwd)\s*[:=]\s*\S+"),
]

# .env key names whose values are treated as secrets.
_SENSITIVE_KEY_HINT = re.compile(
    r"(?i)(api[_-]?key|secret|password|passwd|token|auth|bearer|credential|private[_-]?key)"
)


def env_secret_values(env_path=None) -> Dict[str, str]:
    """Map of sensitive .env key -> value (value is used for redaction)."""
    if env_path is None:
        env_path = Path(__file__).parent.parent / ".env"
    secrets: Dict[str, str] = {}
    if not env_path.exists():
        return secrets
    try:
        from dotenv import dotenv_values
        values = dotenv_values(str(env_path))
        for key, val in values.items():
            if val and _SENSITIVE_KEY_HINT.search(key):
                secrets[key] = val
    except Exception:
        # Fail-safe: if .env cannot be parsed, redact nothing extra.
        pass
    return secrets


def redact_secrets(text: str, secret_values: Dict[str, str] | None = None) -> str:
    """Replace known secret shapes and .env secret values with [REDACTED]."""
    if not text:
        return text
    out = text
    for pat in _PATTERNS:
        out = pat.sub(_REDACTED, out)
    if secret_values is None:
        secret_values = env_secret_values()
    for value in secret_values.values():
        if len(value) >= 4 and value in out:
            out = out.replace(value, _REDACTED)
    return out


def looks_sensitive(text: str, secret_values: Dict[str, str] | None = None) -> bool:
    """Decision helper for the privacy firewall: would this text be unsafe
    to hand to a non-local model?"""
    if not text:
        return False
    for pat in _PATTERNS:
        if pat.search(text):
            return True
    if secret_values is None:
        secret_values = env_secret_values()
    return any(len(v) >= 4 and v in text for v in secret_values.values())