"""
NOVA Voice Assistant - Main Window
NOVA's command center: dark atmospheric UI with a central animated core,
numeric system readouts, live transcript, and full voice interaction.

Threading model (unchanged from v1 — voice architecture is untouched):
- Voice listener: background thread (captures + transcribes audio)
- Command processing: background thread (brain + controlled automation)
- TTS: background thread (synthesis + playback)
- UI: main thread only, updated through VoiceBridge signals.

The brain runs the automation pipeline itself (intent -> plan -> tool ->
verification -> response). This window still orchestrates the EXECUTING
animation, latency reporting, and honest success/failure flashes.

Visual additions in this version:
- Shared NovaStateAnimator drives orb/rings/waveform/status in sync.
- Task progress + success/failure feedback chips.
- Inline text-input fallback (no modal dialog).
"""

import threading
import time
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QRectF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextBrowser, QLineEdit, QGraphicsDropShadowEffect,
)

from config import config
from utils.logger import log
from ui.theming import PALETTE, STATE_DEFS
from ui.state_engine import NovaStateAnimator
from ui.ambient import AmbientBackground
from ui.ring_field import EnergyRings
from ui.nova_orb import NovaOrb
from ui.waveform import WaveformWidget
from ui.glass import GlassPanel, SectionTitle, FlashChip
from ui.styles.theme import QSS as THEME_QSS
from ui.settings_dialog import SettingsDialog
from voice.listener import Listener
from voice.text_to_speech import create_tts_provider
from brain.agent import NovaAgent

STATE_LABELS = {
    "IDLE": "READY",
    "LISTENING": "LISTENING",
    "PROCESSING": "THINKING",
    "SPEAKING": "SPEAKING",
    "EXECUTING": "EXECUTING",
    "ERROR": "ERROR",
}
STATE_CAPTIONS = {
    "IDLE": "Ready for your command",
    "LISTENING": "Listening — speak now",
    "PROCESSING": "Processing your request",
    "SPEAKING": "Speaking response",
    "EXECUTING": "Executing task",
    "ERROR": "Something went wrong",
}


class VoiceBridge(QObject):
    """Cross-thread signal bridge. Workers never touch UI widgets directly."""

    state_changed = pyqtSignal(str)
    text_captured = pyqtSignal(str)          # user speech recognized
    response_ready = pyqtSignal(str)         # NOVA reply text
    action_triggered = pyqtSignal(str)       # action type + detail
    task_progress = pyqtSignal(float)        # 0..1 execution progress
    error_occurred = pyqtSignal(str)
    audio_level = pyqtSignal(float)
    latency_updated = pyqtSignal(float)
    shutdown_requested = pyqtSignal()


class _Root(QWidget):
    """Central widget that keeps the ambient background filling the window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ambient = AmbientBackground(self)

    def resizeEvent(self, event):
        self.ambient.setGeometry(self.rect())
        super().resizeEvent(event)


class _CoreDisplay(QWidget):
    """Stacked core: energy rings behind + orb centred on top."""

    def __init__(self, animator, parent=None):
        super().__init__(parent)
        self.rings = EnergyRings(animator, self)
        self.orb = NovaOrb(animator, self, size=232)
        self._animator = animator

    def resizeEvent(self, event):
        self.rings.setGeometry(self.rect())
        ox = max((self.width() - self.orb.width()) // 2, 0)
        oy = max((self.height() - self.orb.height()) // 2, 0)
        self.orb.move(ox, oy)
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NOVA")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_offset: Optional[tuple[int, int]] = None
        self._is_closing = False
        self._latest_response: str = ""

        # Core components (identical voice architecture)
        self.brain = NovaAgent()
        self.tts = create_tts_provider()
        self.bridge = VoiceBridge()
        self.listener = Listener()

        # Shared visual clock
        self.animator = NovaStateAnimator(self)

        self._build_ui()
        self._wire_signals()
        self._init_listener()

        QTimer.singleShot(1500, self._startup_message)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self._root = _Root()
        self.setCentralWidget(self._root)

        outer = QVBoxLayout(self._root)
        outer.setContentsMargins(22, 18, 22, 22)
        outer.setSpacing(0)

        # ---- Title bar ----
        tb = QHBoxLayout()
        brand = QHBoxLayout()
        brand.setSpacing(12)

        word = QLabel("N O V A")
        word.setObjectName("wordmark")
        brand.addWidget(word)

        dot = QLabel("●")
        dot.setStyleSheet("color: #00E9CB; font-size: 9px;")
        brand.addWidget(dot)

        tag = QLabel("AURORA MIND")
        tag.setObjectName("tagline")
        brand.addWidget(tag)

        brand.addStretch()
        tb.addLayout(brand)

        self.settings_btn = QPushButton("⚙  SETTINGS")
        self.settings_btn.setObjectName("settings_button")
        self.settings_btn.clicked.connect(self._open_settings)
        tb.addWidget(self.settings_btn)

        min_btn = QPushButton("—")
        min_btn.setObjectName("title_min")
        min_btn.clicked.connect(self.showMinimized)
        tb.addWidget(min_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("title_close")
        close_btn.clicked.connect(self.close)
        tb.addWidget(close_btn)

        outer.addLayout(tb)
        outer.addSpacing(14)

        # ---- Main row: transcript | core | system ----
        main = QHBoxLayout()
        main.setSpacing(18)
        main.addWidget(self._build_transcript_panel(), 1)
        main.addWidget(self._build_core_column(), 2)
        main.addWidget(self._build_system_panel(), 1)
        outer.addLayout(main, 1)
        outer.addSpacing(16)

        # ---- Bottom dock: mic | text input | (settings above) ----
        outer.addLayout(self._build_dock())

        self.setFixedSize(1280, 820)

    def _build_transcript_panel(self) -> QWidget:
        panel = GlassPanel(object_name="glass_panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        lay.addWidget(SectionTitle("TRANSCRIPT"))

        self.history = QTextBrowser()
        self.history.setObjectName("history_browser")
        self.history.document().setDefaultStyleSheet("")
        lay.addWidget(self.history, 1)

        sepf = QFrame()
        sepf.setFixedHeight(1)
        sepf.setStyleSheet("background-color: rgba(255,255,255,0.06);")
        lay.addWidget(sepf)

        task_title = QLabel("CURRENT TASK")
        task_title.setObjectName("section_title")
        lay.addWidget(task_title)

        self.command_label = QLabel("Awaiting command…")
        self.command_label.setWordWrap(True)
        self.command_label.setStyleSheet(
            f"color: {PALETTE['accent']}; font-size: 12px;"
        )
        lay.addWidget(self.command_label)

        self.meta_label = QLabel("—")
        self.meta_label.setObjectName("task_meta")
        self.meta_label.setWordWrap(True)
        lay.addWidget(self.meta_label)

        return panel

    def _build_core_column(self) -> QWidget:
        wrapper = QWidget()
        col = QVBoxLayout(wrapper)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)

        core = _CoreDisplay(self.animator)
        core.setFixedSize(520, 340)
        col.addWidget(core, 1, Qt.AlignmentFlag.AlignHCenter)

        self.waveform = WaveformWidget(self.animator, width=470, height=50)
        col.addWidget(self.waveform, 0, Qt.AlignmentFlag.AlignHCenter)

        self.state_label = QLabel("● READY")
        self.state_label.setObjectName("state_label")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.state_label)

        self.state_caption = QLabel(STATE_CAPTIONS["IDLE"])
        self.state_caption.setObjectName("main_status")
        self.state_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.state_caption)

        self.flash_chip = FlashChip()
        col.addWidget(self.flash_chip, 0, Qt.AlignmentFlag.AlignCenter)

        return wrapper

    def _build_system_panel(self) -> QWidget:
        panel = GlassPanel(object_name="glass_panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(8)

        lay.addWidget(SectionTitle("SYSTEM"))

        # AI status
        ai_row = QHBoxLayout()
        ai_row.setSpacing(8)
        self.ai_dot = QLabel("●")
        self.ai_dot.setStyleSheet("color: #00E9CB; font-size: 10px;")
        ai_row.addWidget(self.ai_dot)
        self.ai_status = QLabel("AI CORE · ONLINE")
        self.ai_status.setObjectName("sys_value")
        self.ai_status.setStyleSheet(
            f"color: #00E9CB; font-size: 12px; font-weight: 600; letter-spacing: 1px;"
        )
        ai_row.addWidget(self.ai_status)
        ai_row.addStretch()
        lay.addLayout(ai_row)

        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.06);")
        lay.addWidget(sep)

        # Static rows
        self.sys_mic = self._add_row(lay, "MIC", "READY")
        self.sys_lang = self._add_row(lay, "LANGUAGE", config.stt.language.upper())
        self.sys_stt = self._add_row(lay, "SPEECH→TEXT", config.stt.provider.upper())
        self.sys_tts = self._add_row(lay, "TEXT→SPEECH", config.tts.provider.upper())
        self.sys_wake = self._add_row(lay, "WAKE WORD",
                                     f"{config.wake_word.word.upper()} · "
                                     f"{'ON' if config.wake_word.enabled else 'OFF'}")
        self.sys_latency = self._add_row(lay, "LATENCY", "—")

        lay.addSpacing(8)
        hint = QLabel(
            "Speak or type in English, हिन्दी or Hinglish.\n"
            "Examples:  “Chrome kholo” · “क्रोम खोलो”\n"
            "           “YouTube open karo” · “Tell me the time”"
        )
        hint.setWordWrap(True)
        hint.setObjectName("task_meta")
        lay.addWidget(hint)

        lay.addStretch()
        return panel

    def _add_row(self, lay, key: str, value: str) -> QLabel:
        row = QHBoxLayout()
        row.setSpacing(8)
        k = QLabel(key)
        k.setObjectName("sys_key")
        v = QLabel(value)
        v.setObjectName("sys_value")
        row.addWidget(k)
        row.addStretch()
        row.addWidget(v)
        lay.addLayout(row)
        return v

    def _build_dock(self) -> QHBoxLayout:
        dock = QHBoxLayout()
        dock.setSpacing(12)

        self.mic_button = QPushButton("●  MICROPHONE")
        self.mic_button.setObjectName("mic_button")
        self.mic_button.setToolTip("Toggle listening (click or focus + Enter)")
        self.mic_button.clicked.connect(self._toggle_mic)
        self.mic_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        dock.addWidget(self.mic_button)

        self.cmd_input = QLineEdit()
        self.cmd_input.setObjectName("cmd_input")
        self.cmd_input.setPlaceholderText("Type a command…  ( Enter to send )")
        self.cmd_input.returnPressed.connect(self._send_text)
        dock.addWidget(self.cmd_input, 1)

        send = QPushButton("SEND")
        send.setObjectName("send_button")
        send.clicked.connect(self._send_text)
        dock.addWidget(send)

        return dock

    # ------------------------------------------------------------------ wires
    def _wire_signals(self):
        self.bridge.state_changed.connect(self._set_state)
        self.bridge.text_captured.connect(self._on_text_captured)
        self.bridge.response_ready.connect(self._on_response)
        self.bridge.action_triggered.connect(self._on_action)
        self.bridge.task_progress.connect(self._on_task_progress)
        self.bridge.error_occurred.connect(self._on_error)
        self.bridge.audio_level.connect(self.animator.set_audio_level)
        self.bridge.latency_updated.connect(
            lambda ms: self.sys_latency.setText(f"{ms:.0f} ms")
        )
        self.bridge.shutdown_requested.connect(self.close)

    def _init_listener(self):
        self.listener.on_state_change = lambda s: self.bridge.state_changed.emit(s)
        self.listener.on_text_captured = lambda t: self.bridge.text_captured.emit(t)
        self.listener.on_error = lambda e: self.bridge.error_occurred.emit(e)
        self.listener.on_audio_level = lambda l: self.bridge.audio_level.emit(l)

        ok = self.listener.initialize()
        if ok:
            threading.Thread(target=self.listener.calibrate, daemon=True).start()
            log.info("Microphone ready")
        else:
            self._set_connection(False)
            self._append_history("SYSTEM", "No microphone detected — type or use Send.")

    # ------------------------------------------------------------------ states
    def _startup_message(self):
        self._append_history("NOVA", "SYSTEMS ONLINE. I'm ready — speak or type a command.")

    def _set_state(self, state: str):
        self.animator.set_state(state)
        self.state_label.setText(f"● {STATE_LABELS.get(state, state)}")
        self.state_caption.setText(STATE_CAPTIONS.get(state, ""))

        primary = STATE_DEFS[state]["primary"]
        hexc = QColor(*primary).name()
        self.state_label.setStyleSheet(
            f"QLabel#state_label {{ color: {hexc}; font-size: 13px; "
            f"font-weight: 700; letter-spacing: 2px; }}"
        )
        self.flash_chip.hide()

        mic_text = {
            "LISTENING": "◉ LISTENING",
            "PROCESSING": "… THINKING",
            "SPEAKING": "◉ SPEAKING",
            "EXECUTING": "✓ EXECUTING",
            "ERROR": "⚠ ERROR",
            "IDLE": "READY",
        }.get(state, "READY")
        self.sys_mic.setText(mic_text)

        # Wake-word ornament clears when NOVA returns to a neutral state
        if state in ("IDLE", "LISTENING"):
            self.animator.clear_orb_text()

    def _on_task_progress(self, value: float):
        self.animator.set_progress(value)

    def _flash(self, text: str, kind: str):
        color = {
            "success": PALETTE["success"],
            "error": PALETTE["danger"],
            "notice": PALETTE["warning"],
        }.get(kind, PALETTE["accent"])
        hexc = QColor(*color).name()
        self.flash_chip.flash(text, hexc)
        QTimer.singleShot(3200, self.flash_chip.hide)

    def _on_error(self, message: str):
        log.error("Voice pipeline error: %s", message)
        self._set_state("ERROR")
        self._flash("⚠ Action did not complete", "error")
        self._append_history("NOVA", "I had trouble with that. Could you try again?")
        QTimer.singleShot(2500, lambda: self._set_state("IDLE"))

    # ------------------------------------------------------------------ commands
    def _on_text_captured(self, text: str):
        """Voice text arrives on the UI thread (wake word or command)."""
        if text.strip().lower() == config.wake_word.word.lower():
            self.command_label.setText(f"Wake: {text}")
            self._set_state("SPEAKING")
            self.animator.set_orb_text("YES?")
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
            target=self._process_worker, args=(text,), daemon=True
        ).start()

    def _send_text(self):
        text = self.cmd_input.text().strip()
        if not text:
            return
        self.cmd_input.clear()
        self._append_history("YOU", text)
        self.command_label.setText(text)
        self._set_state("PROCESSING")
        threading.Thread(
            target=self._process_worker, args=(text,), daemon=True
        ).start()

    def _process_worker(self, text: str):
        """Background: run the brain, report latency, emit results."""
        try:
            time.sleep(0.30)
            t0 = time.perf_counter()
            response, action = self.brain.process(text)
            latency = (time.perf_counter() - t0) * 1000.0
            self.bridge.state_changed.emit("PROCESSING")

            self._latest_response = response
            self.bridge.response_ready.emit(response)
            self.bridge.latency_updated.emit(latency)

            if action == "execute":
                self.bridge.action_triggered.emit(text)
            elif action == "quit":
                self.bridge.state_changed.emit("SPEAKING")
                self._speak_worker(response)
                self.bridge.shutdown_requested.emit()
            else:
                self.bridge.state_changed.emit("SPEAKING")
                self._speak_worker(response)
                self.bridge.state_changed.emit("IDLE")
        except Exception as e:
            log.error("Brain processing failed: %s", e)
            self.bridge.error_occurred.emit(str(e))

    def _on_response(self, text: str):
        self.meta_label.setText("RESPONSE")
        self.meta_label.setStyleSheet(
            "QLabel#task_meta { color: #9FB4CE; font-size: 10.5px; }"
        )
        self._append_history("NOVA", text)

    def _on_action(self, command: str):
        """Automation already ran inside the brain worker; animate + report."""
        self._set_state("EXECUTING")
        self.command_label.setText(command)
        self.meta_label.setText("EXECUTING…")
        self.meta_label.setStyleSheet(
            "QLabel#task_meta { color: #FBBF24; font-size: 10.5px; }"
        )

        ok = getattr(self.brain, "last_action_ok", False)
        self._append_history(
            "SYSTEM",
            (f"Automation complete: {command}" if ok else f"Automation failed: {command}"),
        )

        threading.Thread(
            target=self._execute_pipeline, daemon=True
        ).start()

    def _execute_pipeline(self, _app=None):
        """Background: brief pulse, then speak the verified reply + flash."""
        for i in range(1, 17):
            self.bridge.task_progress.emit(i / 16)
            time.sleep(0.035)

        self.bridge.state_changed.emit("SPEAKING")
        reply = self._latest_response or "Done."
        self._speak_worker(reply)
        self.bridge.state_changed.emit("IDLE")
        self.bridge.task_progress.emit(0.0)

        ok = getattr(self.brain, "last_action_ok", False)
        summary = getattr(self.brain, "last_action_summary", "") or (
            "Task complete" if ok else "Task failed"
        )
        self._flash(f"✓ {summary}" if ok else f"⚠ {summary}",
                    "success" if ok else "error")

    def _speak_worker(self, text: str):
        try:
            self.tts.speak(text)
        except Exception as e:
            log.error("TTS failed: %s", e)
            self.bridge.error_occurred.emit(str(e))

    # ------------------------------------------------------------------ controls
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

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    # ------------------------------------------------------------------ helpers
    def _set_connection(self, online: bool):
        if online:
            self.ai_dot.setStyleSheet("color: #00E9CB; font-size: 10px;")
            self.ai_status.setText("AI CORE · ONLINE")
        else:
            self.ai_dot.setStyleSheet("color: #f87171; font-size: 10px;")
            self.ai_status.setText("AI CORE · OFFLINE")

    def _append_history(self, speaker: str, text: str):
        if speaker == "YOU":
            entry = (
                f'<span style="color:#7DD7FF;">▸ YOU</span> &nbsp;'
                f'<b style="color:#EAF4FF;">{text}</b>'
            )
        elif speaker == "SYSTEM":
            entry = (
                f'<span style="color:#FBBF24;">⚡ SYSTEM</span> &nbsp;'
                f'<span style="color:#9FB4CE;">{text}</span>'
            )
        else:
            entry = (
                f'<span style="color:#FF7188;">◉ NOVA</span> &nbsp;'
                f'<b style="color:#A8F0FF;">{text}</b>'
            )
        self.history.append(entry)
        sb = self.history.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ------------------------------------------------------------------ window
    def resizeEvent(self, event):
        self._root.ambient.setGeometry(self._root.rect())
        super().resizeEvent(event)

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