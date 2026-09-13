"""
Browser automation tests.

Primary tests exercise the tool layer through a stubbed BrowserController so
the suite never launches a real browser. A single optional test launches a
real headless Edge/Chrome and is skipped when no browser binary exists.
"""

import os
import re
import shutil
import unittest

from automation.result import ToolResult, ActionStep
from automation.safety import RiskLevel, classify, TOOL_BASE_RISK
from automation.tools import build_registry


class _StubBrowser:
    def __init__(self):
        self.last_url = ""
        self.page_text = "This is a live website heading. Unrelated body."
        self.clicks = []

    def navigate(self, url):
        self.last_url = url
        self.page_text = "Loaded: " + url
        return self.page_text

    def visible_text(self, limit=2000):
        return self.page_text[:limit]

    def scroll(self, direction, amount=900):
        return direction

    def click_text(self, text):
        self.clicks.append(text)
        return text.lower() in "Button".lower() or text == "Go"

    def click_selector(self, sel):
        return sel == "#go"

    def type_text(self, text, submit=True):
        return bool(text)


class BrowserToolContractTests(unittest.TestCase):
    def setUp(self):
        from automation.tools import browser as _b
        self._real = _b.get_browser
        self.stub = _StubBrowser()
        _b.get_browser = lambda: self.stub
        self.registry = build_registry()

    def tearDown(self):
        from automation.tools import browser as _b
        _b.get_browser = self._real

    def test_registry_has_browser_tools(self):
        for name in ("browser_open_url", "browser_search", "browser_read",
                     "browser_scroll", "browser_click", "browser_type"):
            self.assertIn(name, self.registry)

    def _run(self, name, params):
        return self.registry[name]({"tool": name, **(params or {})})

    def test_open_url(self):
        r = self._run("browser_open_url", {"url": "example.com"})
        self.assertTrue(r.ok, r.message)
        self.assertIn("example.com", r.message)

    def test_search_builds_youtube_query(self):
        from automation.tools import browser as _b
        r = self._run("browser_search",
                      {"query": "rainy day songs", "engine": "youtube"})
        self.assertTrue(r.ok, r.message)
        self.assertIn("youtube.com/results", _b.get_browser().last_url)

    def test_search_builds_google_query(self):
        from automation.tools import browser as _b
        r = self._run("browser_search", {"query": "weather today"})
        self.assertTrue(r.ok, r.message)
        self.assertIn("google.com/search", _b.get_browser().last_url)

    def test_read_marks_untrusted(self):
        r = self._run("browser_read", {})
        self.assertTrue(r.ok, r.message)
        self.assertIn("untrusted", r.message)
        self.assertTrue(r.details.get("untrusted", False))

    def test_click_missing_shows_failure(self):
        r = self._run("browser_click", {"text": "NopeNope"})
        self.assertFalse(r.ok)

    def test_click_found_ok(self):
        r = self._run("browser_click", {"text": "Go"})
        self.assertTrue(r.ok, r.message)

    def test_type_reports_submit(self):
        r = self._run("browser_type", {"text": "hello", "submit": True})
        self.assertTrue(r.ok, r.message)
        self.assertIn("submitted", r.message)

    def test_missing_param_fails(self):
        self.assertFalse(self._run("browser_search", {}).ok)
        self.assertFalse(self._run("browser_click", {}).ok)


class BrowserRiskTests(unittest.TestCase):
    def test_base_risk_levels(self):
        self.assertEqual(TOOL_BASE_RISK["browser_search"], RiskLevel.SAFE)
        self.assertEqual(TOOL_BASE_RISK["browser_read"], RiskLevel.SAFE)
        self.assertEqual(TOOL_BASE_RISK["browser_scroll"], RiskLevel.SAFE)
        self.assertEqual(TOOL_BASE_RISK["browser_open_url"], RiskLevel.SAFE)
        self.assertEqual(TOOL_BASE_RISK["browser_click"],
                         RiskLevel.CONFIRMATION_REQUIRED)
        self.assertEqual(TOOL_BASE_RISK["browser_type"],
                         RiskLevel.CONFIRMATION_REQUIRED)

    def test_classify_respects_frame(self):
        self.assertEqual(
            classify("search for rain songs on youtube",
                     "browser_search", {"query": "rain songs"}),
            RiskLevel.SAFE)
        self.assertEqual(
            classify("click the button", "browser_click", {"text": "Button"}),
            RiskLevel.CONFIRMATION_REQUIRED)

    def test_high_risk_never_flows_into_browser(self):
        self.assertEqual(
            classify("delete system files", "browser_search",
                     {"query": "x"}),
            RiskLevel.HIGH_RISK)


def _find_browser_binary():
    candidates = [
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    ]
    return next((c for c in candidates if os.path.isfile(c)), None)


@unittest.skipUnless(_find_browser_binary(),
                     "No Edge/Chrome binary installed on this machine")
class RealBrowserCdpTests(unittest.TestCase):
    def setUp(self):
        from automation.browser_tools import BrowserController
        self.controller = BrowserController(channel="auto", headless=True,
                                            port=0)
        # port 0 is invalid; pick a free port to avoid clashing with a live
        # browser the user may already have open on the default.
        import socket
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        self.controller.port = sock.getsockname()[1]
        sock.close()

    def tearDown(self):
        self.controller.stop()

    def test_navigate_and_read(self):
        self.controller.navigate("https://example.com")
        text = self.controller.visible_text(limit=400)
        self.assertIn("Example Domain", text)


if __name__ == "__main__":
    unittest.main()