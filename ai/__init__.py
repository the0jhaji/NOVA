"""
NOVA Voice Assistant - AI Provider Layer

AIProvider (abstract)
├── LocalAIProvider (abstract)
│   └── OllamaProvider        -> local runtime, loopback only (localhost)
└── OptionalCloudAIProvider   -> OpenAI-compatible endpoint, DISABLED by default

Rules enforced here:
- The local provider talks ONLY to a loopback model runtime.
- No automatic cloud fallback. If the local model fails, the caller is told
  the request was NOT forwarded anywhere.
- Cloud calls require Cloud AI enabled + explicitly user-approved + the
  NetworkManager decision to be ALLOWED_CLOUD.
"""

from ai.providers.base import AIProvider, AIUnavailable, AIBlocked
from ai.providers.ollama import OllamaProvider
from ai.providers.cloud import CloudAIProvider
from ai.factory import create_ai_provider

__all__ = [
    "AIProvider",
    "AIUnavailable",
    "AIBlocked",
    "OllamaProvider",
    "CloudAIProvider",
    "create_ai_provider",
]