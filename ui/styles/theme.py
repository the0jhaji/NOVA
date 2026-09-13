# NOVA Fallback Theme — QSS
# Loaded if theme.json is missing or invalid.

QSS = """
/* ===== Global ===== */
* {
    font-family: "Segoe UI", "Segoe UI Semibold", sans-serif;
}

QMainWindow, QWidget {
    background-color: #0a0d1a;
    color: #d0e0f0;
}

/* ===== Connection dot ===== */
#connection_dot {
    border-radius: 5px;
    min-width: 10px;
    min-height: 10px;
    max-width: 10px;
    max-height: 10px;
    background-color: #7a7a7a;
}

#connection_dot[connected="true"] {
    background-color: #00ff88;
}

/* ===== Buttons ===== */
QPushButton#settings_button {
    background-color: transparent;
    color: #8899aa;
    border: none;
    font-size: 21px;
    padding: 4px;
    border-radius: 4px;
}
QPushButton#settings_button:hover {
    color: #00b4d8;
    background-color: rgba(0, 180, 216, 0.08);
}

QPushButton#mic_button {
    background-color: rgba(0, 180, 216, 0.12);
    border: 1px solid rgba(0, 180, 216, 0.35);
    color: #00b4d8;
    border-radius: 18px;
    padding: 8px 22px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#mic_button:hover {
    background-color: rgba(0, 180, 216, 0.22);
}
QPushButton#mic_button[active="true"] {
    background-color: rgba(0, 255, 136, 0.15);
    border-color: rgba(0, 255, 136, 0.5);
    color: #00ff88;
}

/* ===== Custom titlebar buttons ===== */
QPushButton#title_min, QPushButton#title_close {
    background: transparent;
    border: none;
    color: #8899aa;
    font-size: 14px;
    border-radius: 4px;
    padding: 3px 8px;
}
QPushButton#title_min:hover { background: rgba(255,255,255,0.08); color: #d0e0f0; }
QPushButton#title_close:hover { background: rgba(255,82,82,0.25); color: #ff5252; }

/* ===== Labels ===== */
QLabel#state_label {
    color: #4dd0ff;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 2px;
}

QLabel#idle_hint {
    color: #5a6b7a;
    font-size: 12px;
}

/* ===== Chat / history ===== */
QTextBrowser#history_browser {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 10px;
    color: #c8d8e8;
    padding: 10px;
    font-size: 13px;
}

/* ===== System panel ===== */
QLabel#system_title, QLabel#conversation_title {
    color: #7d8b9d;
    font-size: 11px;
    font-weight: 600;
}
QLabel#sys_value {
    color: #4dd0ff;
    font-size: 12px;
}
QLabel#sys_key {
    color: #7d8b9d;
    font-size: 12px;
}
QFrame#sys_separator {
    color: transparent;
    background-color: rgba(255, 255, 255, 0.07);
    max-height: 1px;
}
"""