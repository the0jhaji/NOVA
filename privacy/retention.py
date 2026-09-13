"""
NOVA Voice Assistant - Data Retention & Clear NOVA Data
Default retention policy (see README.md / Privacy):
  conversation history  -> in-memory for this session only (optional: disk)
  voice recordings      -> NOT STORED
  screenshots           -> NOT STORED unless explicitly requested
  AI prompts/responses  -> local only
  temporary files       -> deleted automatically when no longer required
"""

import shutil
from pathlib import Path

from utils.logger import log

ROOT = Path(__file__).parent.parent
TEMP_DIR = ROOT / "data"
MODEL_CACHE = ROOT / "models"


def temp_artifacts_dir() -> Path:
    TEMP_DIR.mkdir(exist_ok=True)
    return TEMP_DIR


def cleanup_dirs() -> None:
    """Delete temporary/transient artifacts. Keeps .env and model cache."""
    for p in (TEMP_DIR,):
        if p.exists():
            try:
                shutil.rmtree(p, ignore_errors=True)
                log.info("Temporary artifacts removed")
            except Exception as e:
                log.warning("Could not clear temp dir: %s", e)


def clear_nova_data() -> dict:
    """Public entry point for Settings → Privacy → Clear NOVA Data."""
    removed = {"conversation_history": True,
               "temporary_files": True}
    cleanup_dirs()
    # Conversation history lives in-memory; handlers reset it separately.
    return removed


def retention_mode() -> str:
    from privacy.state import privacy_state
    return privacy_state.conversation_retention


def should_store_history() -> bool:
    return retention_mode() == "disk"


def append_conversation(role: str, text: str, timestamp: str) -> None:
    """Persist a conversation entry ONLY when the user opted into disk
    retention (PRIVACY_CONVERSATION_RETENTION=disk). Default is memory-only."""
    if not should_store_history():
        return
    import json
    try:
        log_dir = ROOT / "data" / "conversations"
        log_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        fname = log_dir / f"sessions_{datetime.now():%Y%m%d}.jsonl"
        with open(fname, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"role": role, "text": text,
                                 "ts": timestamp}, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("Conversation disk write skipped: %s", e)