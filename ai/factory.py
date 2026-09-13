"""
NOVA Voice Assistant - AI provider factory
Picks the provider from configuration. Cloud is DISABLED BY DEFAULT and
additionally requires explicit session approval; "none" disables AI and
NOVA's deterministic intent engine remains primary.
"""

from typing import Optional

from ai.providers.base import AIProvider
from config import config
from privacy.state import privacy_state
from utils.logger import log


def create_ai_provider() -> Optional[AIProvider]:
    provider = (config.ai.ai_provider or "ollama").lower().strip()

    if provider in ("none", "off", "disabled"):
        return None

    if provider == "cloud":
        if not privacy_state.is_cloud_active():
            log.info("Cloud AI configured but not enabled+approved — "
                     "staying local")
            return None
        from ai.providers.cloud import CloudAIProvider
        return CloudAIProvider()

    # default: local Ollama runtime
    from ai.providers.ollama import OllamaProvider
    return OllamaProvider()