"""
NOVA Voice Assistant - Privacy Dialog
Settings → Privacy. Local-first, private by default. Every change persists
to .env and is guarded by explicit confirmation.

Cloud AI is OFF by default. Turning it ON shows the mandatory warning and
requires the user to click a separate "I understand" button before the
approval takes effect. Nothing leaves the machine just from opening this
dialog.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout,
)

from config import config
from privacy.state import (
    privacy_state, NETWORK_LOCAL_ONLY, NETWORK_BLOCKED,
)
from privacy.network_manager import network
from privacy.retention import clear_nova_data
from ui.glass import GlassPanel, SectionTitle
from ui.theming import PALETTE

_ACCENT = "#00E9CB"
_DANGER = "#f87171"
_WARNING = "#FBBF24"
_MUTED = PALETTE["text_muted"]
_SUB = PALETTE["text_secondary"]

# Mandatory message shown before enabling cloud AI (keep verbatim).
CLOUD_WARNING = ("Cloud AI is enabled. Some information may be sent to an "
                 "external AI provider. Review Privacy Settings before "
                 "continuing.")


class PrivacyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NOVA · Privacy & Security")
        self.setModal(True)
        self.setFixedSize(520, 700)

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

        lay.addWidget(self._title("PRIVACY & SECURITY"))
        lay.addWidget(self._label(
            "Local-first by design. No cloud, no telemetry, no uploads "
            "unless YOU say so.", _MUTED, 11))
        lay.addSpacing(8)

        # ---------------------------------------------------------- cloud AI
        lay.addWidget(SectionTitle("CLOUD AI"))
        self.cloud_chk = QCheckBox("Enable Cloud AI (OFF by default)")
        self.cloud_chk.setChecked(privacy_state.is_cloud_active()
                                  or config.ai.cloud_enabled)
        self.cloud_chk.toggled.connect(self._on_cloud_toggle)
        lay.addWidget(self._styled_check(self.cloud_chk))

        self.cloud_warn = QLabel("!" + CLOUD_WARNING)
        self.cloud_warn.setWordWrap(True)
        self.cloud_warn.setVisible(False)
        self.cloud_warn.setStyleSheet(f"color: {_WARNING}; font-size: 11px;")
        lay.addWidget(self.cloud_warn)

        self.approve_btn = QPushButton("I UNDERSTAND — ENABLE CLOUD AI")
        self.approve_btn.setObjectName("privacy_approve")
        self.approve_btn.setVisible(False)
        self.approve_btn.setStyleSheet(self._danger_btn_qss())
        self.approve_btn.clicked.connect(self._confirm_cloud)
        lay.addWidget(self.approve_btn)

        if privacy_state.is_cloud_active():
            self.cloud_warn.setVisible(True)
            self.cloud_warn.setText("● Cloud AI is currently ENABLED and "
                                    "approved for this session.")
            self.cloud_warn.setStyleSheet(f"color: {_WARNING}; font-size: 11px;")
        lay.addSpacing(6)

        # ---------------------------------------------------------- toggles
        lay.addWidget(SectionTitle("PRIVACY CONTROLS"))
        self.screen_chk = QCheckBox("Screen awareness (may capture your "
                                    "screen on request only)")
        self.screen_chk.setChecked(privacy_state.screen_awareness)
        self.screen_chk.toggled.connect(self._on_screen)
        lay.addWidget(self._styled_check(self.screen_chk))

        self.telemetry_chk = QCheckBox("Diagnostics (optional, always "
                                       "aggregate, never personal)")
        self.telemetry_chk.setChecked(privacy_state.telemetry_enabled)
        self.telemetry_chk.toggled.connect(self._on_telemetry)
        lay.addWidget(self._styled_check(self.telemetry_chk))

        lay.addLayout(self._row(_label_text("CONVERSATION RETENTION")))
        self.retention_box = QComboBox()
        self.retention_box.addItems(["session", "disk", "none"])
        self.retention_box.setCurrentText(privacy_state.conversation_retention)
        self.retention_box.currentTextChanged.connect(self._on_retention)
        lay.addWidget(self._combo(self.retention_box))
        lay.addWidget(self._label(
            "session = in memory only · disk = kept locally · "
            "none = not remembered. Voice audio is never stored.",
            _SUB, 10))
        lay.addSpacing(6)

        # -------------------------------------------------------- clear data
        lay.addWidget(SectionTitle("CLEAR NOVA DATA"))
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        clear_btn = QPushButton("✕  CLEAR DATA")
        clear_btn.setStyleSheet(self._danger_btn_qss())
        clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(clear_btn)
        lay.addLayout(btn_row)
        self.clear_status = QLabel("")
        self.clear_status.setStyleSheet(f"color: {_ACCENT}; font-size: 11px;")
        lay.addWidget(self.clear_status)
        lay.addSpacing(6)

        # -------------------------------------------------------- overview
        lay.addWidget(SectionTitle("CURRENT POLICY"))
        self.policy_rows = {}
        for key in ("NETWORK MODE", "CLOUD AI", "TELEMETRY",
                    "SCREEN AWARENESS", "CONVERSATION"):
            row = QHBoxLayout()
            row.addWidget(_label_text(key))
            row.addStretch()
            self.policy_rows[key] = QLabel("—")
            self.policy_rows[key].setStyleSheet(
                f"color: {_ACCENT}; font-size: 11px;")
            row.addWidget(self.policy_rows[key])
            lay.addLayout(row)
        self._refresh_policy()

        lay.addSpacing(6)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.06);")
        lay.addWidget(sep)
        lay.addSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("CLOSE")
        ok_btn.setStyleSheet(self._btn_qss())
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        root.addWidget(panel)

    # ------------------------------------------------------------- handlers
    def _on_cloud_toggle(self, on: bool):
        if on and not privacy_state.is_cloud_active():
            self.cloud_warn.setVisible(True)
            self.cloud_warn.setText("!" + CLOUD_WARNING)
            self.cloud_warn.setStyleSheet(f"color: {_WARNING}; font-size: 11px;")
            self.approve_btn.setVisible(True)
        elif on:
            self.cloud_warn.setVisible(True)
            self.cloud_warn.setText("● Cloud AI is currently ENABLED and "
                                    "approved for this session.")
            self.approve_btn.setVisible(False)
        else:
            self.cloud_warn.setVisible(False)
            self.approve_btn.setVisible(False)
            privacy_state.disable_cloud()
            network.revoke_scopes()
            config.write_env("CLOUD_AI_ENABLED", "false")
            self._refresh_policy()

    def _confirm_cloud(self):
        privacy_state.enable_cloud(True)
        network.approve_scope("ai")
        config.write_env("CLOUD_AI_ENABLED", "true")
        self.approve_btn.setVisible(False)
        self.cloud_warn.setText("● Cloud AI is now enabled and approved.")
        self.cloud_warn.setStyleSheet(f"color: {_ACCENT}; font-size: 11px;")
        self._refresh_policy()
        self._flash("Ready. NetworkManager approves this scope "
                    "until you disable it or close NOVA.")

    def _on_screen(self, on: bool):
        privacy_state.set_screen_awareness(on)
        config.write_env("PRIVACY_SCREEN_AWARENESS", "true" if on else "false")
        self._refresh_policy()

    def _on_telemetry(self, on: bool):
        privacy_state.set_telemetry(on)
        config.write_env("PRIVACY_TELEMETRY_ENABLED", "true" if on else "false")
        self._refresh_policy()

    def _on_retention(self, mode: str):
        privacy_state.set_conversation_retention(mode)
        config.write_env("PRIVACY_CONVERSATION_RETENTION", mode)
        self._refresh_policy()

    def _on_clear(self):
        removed = clear_nova_data()
        self.clear_status.setText(
            f"Cleared: {', '.join(k for k, v in removed.items() if v)}.")
        self._refresh_policy()

    def _refresh_policy(self):
        state = privacy_state
        mode = {NETWORK_LOCAL_ONLY: "LOCAL-ONLY",
                NETWORK_BLOCKED: "BLOCKED"}.get(state.network_mode,
                                                state.network_mode.upper())
        self.policy_rows["NETWORK MODE"].setText(mode)
        self.policy_rows["CLOUD AI"].setText(
            "ON (approved)" if state.is_cloud_active() else "OFF")
        self.policy_rows["TELEMETRY"].setText(
            "ON" if state.telemetry_enabled else "OFF")
        self.policy_rows["SCREEN AWARENESS"].setText(
            "ON" if state.screen_awareness else "OFF")
        self.policy_rows["CONVERSATION"].setText(
            state.conversation_retention.upper())

    def _flash(self, text: str):
        self.cloud_warn.setVisible(True)
        self.cloud_warn.setText("● " + text)
        self.cloud_warn.setStyleSheet(f"color: {_SUB}; font-size: 11px;")

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
                color: {_ACCENT}; border-radius: 14px;
                padding: 8px 22px; font-weight: 600; letter-spacing: 1px;
            }}
            QPushButton:hover {{ background-color: rgba(0, 233, 203, 0.22); }}
        """

    def _danger_btn_qss(self) -> str:
        return f"""
            QPushButton {{
                background-color: rgba(248, 113, 113, 0.10);
                border: 1px solid rgba(248, 113, 113, 0.35);
                color: {_DANGER}; border-radius: 12px;
                padding: 8px 18px; font-weight: 600; letter-spacing: 1px;
            }}
            QPushButton:hover {{ background-color: rgba(248, 113, 113, 0.2); }}
        """


def _label_text(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {_MUTED}; font-size: 11px; "
                      f"letter-spacing: 1px;")
    return lbl