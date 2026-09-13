"""
AI provider tests with a fake local Ollama runtime and a fake OpenAI
compatible endpoint, both on loopback random ports so no external
dependency is required. Also verifies fail-closed cloud gating.
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from ai.providers.base import AIUnavailable, AIBlocked
from ai.providers.ollama import OllamaProvider
from ai.providers.cloud import CloudAIProvider
from privacy.state import privacy_state
from privacy.network_manager import network


_FAKE_TOOL = json.dumps({
    "intent": "tool", "tool": "open_application",
    "params": {"name": "chrome"}, "message": "Opening Chrome",
})
_FAKE_CHAT = json.dumps({"intent": "chat", "message": "Hello from local AI"})


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, code, obj, read_body=False):
        if read_body:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            self._last_body = body
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def do_GET(self):
        if self.path.startswith("/api/tags"):
            self._send(200, {"models": [{"name": "qwen3:8b"}]})
        else:
            self._send(404, {"error": "nope"})

    def do_POST(self):
        if self.path.startswith("/api/chat"):
            self._send(200, {"message": {"content": _FAKE_TOOL}}, read_body=True)
        elif self.path.startswith("/chat/completions"):
            self._send(200, {"choices": [{"message": {"content": "cloud reply"}}]},
                       read_body=True)
        else:
            self._send(404, {"error": "unknown"})


class FakeOllama:
    def __init__(self):
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()

    def base_url(self):
        return f"http://127.0.0.1:{self.port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class OllamaProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeOllama()

    @classmethod
    def tearDownClass(cls):
        cls.fake.close()

    def test_available_true_for_installed_model(self):
        p = OllamaProvider(base_url=self.fake.base_url(),
                           model="qwen3:8b", timeout=5)
        self.assertTrue(p.available())

    def test_available_false_for_missing_model(self):
        p = OllamaProvider(base_url=self.fake.base_url(), model="nope:1b")
        self.assertFalse(p.available())

    def test_chat_returns_content(self):
        p = OllamaProvider(base_url=self.fake.base_url(),
                           model="qwen3:8b", timeout=5)
        self.assertEqual(p.chat("hi"), _FAKE_TOOL)

    def test_plan_parses_tool_action(self):
        p = OllamaProvider(base_url=self.fake.base_url(),
                           model="qwen3:8b", timeout=5)
        plan = p.plan("open chrome")
        self.assertEqual(plan["intent"], "tool")
        self.assertEqual(plan["tool"], "open_application")

    def test_remote_loopback_refused(self):
        p = OllamaProvider(base_url="http://192.0.2.5:11434",
                           model="qwen3:8b", allow_remote=False)
        self.assertFalse(p.available())
        with self.assertRaises(AIBlocked):
            p.chat("hi")


class CloudProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeOllama()

    @classmethod
    def tearDownClass(cls):
        cls.fake.close()

    def setUp(self):
        privacy_state.disable_cloud()

    def tearDown(self):
        privacy_state.disable_cloud()

    def test_cloud_refused_without_approval(self):
        p = CloudAIProvider(base_url=self.fake.base_url(), model="gpt-x",
                            api_key="k")
        self.assertFalse(p.available())
        with self.assertRaises(AIBlocked):
            p.chat("hi")

    def test_cloud_allowed_after_approval(self):
        privacy_state.enable_cloud(True)
        network.approve_scope("ai")
        p = CloudAIProvider(base_url=self.fake.base_url(), model="gpt-x",
                            api_key="k")
        self.assertTrue(p.available())
        self.assertEqual(p.chat("hi"), "cloud reply")


if __name__ == "__main__":
    unittest.main()