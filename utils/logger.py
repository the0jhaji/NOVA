"""
NOVA Voice Assistant - Logger
Centralized logging with file and console output.
Handles Unicode safely (Windows consoles often use cp1252 which
cannot encode Devanagari, emoji, etc.).
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


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
    fmt = logging.Formatter(
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