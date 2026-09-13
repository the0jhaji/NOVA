"""
NOVA Voice Assistant - Memory Package
Local persistent memory (SQLite) for preferences and context, private by
default. Secrets are refused at the store boundary; "session" scope keeps
everything in-memory; everything is cleared from Settings → Memory.
"""

from memory.store import MemoryStore, memory_store

__all__ = ["MemoryStore", "memory_store"]