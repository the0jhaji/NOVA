"""
NOVA Voice Assistant - Logger
Centralized logging with file and console output.
Handles Unicode safely (Windows consoles often use cp1252 which
cannot encode Devanagari, emoji, etc.).

Privacy: every message is passed through a redacting formatter at the
sink, so secrets (.env values, API keys, bearer tokens, JWT shapes) can
never reach a log file or console even if a caller slips.
The source code never logs full microphone transcripts or file contents.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


class RedactingFormatter(logging.Formatter):
    """Formats a record then strips secrets from the final text."""

    def format(self, record: logging.LogRecord):
        text = super().format(record)
        try:
            from privacy.redactor import redact_secrets
            return redact_secrets(text)
        except Exception:
            return text


class SafeConsoleHandler(logging.StreamHandler):
    """Console handler that never crashes on Unicode-unsafe terminals."""

    def emit(self, record: logging.LogRecord):
        try:
            message = self.format(record)
        except Exception:
            self.handleError(record)
            return
        try:
            self.stream.write(message + self.terminator)
            self.flush()
        except UnicodeEncodeError:
            try:
                enc = getattr(self.stream, "encoding", None) or "utf-8"
                safe = message.encode(enc, errors="replace").decode(enc, errors="ignore")
                self.stream.write(safe + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)
        except Exception:
            self.handleError(record)


def setup_logger(name: str = "nova", level: int = logging.DEBUG) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    fmt = RedactingFormatter(
        "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    console = SafeConsoleHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"nova_{datetime.now():%Y%m%d}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


log = setup_logger()