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
            super().emit(record)
        except UnicodeEncodeError:
            # Fall back: encode with replacement to lossy ASCII
            message = self.format(record)
            try:
                safe = message.encode(sys.stdout.encoding or "utf-8",
                                      errors="replace").decode(
                    sys.stdout.encoding or "utf-8", errors="ignore")
                sys.stdout.write(safe + "\n")
                sys.stdout.flush()
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