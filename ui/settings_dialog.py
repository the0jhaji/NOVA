"""
NOVA Voice Assistant - Settings Dialog
Editable voice controls + configuration overview.

Voice settings apply live through the VoiceController (volume, speed,
language mode, auto-detect, provider) and are persisted to .env so they
survive a restart.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSlider, QVBoxLayout,
)

from config import config
from ui.glass import GlassPanel, SectionTitle
from ui.theming import PALETTE
from voice.controller import voice as voice_ctl

_ACCENT = "#00E9CB"
_MUTED = PALETTE["text_muted"]
_SUB = PALETTE["text_secondary"]


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NOVA · Settings")
        self.setModal(True)
        self.setFixedSize(480, 640)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(0)

        panel = GlassPanel()
        panel.setStyleSheet(f"""
            QFrame#glass_panel {{
                background-color: rgba(10, 16, 32, 0.97);
                border: 1px solid rgba(0, 233, 203, 0.25);
                border-radius: 16px;
            }}
        """)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(22, 20, 22, 16)
        lay.setSpacing(6)

        lay.addWidget(self._title("NOVA — SETTINGS"))
        lay.addWidget(self._label(
            "Voice, language and identity for NOVA's voice assistant.",
            _MUTED, 11))
        lay.addSpacing(8)

        # ------------------------------------------------------------ voice
        lay.addWidget(SectionTitle("VOICE"))
        self.voice_enabled = QCheckBox("Voice responses enabled")
        self.voice_enabled.setChecked(voice_ctl.enabled)
        self.voice_enabled.toggled.connect(self._on_enabled)
        lay.addWidget(self._styled_check(self.voice_enabled))

        lay.addWidget(self._row(_label_text("PROVIDER")))
        self.provider_box = QComboBox()
        self.provider_box.addItems(["edge-tts", "windows-sapi", "none"])
        self.provider_box.setCurrentText(voice_ctl.provider.name)
        self.provider_box.currentTextChanged.connect(self._on_provider)
        lay.addWidget(self._combo(self.provider_box))
        lay.addWidget(self._label(
            "edge-tts = natural neural Indian female voices "
            "(Neerja / Swara). Provider changes apply immediately.",
            _SUB, 10))

        self.voice_enabled.toggled.connect(self._refresh)
        lay.addSpacing(6)

        lay.addWidget(self._row(_label_text("LANGUAGE MODE")))
        self.lang_box = QComboBox()
        self.lang_box.addItems(["AUTO", "ENGLISH", "HINDI", "HINGLISH"])
        self.lang_box.setCurrentText(voice_ctl.language_mode)
        self.lang_box.currentTextChanged.connect(self._on_lang)
        lay.addWidget(self._combo(self.lang_box))

        self.auto_chk = QCheckBox("Auto-detect the user's language")
        self.auto_chk.setChecked(voice_ctl.auto_detect)
        self.auto_chk.toggled.connect(self._on_auto)
        self.auto_chk.setEnabled(voice_ctl.language_mode == "AUTO")
        lay.addWidget(self._styled_check(self.auto_chk))
        lay.addWidget(self._label(
            "NOVA answers and speaks in Hindi when you write हिन्दी, "
            "Hinglish for Romanised Hindi, English otherwise.",
            _SUB, 10))
        lay.addSpacing(6)

        self.volume_lbl = self._row(_label_text(f"VOLUME  {voice_ctl.volume}%"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(voice_ctl.volume)
        self.volume_slider.valueChanged.connect(self._on_volume)
        lay.addWidget(self._slider(self.volume_slider))

        self.speed_lbl = self._row(_label_text(f"SPEED  {voice_ctl.speed:+d}"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(-50, 50)
        self.speed_slider.setValue(voice_ctl.speed)
        self.speed_slider.valueChanged.connect(self._on_speed)
        lay.addWidget(self._slider(self.speed_slider))
        lay.addSpacing(6)

        test_row = QHBoxLayout()
        test_row.addStretch()
        test_btn = QPushButton("▶  TEST VOICE")
        test_btn.setObjectName("settings_test")
        test_btn.setStyleSheet(self._btn_qss())
        test_btn.clicked.connect(lambda: voice_ctl.test())
        test_row.addWidget(test_btn)
        self.voice_enabled.toggled.connect(
            lambda on: test_btn.setEnabled(on))
        lay.addLayout(test_row)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.06);")
        lay.addWidget(sep)

        # ------------------------------------------------------ overview
        lay.addWidget(SectionTitle("CONFIGURATION"))
        rows = [
            ("VOICE (STT)", config.stt.provider.upper()),
            ("SPEECH (TTS)", config.voice.provider.upper()),
            ("VOICE", voice_ctl.describe()),
            ("LANGUAGE", config.voice.language_mode),
            ("WAKE WORD", f"{config.wake_word.word} "
                          f"({'ON' if config.wake_word.enabled else 'OFF'})"),
            ("MODEL", f"NOVA v{config.app_version}"),
        ]
        for key, value in rows:
            lay.addLayout(self._info_row(key, value))

        lay.addSpacing(6)
        lay.addWidget(self._label(
            "All choices are saved to .env and survive a restart.",
            _SUB, 10))

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("CLOSE")
        ok_btn.setStyleSheet(self._btn_qss())
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        root.addWidget(panel)

    # ------------------------------------------------------------- handlers
    def _on_enabled(self, on: bool):
        voice_ctl.set_enabled(on)

    def _on_provider(self, name: str):
        if name:
            voice_ctl.set_provider(name)

    def _on_lang(self, mode: str):
        voice_ctl.set_language_mode(mode)
        self.auto_chk.setEnabled(mode == "AUTO")

    def _on_auto(self, on: bool):
        voice_ctl.set_auto_detect(on)

    def _on_volume(self, value: int):
        voice_ctl.set_volume(value)
        self.volume_lbl.setText(f"VOLUME  {value}%")

    def _on_speed(self, value: int):
        voice_ctl.set_speed(value)
        self.speed_lbl.setText(f"SPEED  {value:+d}")

    def _refresh(self):
        self.lang_box.setEnabled(self.voice_enabled.isChecked())

    # -------------------------------------------------------------- widgets
    def _title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: #EAF4FF; font-size: 15px; "
                          f"font-weight: 700; letter-spacing: 2px;")
        return lbl

    def _label(self, text: str, color: str, size: int) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {color}; font-size: {size}px;")
        return lbl

    def _row(self, widget: QLabel) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(widget)
        row.addStretch()
        return row

    def _label_text(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {_MUTED}; font-size: 11px; "
                          f"letter-spacing: 1px;")
        return lbl

    def _info_row(self, key: str, value: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self._label_text(key))
        row.addStretch()
        v = QLabel(str(value))
        v.setStyleSheet(f"color: {_ACCENT}; font-size: 11px;")
        row.addWidget(v)
        return row

    def _combo(self, box: QComboBox) -> QComboBox:
        box.setStyleSheet(f"""
            QComboBox {{
                background-color: rgba(0, 233, 203, 0.08);
                border: 1px solid rgba(0, 233, 203, 0.28);
                border-radius: 10px;
                color: #EAF4FF; padding: 6px 10px; font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: #0C1420; color: #EAF4FF;
                border: 1px solid rgba(0, 233, 203, 0.25);
                selection-background-color: rgba(0, 233, 203, 0.2);
            }}
        """)
        return box

    def _slider(self, s: QSlider) -> QSlider:
        s.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 5px; background: rgba(255,255,255,0.10);
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 14px; height: 14px; margin: -5px 0;
                border-radius: 7px;
                background: {_ACCENT};
            }}
        """)
        return s

    def _styled_check(self, chk: QCheckBox) -> QCheckBox:
        chk.setStyleSheet(
            f"QCheckBox {{ color: {_SUB}; font-size: 12px; }} "
            f"QCheckBox::indicator {{ width: 15px; height: 15px; }}")
        return chk

    def _btn_qss(self) -> str:
        return f"""
            QPushButton {{
                background-color: rgba(0, 233, 203, 0.12);
                border: 1px solid rgba(0, 233, 203, 0.35);
                color: {_ACCENT};
                border-radius: 14px;
                padding: 8px 22px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{ background-color: rgba(0, 233, 203, 0.22); }}
            QPushButton:disabled {{ color: #42566E;
                border-color: rgba(66, 86, 110, 0.4); }}
        """