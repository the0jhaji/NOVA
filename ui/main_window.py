"""
NOVA Voice Assistant - Main Window
The main desktop command center UI.
Wires together the orb, waveform, voice pipeline, and brain.

Threading model:
- Voice listener: background thread (captures audio, transcribes)
- Command processing: background thread (brain + simulated execution)
- TTS: background thread (speech synthesis + playback)
- UI: main thread only (updated via bridge signals)
"""

import threading
import time
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextBrowser, QGraphicsDropShadowEffect, QInputDialog,
)

from config import config
from utils.logger import log
from ui.nova_orb import NovaOrb, STATE_COLORS
from ui.waveform import WaveformWidget
from ui.styles.theme import QSS as THEME_QSS
from voice.listener import Listener
from voice.text_to_speech import create_tts_provider
from brain.agent import NovaAgent

# Map text keywords to simulated app opens
EXECUTE_APP_MAP = {
    "chrome": "Chrome",
    "notepad": "Notepad",
    "calculator": "Calculator",
    "youtube": "YouTube in your browser",
    "browser": "your default browser",
}


class VoiceBridge(QObject):
    """
    Cross-thread signal bridge.
    Worker threads must NOT touch UI widgets directly; they emit signals
    which are queued and handled on the main (UI) thread.
    """

    state_changed = pyqtSignal(str)
    text_captured = pyqtSignal(str)          # user speech recognized
    response_ready = pyqtSignal(str)         # NOVA reply text
    action_triggered = pyqtSignal(str)       # action type + detail
    error_occurred = pyqtSignal(str)
    audio_level = pyqtSignal(float)
    shutdown_requested = pyqtSignal()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NOVA")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_offset: Optional[tuple[int, int]] = None
        self._is_closing = False

        # Core components
        self.brain = NovaAgent()
        self.tts = create_tts_provider()
        self.bridge = VoiceBridge()
        self.listener = Listener()

        self._latest_response: str = ""

        self._build_ui()
        self._wire_signals()
        self._init_listener()

        QTimer.singleShot(1500, self._startup_message)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        self.panel = QFrame()
        self.panel.setObjectName("main_panel")
        self.panel.setStyleSheet("""
            QFrame#main_panel {
                background-color: rgba(14, 18, 32, 0.92);
                border: 1px solid rgba(0, 180, 216, 0.15);
                border-radius: 18px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setColor(QColor(0, 180, 216, 28))
        shadow.setOffset(0, 0)
        self.panel.setGraphicsEffect(shadow)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(24, 10, 24, 20)
        panel_layout.setSpacing(0)

        panel_layout.addLayout(self._build_titlebar())
        panel_layout.addSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(24)
        top.addLayout(self._build_system_panel(), 1)
        top.addLayout(self._build_orb_column(), 2)
        top.addLayout(self._build_chat_panel(), 1)
        panel_layout.addLayout(top)
        panel_layout.addSpacing(14)

        panel_layout.addLayout(self._build_state_bar())
        panel_layout.addSpacing(6)
        panel_layout.addLayout(self._build_controls())

        central.setLayout(outer)
        outer.addWidget(self.panel)

        self.setFixedSize(1000, 640)

    def _build_titlebar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 0, 0)

        brand = QHBoxLayout()
        brand.setSpacing(10)

        title = QLabel("N O V A")
        title.setStyleSheet("""
            color: #e8f6ff;
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 4px;
        """)
        brand.addWidget(title)

        self.connection_dot = QLabel("●")
        self.connection_dot.setStyleSheet("color: #00ff88; font-size: 10px;")
        brand.addWidget(self.connection_dot)

        self.status_label = QLabel("SYSTEM ONLINE")
        self.status_label.setStyleSheet("color: #4ad0af; font-size: 10px; letter-spacing: 1px;")
        brand.addWidget(self.status_label)

        brand.addStretch()
        row.addLayout(brand)

        controls = QHBoxLayout()
        controls.setSpacing(6)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("settings_button")
        self.settings_btn.setToolTip("NOVA Settings")
        self.settings_btn.clicked.connect(self._open_settings)
        controls.addWidget(self.settings_btn)

        min_btn = QPushButton("—")
        min_btn.setObjectName("title_min")
        min_btn.clicked.connect(self.showMinimized)
        controls.addWidget(min_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("title_close")
        close_btn.clicked.connect(self.close)
        controls.addWidget(close_btn)

        row.addLayout(controls)
        return row

    def _build_system_panel(self) -> QVBoxLayout:
        panel = QVBoxLayout()
        panel.setSpacing(8)
        panel.setAlignment(Qt.AlignmentFlag.AlignTop)

        sys_title = QLabel("SYSTEM STATUS")
        sys_title.setObjectName("system_title")
        panel.addWidget(sys_title)

        separator = QFrame()
        separator.setObjectName("sys_separator")
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: rgba(255,255,255,0.07);")
        panel.addWidget(separator)
        panel.addSpacing(6)

        sys_items = [
            ("CORE", "NOVA v0.1"),
            ("LANG", config.stt.language.upper()),
            ("STT", config.stt.provider.upper()),
            ("TTS", config.tts.provider.upper()),
            ("WAKE", "ON" if config.wake_word.enabled else "OFF"),
            ("MIC", "READY"),
        ]
        self._system_items = {}
        for key, value in sys_items:
            r = QHBoxLayout()
            r.setSpacing(10)
            key_lbl = QLabel(key)
            key_lbl.setObjectName("sys_key")
            key_lbl.setStyleSheet("color: #7d8b9d; font-size: 12px;")
            val_lbl = QLabel(value)
            val_lbl.setObjectName("sys_value")
            val_lbl.setStyleSheet("color: #4dd0ff; font-size: 12px;")
            self._system_items[key.lower()] = val_lbl
            r.addWidget(key_lbl)
            r.addStretch()
            r.addWidget(val_lbl)
            panel.addLayout(r)

        panel.addSpacing(14)

        hint = QLabel(
            "NOVA is an adaptive AI companion.\n\n"
            "Speak in English, Hindi or Hinglish.\n"
            "Example: \"NOVA, YouTube kholo\""
        )
        hint.setObjectName("idle_hint")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "QLabel#idle_hint { color: #5a6b7a; font-size: 11px; line-height: 1.6; }"
        )
        panel.addWidget(hint)

        panel.addStretch()
        return panel

    def _build_orb_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(4)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.orb = NovaOrb(size=250)
        col.addWidget(self.orb, 0, Qt.AlignmentFlag.AlignCenter)

        self.waveform = WaveformWidget(width=460, height=50)
        self.waveform.setFixedWidth(460)
        col.addWidget(self.waveform, 0, Qt.AlignmentFlag.AlignCenter)

        return col

    def _build_chat_panel(self) -> QVBoxLayout:
        panel = QVBoxLayout()
        panel.setSpacing(8)

        chat_title = QLabel("COMMAND FEED")
        chat_title.setObjectName("conversation_title")
        chat_title.setStyleSheet("color: #7d8b9d; font-size: 11px; font-weight: 600;")
        panel.addWidget(chat_title)

        self.history = QTextBrowser()
        self.history.setObjectName("history_browser")
        self.history.setStyleSheet("""
            QTextBrowser {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 10px;
                color: #c8d8e8;
                padding: 10px;
                font-size: 12px;
            }
        """)
        self.history.setFixedWidth(270)
        panel.addWidget(self.history)

        self.command_label = QLabel("Awaiting command...")
        self.command_label.setObjectName("command_label")
        self.command_label.setWordWrap(True)
        self.command_label.setStyleSheet("""
            QLabel#command_label {
                color: #a8f0ff;
                font-size: 12px;
                padding: 2px 0;
            }
        """)
        panel.addWidget(self.command_label)

        self.response_label = QLabel("")
        self.response_label.setObjectName("response_label")
        self.response_label.setWordWrap(True)
        self.response_label.setStyleSheet("""
            QLabel#response_label {
                color: #d0e0f0;
                font-size: 12px;
                padding: 2px 0;
            }
        """)
        panel.addWidget(self.response_label)

        panel.addStretch()
        return panel

    def _build_state_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        self.state_label = QLabel("● IDLE")
        self.state_label.setObjectName("state_label")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.state_label, 0, Qt.AlignmentFlag.AlignCenter)
        return row

    def _build_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.mic_button = QPushButton("🎤  MICROPHONE")
        self.mic_button.setObjectName("mic_button")
        self.mic_button.clicked.connect(self._toggle_mic)
        row.addWidget(self.mic_button)

        self.text_button = QPushButton("⌨  TYPE COMMAND")
        self.text_button.setObjectName("mic_button")
        self.text_button.clicked.connect(self._handle_text_input)
        row.addWidget(self.text_button)

        return row

    # ------------------------------------------------------------------
    # Signal wiring & listener init
    # ------------------------------------------------------------------
    def _wire_signals(self):
        self.bridge.state_changed.connect(self._set_state)
        self.bridge.text_captured.connect(self._on_text_captured)
        self.bridge.response_ready.connect(self._on_response)
        self.bridge.action_triggered.connect(self._on_action)
        self.bridge.error_occurred.connect(self._on_error)
        self.bridge.audio_level.connect(self._on_audio_level)
        self.bridge.shutdown_requested.connect(self.close)

    def _init_listener(self):
        self.listener.on_state_change = lambda s: self.bridge.state_changed.emit(s)
        self.listener.on_text_captured = lambda t: self.bridge.text_captured.emit(t)
        self.listener.on_error = lambda e: self.bridge.error_occurred.emit(e)
        self.listener.on_audio_level = lambda l: self.bridge.audio_level.emit(l)

        ok = self.listener.initialize()
        if ok:
            import threading
            threading.Thread(target=self.listener.calibrate, daemon=True).start()
            log.info("Microphone ready")
        else:
            self._set_connection(False)
            self._append_history("SYSTEM", "No microphone detected — use TYPE COMMAND.")

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------
    def _startup_message(self):
        self._set_state("IDLE")
        self._append_history(
            "NOVA",
            "SYSTEMS ONLINE. State your command, or use the microphone."
        )

    def _set_state(self, state: str):
        self.orb.state = state
        self.waveform.state = state
        self.state_label.setText(f"● {state}")

        primary = STATE_COLORS.get(state, STATE_COLORS["IDLE"])[0]
        self.state_label.setStyleSheet(
            f"QLabel#state_label {{ color: {primary.name()}; font-size: 13px; "
            f"font-weight: 600; letter-spacing: 2px; }}"
        )

        labels = {
            "LISTENING": "◉ LISTENING",
            "PROCESSING": "… THINKING",
            "SPEAKING": "◉ SPEAKING",
            "EXECUTING": "✓ EXECUTING",
            "ERROR": "⚠ ERROR",
            "IDLE": "READY",
        }
        self._update_sys_item("mic", labels.get(state, "READY"))

    def _on_audio_level(self, level: float):
        self.orb.set_audio_level(level)
        self.waveform.set_audio_level(level)

    def _on_error(self, message: str):
        log.error("Voice pipeline error: %s", message)
        self._set_state("ERROR")
        self._append_history("NOVA", "I had trouble hearing you. Try again?")
        QTimer.singleShot(2500, lambda: self._set_state("IDLE"))

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------
    def _on_text_captured(self, text: str):
        """Voice/captured text arrives on the UI thread."""
        # Wake-word only response
        if text.strip().lower() == config.wake_word.word.lower():
            self.command_label.setText(f"Wake: {text}")
            self._set_state("SPEAKING")
            reply = "Yes?"
            threading.Thread(
                target=self._speak_worker, args=(reply,), daemon=True
            ).start()
            self.bridge.response_ready.emit(reply)
            return

        self._append_history("YOU", text)
        self.command_label.setText(text)
        self._set_state("PROCESSING")

        threading.Thread(
            target=self._process_worker,
            args=(text,),
            daemon=True,
        ).start()

    _latest_response: str = ""

    def _process_worker(self, text: str):
        """Background: run the brain and emit results on the bridge."""
        try:
            time.sleep(0.35)  # brief perceived "thinking" delay
            response, action = self.brain.process(text)

            self._latest_response = response
            self.bridge.response_ready.emit(response)

            if action == "execute":
                self.bridge.action_triggered.emit(text)
            elif action == "quit":
                self.bridge.state_changed.emit("SPEAKING")
                self._speak_worker(response)
                QTimer.singleShot(2000, self.bridge.shutdown_requested.emit)
            else:
                self.bridge.state_changed.emit("SPEAKING")
                self._speak_worker(response)
                self.bridge.state_changed.emit("IDLE")
        except Exception as e:
            log.error("Brain processing failed: %s", e)
            self.bridge.error_occurred.emit(str(e))

    def _on_response(self, text: str):
        self.response_label.setText(text)

    def _on_action(self, command: str):
        """Simulated execution indicator (Phase 2 replaces with real automation)."""
        text = command.lower()
        app = None
        for key in EXECUTE_APP_MAP:
            if key in text:
                app = EXECUTE_APP_MAP[key]
                break

        self._set_state("EXECUTING")
        if app:
            log.info("SIMULATED ACTION: opening %s", app)
            self._append_history(
                "SYSTEM",
                f"[SIMULATED] Opening {app} — real automation in Phase 2",
            )
        else:
            self._append_history("SYSTEM", "[SIMULATED] Executing action")

        threading.Thread(
            target=self._execute_pipeline, args=(app,), daemon=True
        ).start()

    def _execute_pipeline(self, app: Optional[str]):
        """Background: show EXECUTING briefly, then speak and idle."""
        time.sleep(0.9)
        self.bridge.state_changed.emit("SPEAKING")
        reply = self._latest_response or (
            f"Opening {app}." if app else "Done."
        )
        self._speak_worker(reply)
        self.bridge.state_changed.emit("IDLE")

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------
    def _speak_worker(self, text: str):
        try:
            self.tts.speak(text)
        except Exception as e:
            log.error("TTS failed: %s", e)
            self.bridge.error_occurred.emit(str(e))

    # ------------------------------------------------------------------
    # Input controls
    # ------------------------------------------------------------------
    def _toggle_mic(self):
        if self.listener.listening:
            self.listener.stop()
            self.mic_button.setProperty("active", "false")
            self._set_state("IDLE")
        else:
            self.listener.start()
            self.mic_button.setProperty("active", "true")
            self._set_state("LISTENING")
        self.mic_button.style().unpolish(self.mic_button)
        self.mic_button.style().polish(self.mic_button)

    def _handle_text_input(self):
        text, ok = QInputDialog.getText(
            self, "NOVA Command", "Enter a command:", text="Hello NOVA"
        )
        if ok and text.strip():
            self._append_history("YOU", text)
            self.command_label.setText(text.strip())
            self._set_state("PROCESSING")
            threading.Thread(
                target=self._process_worker, args=(text.strip(),), daemon=True
            ).start()

    def _open_settings(self):
        self._append_history(
            "SYSTEM", "Settings panel coming in a later phase. Edit .env to configure NOVA."
        )

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _update_sys_item(self, key: str, value: str):
        lbl = self._system_items.get(key)
        if lbl:
            lbl.setText(value)

    def _set_connection(self, online: bool):
        if online:
            self.connection_dot.setStyleSheet("color: #00ff88; font-size: 10px;")
            self.status_label.setText("SYSTEM ONLINE")
            self.status_label.setStyleSheet("color: #4ad0af; font-size: 10px;")
        else:
            self.connection_dot.setStyleSheet("color: #ff5252; font-size: 10px;")
            self.status_label.setText("CONNECTION LOST")
            self.status_label.setStyleSheet("color: #ff5252; font-size: 10px;")

    def _append_history(self, speaker: str, text: str):
        if speaker == "YOU":
            entry = (
                f'<span style="color:#7fd8ff;">▸ YOU</span> &nbsp;'
                f'<b style="color:#e8f6ff;">{text}</b>'
            )
        elif speaker == "SYSTEM":
            entry = (
                f'<span style="color:#ffc107;">⚡ SYSTEM</span> &nbsp;'
                f'<span style="color:#b0bec5;">{text}</span>'
            )
        else:
            entry = (
                f'<span style="color:#ff6b9d;">◉ NOVA</span> &nbsp;'
                f'<b style="color:#a8f0ff;">{text}</b>'
            )
        self.history.append(entry)
        scrollbar = self.history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ------------------------------------------------------------------
    # Window behavior
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                int(event.globalPosition().x()) - self.x(),
                int(event.globalPosition().y()) - self.y(),
            )

    def mouseMoveEvent(self, event):
        if self._drag_offset:
            dx = int(event.globalPosition().x()) - self._drag_offset[0]
            dy = int(event.globalPosition().y()) - self._drag_offset[1]
            self.move(dx, dy)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    def closeEvent(self, event):
        if self._is_closing:
            event.accept()
            return
        self._is_closing = True
        log.info("NOVA shutting down...")
        self.listener.stop()
        event.accept()