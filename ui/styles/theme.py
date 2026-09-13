# NOVA theme — QSS built from the shared palette (single source of truth).

from ui.theming import PALETTE

P = PALETTE

QSS = f"""
/* ===================== Global ===================== */
* {{
    font-family: "Segoe UI", "Segoe UI Semibold", sans-serif;
}}
QWidget {{
    color: {P["text_primary"]};
    background: transparent;
}}
QToolTip {{
    background-color: rgba(10, 16, 32, 0.96);
    color: {P["text_secondary"]};
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}}

/* ===================== Glass panel ===================== */
QFrame#glass_panel {{
    background-color: rgba(12, 18, 36, 0.72);
    border: 1px solid rgba(122, 200, 255, 0.10);
    border-radius: 18px;
}}
QFrame#glass_panel[accent="true"] {{
    border: 1px solid rgba(0, 233, 203, 0.22);
}}

QLabel#section_title {{
    color: {P["text_secondary"]};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
}}

/* ===================== Brand ===================== */
QLabel#wordmark {{
    color: {P["text_primary"]};
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 5px;
}}
QLabel#tagline {{
    color: {P["text_muted"]};
    font-size: 10px;
    letter-spacing: 2px;
}}

/* ===================== Status rows ===================== */
QLabel#sys_key {{
    color: {P["text_muted"]};
    font-size: 11px;
    letter-spacing: 0.5px;
}}
QLabel#sys_value {{
    color: {P["text_secondary"]};
    font-size: 12px;
}}

/* ===================== Transcript ===================== */
QTextBrowser#history_browser {{
    background-color: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    color: {P["text_secondary"]};
    padding: 10px 12px;
    font-size: 12px;
    selection-background-color: rgba(0, 233, 203, 0.25);
}}
QTextBrowser#history_browser QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 2px 4px 2px;
}}
QTextBrowser#history_browser QScrollBar::handle:vertical {{
    background: rgba(0, 233, 203, 0.35);
    border-radius: 4px;
    min-height: 24px;
}}
QTextBrowser#history_browser QScrollBar::add-line:vertical,
QTextBrowser#history_browser QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QTextBrowser#history_browser QScrollBar::add-page:vertical,
QTextBrowser#history_browser QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* ===================== Labels ===================== */
QLabel#state_label {{
    color: {P["accent"]};
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 2px;
}}
QLabel#main_status {{
    color: {P["text_secondary"]};
    font-size: 12px;
}}
QLabel#task_meta {{
    color: {P["text_muted"]};
    font-size: 10.5px;
}}

/* ===================== Privacy badges ===================== */
QLabel#privacy_badge {{
    color: {P["accent"]};
    background-color: rgba(0, 233, 203, 0.08);
    border: 1px solid rgba(0, 233, 203, 0.25);
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#privacy_badge_warn {{
    color: #FBBF24;
    background-color: rgba(251, 191, 36, 0.08);
    border: 1px solid rgba(251, 191, 36, 0.30);
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
}}

/* ===================== Buttons ===================== */
QPushButton#mic_button {{
    background-color: rgba(0, 233, 203, 0.10);
    border: 1px solid rgba(0, 233, 203, 0.30);
    color: {P["accent"]};
    border-radius: 20px;
    padding: 10px 26px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QPushButton#mic_button:hover {{
    background-color: rgba(0, 233, 203, 0.18);
}}
QPushButton#mic_button[active="true"] {{
    background-color: rgba(52, 211, 153, 0.16);
    border-color: rgba(52, 211, 153, 0.55);
    color: #34d399;
}}

QLineEdit#cmd_input {{
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 16px;
    padding: 9px 16px;
    color: {P["text_primary"]};
    font-size: 13px;
}}
QLineEdit#cmd_input:focus {{
    border-color: rgba(0, 233, 203, 0.45);
    background-color: rgba(255, 255, 255, 0.07);
}}

QPushButton#send_button {{
    background-color: rgba(0, 233, 203, 0.12);
    border: 1px solid rgba(0, 233, 203, 0.32);
    color: {P["accent"]};
    border-radius: 16px;
    padding: 9px 16px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#send_button:hover {{
    background-color: rgba(0, 233, 203, 0.22);
}}

QPushButton#settings_button {{
    background: transparent;
    color: {P["text_muted"]};
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 14px;
}}
QPushButton#settings_button:hover {{
    color: {P["accent"]};
    border-color: rgba(0, 233, 203, 0.35);
    background-color: rgba(0, 233, 203, 0.08);
}}

QPushButton#title_min, QPushButton#title_close {{
    background: transparent;
    border: none;
    color: {P["text_muted"]};
    font-size: 14px;
    border-radius: 4px;
    padding: 3px 9px;
}}
QPushButton#title_min:hover {{ background: rgba(255,255,255,0.08); color: {P["text_primary"]}; }}
QPushButton#title_close:hover {{ background: rgba(248,113,113,0.22); color: #f87171; }}
"""

# A11y helper: high-contrast override for the state label if needed later.
ACCENT_HEX = "rgba(0,233,203,1)"