"""
Memory store tests: SQLite + session scopes, sensitive-value refusal,
round-tripping, forget/clear/count, and the redactor's secret guards.
Every store here uses a temporary database (never the user's data/memory.db).
"""

import tempfile
import unittest
from pathlib import Path

from memory.store import MemoryStore


class MemoryStorePersistenceTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.db = str(Path(self._dir.name) / "mem.db")
        self.store = MemoryStore(db_path=self.db)

    def tearDown(self):
        self.store.close()
        self._dir.cleanup()

    def test_roundtrip(self):
        self.assertTrue(self.store.remember("user_name", "Priya"))
        self.assertEqual(self.store.get("user_name"), "Priya")

    def test_remember_overwrites(self):
        self.store.remember("favorite_app", "VS Code")
        self.store.remember("favorite_app", "PyCharm")
        self.assertEqual(self.store.get("favorite_app"), "PyCharm")
        self.assertEqual(self.store.count(), 1)

    def test_sensitive_values_are_refused(self):
        for value in ("Bearer ABCdefghijklmnopqrstuvwxyz012345",
                      "sk-proj-mySu8rSecretKeyValues01",
                      "password=hunter22",
                      "-----BEGIN RSA PRIVATE KEY-----",
                      "AKIAIOSFODNN7EXAMPLE"):
            key = "thing"
            self.assertFalse(
                self.store.remember(key, value),
                msg=f"store accepted sensitive value {value!r}")
        self.assertEqual(self.store.count(), 0)

    def test_sensitive_keys_are_refused(self):
        self.assertFalse(self.store.remember("api_key_openai", "k"))
        self.assertFalse(self.store.remember("password", "pw"))
        self.assertFalse(self.store.remember("auth_token", "t"))

    def test_forget_returns_only_existing(self):
        self.store.remember("a", "1")
        self.assertTrue(self.store.forget("a"))
        self.assertFalse(self.store.forget("a"))

    def test_clear(self):
        self.store.remember("a", "1")
        self.store.remember("b", "2")
        self.assertEqual(self.store.clear(), 2)
        self.assertEqual(self.store.count(), 0)

    def test_all_and_context_facts(self):
        self.store.remember("user_name", "Rohan", kind="name")
        self.store.remember("favorite_app_vs code", "VS Code", kind="app")
        facts = self.store.context_facts()
        self.assertIn("Rohan", facts)
        self.assertIn("VS Code", facts)


class MemoryStoreSessionTests(unittest.TestCase):
    def test_memory_only_scope_never_persists(self):
        store = MemoryStore(memory_only=True)
        self.assertTrue(store.remember("x", "y"))
        self.assertEqual(store.get("x"), "y")
        self.assertEqual(store.clear(), 1)
        store2 = MemoryStore(memory_only=True)
        self.assertIsNone(store2.get("x"))


if __name__ == "__main__":
    unittest.main()