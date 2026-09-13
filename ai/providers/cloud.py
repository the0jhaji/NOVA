"""
NOVA Voice Assistant - OptionalCloudAIProvider (DISABLED BY DEFAULT)

An OpenAI-compatible chat endpoint. It can only be reached when ALL of:

1. CLOUD_AI_ENABLED=true in .env,
2. the user has explicitly confirmed enabling Cloud AI in Privacy settings
   this session (privacy_state.cloud_approved),
3. the NetworkManager returns ALLOWED_CLOUD for scope "ai".

Prompts are already redacted by the caller before they reach this class;
the API key is read from .env, never logged, and never included in prompts.
"""

import json
import urllib.request
from typing import Optional

from ai.providers.base import AIProvider, AIUnavailable, AIBlocked
from config import config
from privacy.network_manager import network, NetworkDecision
from privacy.state import privacy_state
from utils.logger import log


class CloudAIProvider(AIProvider):
    name = "cloud"
    kind = "cloud"

    def __init__(self, base_url: str = "", model: str = "",
                 api_key: str = ""):
        self.base_url = (base_url or config.ai.cloud_base_url).rstrip("/")
        self.model = model or config.ai.cloud_model
        self.api_key = api_key or config.ai.cloud_api_key

    # ------------------------------------------------------------- gating
    def _gate(self):
        """Fail-closed: no approval -> no bytes leave this machine."""
        if not privacy_state.is_cloud_active():
            raise AIBlocked("Cloud AI is not enabled and approved")
        decision = network.request_cloud("ai")
        if decision != NetworkDecision.ALLOWED_CLOUD:
            raise AIBlocked(f"network refused cloud call ({decision.value})")

    def _endpoint(self) -> str:
        if not self.base_url:
            raise AIBlocked("Cloud AI endpoint is not configured")
        return f"{self.base_url}/chat/completions"

    # ------------------------------------------------------------- API
    def available(self) -> bool:
        try:
            self._gate()
            return bool(self.base_url and self.model and self.api_key)
        except AIBlocked:
            return False

    def chat(self, text: str, system: str = "",
             history: Optional[list] = None, temperature: float = 0.4) -> str:
        self._gate()
        if not self.model:
            raise AIBlocked("Cloud AI model is not configured")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        for msg in (history or []):
            messages.append({"role": "user", "content": str(msg.get("content", ""))})
        messages.append({"role": "user", "content": text})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        req = urllib.request.Request(
            self._endpoint(),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config.ai.local_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return str(content)
        except Exception as e:
            log.warning("Cloud AI request failed (scope ai): %s", e)
            raise AIUnavailable("cloud provider failed") from e

    def status(self) -> str:
        return f"cloud · {self.model or 'unconfigured'}"