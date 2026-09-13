"""
NOVA Voice Assistant - Persistent Memory Store (SQLite)
Local memory for preferences, app usage, name, language and conversation
context. Everything stays on this machine.

Privacy rules enforced here (not by the caller):
- The store REFUSES anything that looks sensitive (passwords, API keys,
  tokens, JWT/credential shapes, .env secret values) via the privacy
  redactor - secrets are never written to memory.
- "session" scope keeps everything in-memory only (forgotten on exit).

Schema: memory(kind TEXT, key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)
"""

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from utils.logger import log
from privacy.redactor import looks_sensitive

DEFAULT_KINDS = ("pref", "app", "language", "name", "fact", "context")

_FORBIDDEN_KEY_HINT = (
    "password", "passwd", "pwd", "token", "api_key", "apikey", "secret",
    "private", "credential", "key=",
)


class MemoryStore:
    def __init__(self, db_path: str = "", memory_only: bool = False):
        self.memory_only = memory_only
        self._mem: dict[str, dict] = {}
        self._conn = None
        if not memory_only:
            try:
                path = db_path or str(
                    Path(__file__).parent.parent / "data" / "memory.db")
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                self._conn = sqlite3.connect(path, check_same_thread=False)
                self._conn.execute(
                    "CREATE TABLE IF NOT EXISTS memory ("
                    " kind TEXT NOT NULL, key TEXT PRIMARY KEY,"
                    " value TEXT NOT NULL, updated_at TEXT NOT NULL)")
                self._conn.commit()
            except Exception as e:
                log.warning("Memory DB unavailable (%s) - falling back to "
                            "in-memory for this session", e)
                self._conn = None
                self.memory_only = True

    def _now(self) -> str:
        return datetime.now().isoformat()

    # ------------------------------------------------------------- guards
    def _safe(self, key: str, value: str) -> bool:
        if not value or not isinstance(value, str):
            return False
        hay = f"{key} {value}"
        if looks_sensitive(hay):
            return False
        low = key.lower()
        return not any(h in low for h in _FORBIDDEN_KEY_HINT)

    # ---------------------------------------------------------------- API
    def remember(self, key: str, value: str, kind: str = "fact") -> bool:
        """Store a fact. Returns False (without writing) if it looks
        sensitive or the key/value are unusable."""
        key = key.strip().lower()
        value = value.strip()
        if not self._safe(key, value):
            log.info("Memory store refused entry '%s' (sensitive/blank)",
                     key)
            return False
        now = self._now()
        if self.memory_only:
            self._mem[key] = {"key": key, "value": value, "kind": kind,
                              "updated_at": now}
            return True
        try:
            self._conn.execute(
                "INSERT INTO memory (kind, key, value, updated_at)"
                " VALUES (?,?,?,?)"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value,"
                " kind=excluded.kind, updated_at=excluded.updated_at",
                (kind, key, value, now))
            self._conn.commit()
            return True
        except Exception as e:
            log.warning("Memory write failed: %s", e)
            return False

    def get(self, key: str) -> Optional[str]:
        key = key.strip().lower()
        if self.memory_only:
            entry = self._mem.get(key)
            return entry["value"] if entry else None
        try:
            cur = self._conn.execute(
                "SELECT value FROM memory WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row else None
        except Exception:
            return None

    def all(self) -> List[dict]:
        if self.memory_only:
            return list(self._mem.values())
        try:
            cur = self._conn.execute(
                "SELECT kind, key, value, updated_at FROM memory"
                " ORDER BY updated_at DESC")
            return [{"kind": r[0], "key": r[1], "value": r[2],
                     "updated_at": r[3]} for r in cur.fetchall()]
        except Exception:
            return []

    def forget(self, key: str) -> bool:
        key = key.strip().lower()
        if self.memory_only:
            return self._mem.pop(key, None) is not None
        try:
            cur = self._conn.execute("DELETE FROM memory WHERE key=?", (key,))
            self._conn.commit()
            return cur.rowcount > 0
        except Exception:
            return False

    def clear(self) -> int:
        if self.memory_only:
            n = len(self._mem)
            self._mem.clear()
            return n
        try:
            cur = self._conn.execute("DELETE FROM memory")
            self._conn.commit()
            return cur.rowcount
        except Exception:
            return 0

    def count(self) -> int:
        try:
            cur = self._conn.execute("SELECT COUNT(*) FROM memory")
            return int(cur.fetchone()[0])
        except Exception:
            return 0

    def context_facts(self, limit: int = 10) -> str:
        """Short, redacted memory digest injected into LOCAL prompts only."""
        entries = self.all()[:limit]
        if not entries:
            return ""
        return " • " + "\n • ".join(
            f"{e['kind']}: {e['key']} = {e['value']}" for e in entries)

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


def _build_store() -> MemoryStore:
    from config import config
    if not config.memory.enabled:
        return MemoryStore(memory_only=True)
    memory_only = config.memory.scope == "session"
    return MemoryStore(db_path=config.memory.db_path, memory_only=memory_only)


memory_store = _build_store()