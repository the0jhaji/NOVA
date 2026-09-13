"""
NOVA Voice Assistant - Settings Dialog
A lightweight glass "About / Configuration" window.
Changes are made by editing .env — this dialog documents the options
and shows the active configuration.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import QTimer

from config import config
from ui.glass import GlassPanel, SectionTitle
from ui.theming import PALETTE


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NOVA · Settings")
        self.setModal(True)
        self.setFixedSize(430, 500)

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

        title = QLabel("NOVA — CONFIGURATION")
        title.setStyleSheet("color: #EAF4FF; font-size: 15px; font-weight: 700; letter-spacing: 2px;")
        lay.addWidget(title)

        subtitle = QLabel(
            "Settings are managed through the .env file.\n"
            "Restart NOVA after making changes."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {PALETTE['text_muted']}; font-size: 11px;")
        lay.addWidget(subtitle)
        lay.addSpacing(10)

        rows = [
            ("VOICE (STT)", config.stt.provider.upper()),
            ("SPEECH (TTS)", config.tts.provider.upper()),
            ("TTS VOICE", config.tts.voice),
            ("LANGUAGE", config.stt.language.upper()),
            ("WAKE WORD", f"{config.wake_word.word} ({'ON' if config.wake_word.enabled else 'OFF'})"),
            ("VOICE RATE", config.tts.rate),
            ("MODEL", f"NOVA v{config.app_version}"),
        ]
        for key, value in rows:
            r = QHBoxLayout()
            r.setSpacing(10)
            k = QLabel(key)
            k.setStyleSheet(f"color: {PALETTE['text_muted']}; font-size: 11px; letter-spacing: 0.5px;")
            v = QLabel(str(value))
            v.setStyleSheet(f"color: {PALETTE['accent']}; font-size: 11px;")
            r.addWidget(k)
            r.addStretch()
            r.addWidget(v)
            lay.addLayout(r)

        lay.addSpacing(8)
        hint = QLabel("Edit .env to switch providers or enable the wake word.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {PALETTE['text_secondary']}; font-size: 11px;")
        lay.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("CLOSE")
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 233, 203, 0.12);
                border: 1px solid rgba(0, 233, 203, 0.35);
                color: #00E9CB;
                border-radius: 14px;
                padding: 8px 22px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{ background-color: rgba(0, 233, 203, 0.22); }}
        """)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        root.addWidget(panel)