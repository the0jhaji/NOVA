"""
NOVA - Memory Manager Dialog
View, delete or clear what NOVA has learned. Everything is stored locally
(SQLite) and secrets are refused at the store boundary. "Clear all" wipes
every memory entry immediately - no server, no undo.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QFrame,
)

from config import config
from memory import memory_store
from utils.logger import log

_ACCENT = "#00E9CB"
_WARNING = "#FBBF24"
_DANGER = "#f87171"
_MUTED = "#9FB4CE"
_SUB = "#6B87A6"


class MemoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NOVA - Memory")
        self.setModal(True)
        self.setMinimumSize(560, 460)
        self.setStyleSheet(f"""
            QDialog {{ background-color: #0B1220; }}
            QLabel {{ color: #EAF4FF; font-size: 13px; }}
            QLabel#sub, QLabel#muted {{ color: {_MUTED}; font-size: 11.5px; }}
            QLabel#warn {{ color: {_WARNING}; font-size: 11px; }}
            QListWidget {{
                background-color: #0E1626;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                color: #C6D8EE; font-size: 12px; padding: 6px;
            }}
            QListWidget::item {{ padding: 5px 6px; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)

        header = QLabel("MEMORY")
        header.setStyleSheet(f"color:{_ACCENT}; font-size:15px; "
                             "font-weight:700; letter-spacing:2px;")
        root.addWidget(header)

        scope = config.memory.scope if config.memory.enabled else "off"
        n = memory_store.count() if config.memory.enabled else 0
        sub = QLabel(
            f"Local SQLite storage \u00b7 scope: {scope.upper()} \u00b7 "
            f"{n} entr{'y' if n == 1 else 'ies'}. "
            "Passwords, tokens and secrets are never stored.")
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        root.addWidget(sub)

        self.list = QListWidget()
        root.addWidget(self.list, 1)

        self.status = QLabel("")
        self.status.setObjectName("warn")
        root.addWidget(self.status)

        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.06);")
        root.addWidget(sep)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        del_btn = QPushButton("Delete selected")
        del_btn.setStyleSheet(self._btn_qss())
        del_btn.clicked.connect(self._delete_selected)
        buttons.addWidget(del_btn)
        clear_btn = QPushButton("Clear all memory")
        clear_btn.setStyleSheet(self._danger_btn_qss())
        clear_btn.clicked.connect(self._clear_all)
        buttons.addWidget(clear_btn)
        buttons.addStretch()
        ok_btn = QPushButton("Done")
        ok_btn.setStyleSheet(self._btn_qss())
        ok_btn.clicked.connect(self.accept)
        buttons.addWidget(ok_btn)
        root.addLayout(buttons)

        if config.memory.enabled:
            self._refresh()
        else:
            self.status.setText("Memory is currently OFF (see Settings).")

    # ------------------------------------------------------------- helpers
    def _btn_qss(self) -> str:
        return f"""
            QPushButton {{
                background: transparent; color: {_ACCENT};
                border: 1px solid rgba(0,233,203,0.35);
                border-radius: 10px; padding: 7px 14px; font-size: 12.5px;
            }}
            QPushButton:hover {{ background: rgba(0,233,203,0.10); }}
        """

    def _danger_btn_qss(self) -> str:
        return f"""
            QPushButton {{
                background: transparent; color: {_DANGER};
                border: 1px solid rgba(248,113,113,0.45);
                border-radius: 10px; padding: 7px 14px; font-size: 12.5px;
            }}
            QPushButton:hover {{ background: rgba(248,113,113,0.12); }}
        """

    def _refresh(self):
        self.list.clear()
        for e in memory_store.all():
            self.list.addItem(f"[{e['kind']}] {e['key']} = {e['value']}")
        n = self.list.count()
        self.status.setText(f"{n} entr{'y' if n == 1 else 'ies'} shown locally.")

    def _delete_selected(self):
        row = self.list.currentRow()
        if row < 0:
            self.status.setText("Select an entry to delete.")
            return
        entries = memory_store.all()
        if row < len(entries):
            memory_store.forget(entries[row]["key"])
            self._refresh()
            log.info("Memory entry deleted from dialog")

    def _clear_all(self):
        n = memory_store.clear()
        self._refresh()
        log.info("Memory cleared from dialog (%d entries)", n)