"""
Brain intent tests: multilingual natural-language -> controlled tool mapping,
confirmation flow, honest failure, and quit behaviour.

All tools are mocked so the suite never touches the real desktop.
"""

import unittest

from automation import AutomationEngine, ToolResult
from automation.result import ActionStep
from brain.agent import NovaAgent


class BrainIntentTests(unittest.TestCase):

    def setUp(self):
        self.calls = []
        self.engine = AutomationEngine()
        self.agent = NovaAgent(automation=self.engine)
        for tool in ("open_application", "close_application", "open_url",
                     "open_folder", "create_folder", "create_file",
                     "take_screenshot", "move_file", "copy_file",
                     "rename_file", "search_files"):
            self.engine.register_tool(
                tool, lambda p, t=tool: self._record(t, p))
        self.engine.register_tool(
            "volume_control", lambda p: self._record("volume_control", p))
        self.engine.register_tool(
            "press_key", lambda p: self._record("press_key", p))
        self.engine.register_tool(
            "delete_file", lambda p: self._record("delete_file", p))

    def _record(self, name, params):
        self.calls.append((name, dict(params)))
        return ToolResult(tool=name, success=True, verified=True, message=f"{name}:ok")

    def assert_execute(self, resp, action):
        self.assertEqual(action, "execute", f"expected execute, got {action!r}: {resp}")

    # ------------------------------------------------------------------ apps
    def test_open_chrome_english(self):
        resp, action = self.agent.process("Open Chrome")
        self.assert_execute(resp, action)
        self.assertTrue(self.agent.last_action_ok)

    def test_open_chrome_hinglish(self):
        self.agent.process("Chrome kholo")
        self.assertTrue(self.agent.last_action_ok)

    def test_open_chrome_devanagari(self):
        self.agent.process("क्रोम खोलो")
        self.assertTrue(self.agent.last_action_ok)

    def test_open_vs_code_compound(self):
        resp, action = self.agent.process("Open VS Code and create a new file")
        self.assert_execute(resp, action)
        tools = [c[0] for c in self.calls]
        self.assertIn("open_application", tools)
        self.assertIn("press_key", tools)
        press = [c[1] for c in self.calls if c[0] == "press_key"][0]
        self.assertEqual(press.get("keys"), ["ctrl", "n"])

    def test_close_notepad(self):
        resp, action = self.agent.process("Close Notepad")
        self.assert_execute(resp, action)

    # ------------------------------------------------------------------ web / folders
    def test_open_youtube(self):
        self.agent.process("Open YouTube")
        self.assertTrue(self.agent.last_action_ok)

    def test_open_downloads(self):
        self.agent.process("Open Downloads")
        self.assertTrue(self.agent.last_action_ok)

    # ------------------------------------------------------------- create folder
    def test_create_folder_desktop_named(self):
        self.agent.process("Desktop pe ek folder banao naam Projects")
        calls = [c for c in self.calls if c[0] == "create_folder"]
        self.assertTrue(calls, self.calls)
        params = calls[-1][1]
        self.assertEqual(params.get("name"), "Projects")

    def test_create_folder_downloads_in(self):
        self.agent.process("Downloads mein Python folder banao")
        calls = [c for c in self.calls if c[0] == "create_folder"]
        self.assertTrue(calls)
        name = calls[-1][1].get("name", "").lower()
        self.assertIn("python", name)

    def test_create_folder_desktop_create_karo_named(self):
        self.agent.process("Desktop par ek folder create karo named NOVA")
        calls = [c for c in self.calls if c[0] == "create_folder"]
        self.assertTrue(calls)
        self.assertEqual(calls[-1][1].get("name"), "NOVA")

    # ------------------------------------------------------------------ volume
    def test_volume_50_percent(self):
        self.agent.process("Volume 50 percent karo")
        calls = [c[1] for c in self.calls if c[0] == "volume_control"]
        self.assertTrue(calls)
        params = calls[-1]
        self.assertEqual(params.get("value"), 50)

    def test_volume_thoda_kam(self):
        self.agent.process("Volume thoda kam karo")
        calls = [c[1] for c in self.calls if c[0] == "volume_control"]
        self.assertTrue(calls)
        self.assertEqual(calls[-1].get("action"), "down")

    # ------------------------------------------------------------- screenshot
    def test_screenshot(self):
        self.agent.process("Take a screenshot")
        self.assertTrue(self.agent.last_action_ok)

    # ------------------------------------------------------------- confirmation
    def test_delete_requires_confirmation_then_runs(self):
        resp, action = self.agent.process("delete file hello.txt")
        self.assertEqual(action, "speak", "delete must ask first")
        self.assertFalse(self.agent.last_action_ok)
        self.assertIsNotNone(self.agent._pending_plan)

        resp2, action2 = self.agent.process("yes")
        self.assert_execute(resp2, action2)
        self.assertTrue(any(c[0] == "delete_file" for c in self.calls))
        self.assertIsNone(self.agent._pending_plan)

    def test_confirmation_cancel(self):
        self.agent.process("delete file hello.txt")
        resp, action = self.agent.process("cancel")
        self.assertEqual(action, "speak")
        self.assertFalse(any(c[0] == "delete_file" for c in self.calls))
        self.assertIsNone(self.agent._pending_plan)

    # ------------------------------------------------------------- high risk
    def test_high_risk_refused(self):
        resp, action = self.agent.process("format the system drive")
        self.assertEqual(action, "speak")
        self.assertIn("too risky", resp.lower())
        self.assertFalse(self.agent.last_action_ok)
        self.assertEqual(self.calls, [], "no tool should run")

    def test_refusal_resets_previous_success(self):
        self.agent.process("Open Chrome")
        self.assertTrue(self.agent.last_action_ok)
        resp, action = self.agent.process("wipe the disk")
        self.assertEqual(action, "speak")
        self.assertFalse(self.agent.last_action_ok,
                         "refusal must clear the previous success flag")

    def test_delete_in_protected_area_refused(self):
        resp, action = self.agent.process("delete file C:\\Windows\\System32\\dwm.exe")
        self.assertEqual(action, "speak")
        self.assertFalse(self.agent.last_action_ok)
        self.assertEqual([c[0] for c in self.calls], [])

    # ------------------------------------------------------------- quit
    def test_quit(self):
        resp, action = self.agent.process("bye")
        self.assertEqual(action, "quit")


class YouTubeVideoIntentTests(unittest.TestCase):
    """Video/YouTube requests must go to the browser, never open_application."""

    def setUp(self):
        self.calls = []
        self.engine = AutomationEngine()
        self.agent = NovaAgent(automation=self.engine)
        for tool in ("open_application", "browser_open_url", "browser_search"):
            self.engine.register_tool(
                tool, lambda p, t=tool: self._record(t, p))

    def _record(self, name, params):
        self.calls.append((name, dict(params)))
        return ToolResult(tool=name, success=True, verified=True,
                          message=f"{name}:ok")

    def tool_calls(self, name):
        return [{k: v for k, v in p.items() if k != "tool"}
                for t, p in self.calls if t == name]

    def test_open_a_video_in_youtube_opens_youtube(self):
        resp, action = self.agent.process("open a video in YouTube")
        self.assertEqual(action, "execute")
        urls = self.tool_calls("browser_open_url")
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0]["url"], "youtube.com")
        self.assertEqual(self.tool_calls("open_application"), [])

    def test_open_a_video_on_youtube_opens_youtube(self):
        resp, action = self.agent.process("open a video on YouTube")
        self.assertEqual(action, "execute")
        self.assertEqual(self.tool_calls("browser_open_url")[0]["url"],
                         "youtube.com")

    def test_watch_a_video_opens_youtube(self):
        resp, action = self.agent.process("watch a video on youtube")
        self.assertEqual(action, "execute")
        self.assertEqual(self.tool_calls("browser_open_url")[0]["url"],
                         "youtube.com")

    def test_play_title_on_youtube_searches(self):
        resp, action = self.agent.process("play baby shark on YouTube")
        self.assertEqual(action, "execute")
        searches = self.tool_calls("browser_search")
        self.assertEqual(len(searches), 1)
        self.assertEqual(searches[0], {"query": "baby shark",
                                       "engine": "youtube"})

    def test_play_title_video_on_youtube_searches(self):
        resp, action = self.agent.process(
            "play cricket highlights video on youtube")
        self.assertEqual(action, "execute")
        searches = self.tool_calls("browser_search")
        self.assertEqual(len(searches), 1)
        self.assertEqual(searches[0]["query"], "cricket highlights")
        self.assertEqual(searches[0]["engine"], "youtube")

    def test_open_app_still_opens_app(self):
        resp, action = self.agent.process("open chrome")
        self.assertEqual(action, "execute")
        self.assertEqual(len(self.tool_calls("open_application")), 1)
        self.assertEqual(self.tool_calls("open_application")[0]["name"],
                         "chrome")


if __name__ == "__main__":
    unittest.main()