"""
Brain memory integration tests: remember / recall / forget / clear through
the natural-language pipeline, plus the privacy guarantee that nothing
sensitive ever lands in memory. Uses a temporary store patched onto the
brain module so the real data/memory.db is never touched.
"""

import tempfile
import unittest
from pathlib import Path

import brain.agent as brain_module
from brain.agent import NovaAgent
from memory.store import MemoryStore


class BrainMemoryTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.store = MemoryStore(db_path=str(Path(self._dir.name) / "mem.db"))
        brain_module.memory_store = self.store
        self.agent = NovaAgent()

    def tearDown(self):
        brain_module.memory_store = brain_module.memory_store  # keep patched
        self.store.close()
        self._dir.cleanup()

    def _test_remember(self, phrase):
        agent = self.agent
        brain_module.memory_store = self.store
        resp, action = agent.process(phrase)
        self.assertEqual(action, "speak")
        self.assertTrue(agent.last_action_ok)
        self.assertGreater(self.store.count(), 0, msg=resp)

    def test_remember_english_that(self):
        self._test_remember("remember that I drink coffee in the morning")

    def test_remember_name(self):
        self._test_remember("my name is Priya")
        self.assertEqual(self.store.get("user_name"), "Priya")

    def test_remember_favorite_app(self):
        self._test_remember("I mostly use VS Code")
        self.assertIsNotNone(self.store.get("user_favorite_app_vs code"))

    def test_remember_hinglish(self):
        self._test_remember("yaad rakho main chai peeta hoon")

    def test_recall_when_empty(self):
        resp, action = self.agent.process("what do you remember")
        self.assertEqual(action, "speak")
        self.assertIn("empty", resp.lower())

    def test_recall_lists_facts(self):
        self.agent.process("my name is Rohan")
        resp, action = self.agent.process("what do you remember")
        self.assertIn("Rohan", resp)

    def test_forget_specific(self):
        self.agent.process("my name is Rohan")
        resp, action = self.agent.process("forget my name")
        self.assertIn("forgotten", resp.lower())
        self.assertEqual(self.store.get("user_name"), None)

    def test_clear_memory(self):
        self.agent.process("my name is Rohan")
        resp, action = self.agent.process("clear your memory")
        self.assertEqual(self.store.count(), 0)

    def test_sensitive_remember_is_refused(self):
        resp, action = self.agent.process("remember my password is hunter2")
        self.assertIn("sensitive", resp.lower())
        self.assertEqual(self.store.count(), 0)


class BrainMemoryPrivacyTests(unittest.TestCase):
    """The cloud path must never receive memory context."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.store = MemoryStore(db_path=str(Path(self._dir.name) / "mem.db"))
        brain_module.memory_store = self.store
        self.store.remember("user_name", "Priya")

    def tearDown(self):
        self.store.close()
        self._dir.cleanup()

    def test_local_facts_inject_into_prompt(self):
        seen = []
        class FakeLocal:
            kind = "local"
            name = "fake-local"
            def plan(self, text):
                seen.append(text)
                return None
        agent = NovaAgent()
        agent.ai = FakeLocal()
        agent.process("what should I watch today")
        self.assertEqual(len(seen), 1)
        self.assertIn("user_name", seen[0])
        self.assertIn("Priya", seen[0])

    def test_cloud_prompt_has_no_memory(self):
        seen = []
        class FakeCloud:
            kind = "cloud"
            name = "fake-cloud"
            def plan(self, text):
                seen.append(text)
                return None
        agent = NovaAgent()
        agent.ai = FakeCloud()
        agent.process("what should I watch today")
        self.assertEqual(len(seen), 1)
        self.assertNotIn("Priya", seen[0])
        self.assertNotIn("user_name", seen[0])


if __name__ == "__main__":
    unittest.main()