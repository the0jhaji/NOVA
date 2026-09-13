"""
NOVA Voice Assistant - OllamaProvider (local, private by default)
Talks to the user's own Ollama runtime at http://localhost:11434 only.

- Loopback enforced: any other host is refused unless the user explicitly
  opts into a remote runtime (LOCAL_AI_ALLOW_REMOTE=true).
- stdlib urllib only — no extra dependency, no cloud, no telemetry.
- If the runtime/model is missing, raises AIUnavailable; the caller never
  forwards the request anywhere else.
"""

import json
import urllib.error
import urllib.request
from typing import Optional

from ai.providers.base import AIProvider, AIUnavailable, AIBlocked
from config import config
from privacy.network_manager import is_loopback
from utils.logger import log


class OllamaProvider(AIProvider):
    name = "ollama"
    kind = "local"

    def __init__(self, base_url: str = "", model: str = "",
                 timeout: int = 0, allow_remote: Optional[bool] = None):
        self.base_url = (base_url or config.ai.local_base_url).rstrip("/")
        self.model = model or config.ai.local_model
        self.timeout = int(timeout or config.ai.local_timeout)
        self.allow_remote = (
            config.ai.allow_remote_local_model if allow_remote is None
            else bool(allow_remote))
        self._available: Optional[bool] = None

    # ------------------------------------------------------------- routing
    def _endpoint(self, path: str) -> str:
        if not is_loopback(self.base_url) and not self.allow_remote:
            raise AIBlocked(
                "Local AI endpoint is not on this machine. To keep NOVA "
                "private it is refused unless LOCAL_AI_ALLOW_REMOTE=true.")
        return f"{self.base_url}{path}"

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            self._endpoint(path),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            if resp.status >= 400:
                raise AIUnavailable(f"ollama http {resp.status}")
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, path: str) -> dict:
        req = urllib.request.Request(self._endpoint(path), method="GET")
        with urllib.request.urlopen(req, timeout=6) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # ------------------------------------------------------------- API
    def available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            tags = self._get("/api/tags")
            models = {m.get("name") for m in tags.get("models", [])}
            ok = self.model in models
            if not ok:
                log.info("Local model '%s' not present in Ollama "
                         "(models: %d found)", self.model, len(models))
        except AIBlocked:
            return False
        except Exception:
            ok = False
        self._available = ok
        return ok

    def chat(self, text: str, system: str = "",
             history: Optional[list] = None, temperature: float = 0.4) -> str:
        # Loopback gate first — a remote runtime must never be touched
        # unless the user explicitly opted in.
        target = self._endpoint("/api/chat")
        if not self.available():
            raise AIUnavailable(f"local model '{self.model}' unavailable")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        for msg in (history or []):
            messages.append({"role": str(msg.get("role", "user")),
                             "content": str(msg.get("content", ""))})
        messages.append({"role": "user", "content": text})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 8192},
            "think": False,
        }
        try:
            data = self._post("/api/chat", payload)
        except AIUnavailable:
            raise
        except Exception as e:
            log.warning("Ollama chat failed: %s", e)
            raise AIUnavailable(f"ollama chat failed") from e

        content = data.get("message", {}).get("content", "")
        if isinstance(content, list):         # newer runtimes may chunk
            content = "".join(c.get("text", "") for c in content
                              if isinstance(c, dict))
        return str(content)

    def status(self) -> str:
        return f"ollama · {self.model} · {self.base_url}"