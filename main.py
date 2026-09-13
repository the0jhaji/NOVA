"""
NOVA Voice Assistant - Entry Point
Launches the main window and starts the Qt event loop.
"""

import sys

from PyQt6.QtWidgets import QApplication

from config import config
from utils.logger import log
from ui.main_window import MainWindow


def main():
    # High-DPI-friendly app setup
    app = QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setApplicationVersion(config.app_version)

    # Try to enable modern style
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("nova.voice.assistant.1")
    except Exception:
        pass

    log.info("Starting %s v%s", config.app_name, config.app_version)
    log.info("STT=%s TTS=%s wake=%s", config.stt.provider, config.tts.provider,
             config.wake_word.word if config.wake_word.enabled else "OFF")

    window = MainWindow()

    # Center on primary screen
    screen = app.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        window.move(
            geo.x() + (geo.width() - window.width()) // 2,
            geo.y() + (geo.height() - window.height()) // 2,
        )

    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())