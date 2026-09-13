"""
NOVA Voice Assistant - Brain / Agent
Processes user commands and generates responses.

The brain owns the full automation pipeline:
    intent  ->  action planner  ->  tool selection
           ->  tool execution  ->  verification -> response

Multilingual (English / Hindi / Hinglish / Devanagari) patterns map onto a
fixed set of controlled tools. NOVA never composes a shell command; every
action goes through the AutomationEngine, which enforces risk classification.
"""

import re
from datetime import datetime
from typing import Optional, Tuple

from utils.logger import log
from automation import AutomationEngine, ActionStep, ActionPlan, RiskLevel
from automation.safety import classify, classify_text_high_risk, classify_step, TOOL_BASE_RISK
from automation.paths import resolve_location, default_folder
from voice.language import detect_lang
from ai import create_ai_provider, AIUnavailable, AIBlocked
from privacy.redactor import redact_secrets, looks_sensitive
from privacy.retention import append_conversation
from privacy.telemetry import record as telemetry_record
from memory import memory_store
from config import config as nova_config

# Phrase used whenever the local model cannot run. NOVA never silently
# forwards a request to a cloud provider.
_LOCAL_UNAVAILABLE = ("Local AI is unavailable. I haven't sent your "
                      "request to a cloud service.")


# ---------------------------------------------------------------------------
# Hindi number words (for volume percentages etc.)
# ---------------------------------------------------------------------------

_HINDI_NUMBERS = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4,
    "paanch": 5, "panch": 5, "chhe": 6, "shat": 6, "saat": 7,
    "aath": 8, "nau": 9, "das": 10, "dus": 10, "gyarah": 11,
    "baarah": 12, "barah": 12, "terah": 13, "chaudah": 14,
    "pandrah": 15, "solah": 16, "satarah": 17, "atharah": 18,
    "unnis": 19, "bees": 20, "pachis": 25, "pachaas": 50,
    "saath": 60, "sattar": 70, "assi": 80, "navve": 90, "sau": 100,
    "pachas": 50,
}

_SITE_MAP = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://en.wikipedia.org",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "whatsapp": "https://web.whatsapp.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "amazon": "https://www.amazon.com",
    "à¤¯à¥‚à¤Ÿà¥à¤¯à¥‚à¤¬": "https://www.youtube.com",
    "à¤—à¥‚à¤—à¤²": "https://www.google.com",
    "à¤œà¥€à¤®à¥‡à¤²": "https://mail.google.com",
}

_NAAM_KEYWORDS = re.compile(
    r"\b(naam|named|name|called|called as|named as|à¤¨à¤¾à¤®)\b", re.I
)
_LOCATION_WORDS = {
    "desktop", "downloads", "download", "documents", "document",
    "pictures", "music", "videos", "home",
}

_CONFIRM_YES = re.compile(
    r"^(yes|haan|hum|han|confirm|yeah|yep|ok|okay|theek hai|kar do|karo"
    r"|à¤¹à¤¾à¤|à¤¹à¤¾à¤‚|à¤ à¥€à¤• à¤¹à¥ˆ|à¤•à¤°à¥‹|à¤¹à¥ˆà¤œà¤¾)$",
    re.I,
)
_CONFIRM_NO = re.compile(
    r"^(no|cancel|nahi|na|nope|mat karo|rook do|stop|à¤°à¤¦à¥à¤¦|à¤¨à¤¹à¥€à¤‚|à¤®à¤¤ à¤•à¤°à¥‹|à¤°à¥‹à¤•à¥‹)$",
    re.I,
)


class NovaAgent:
    """
    NOVA's brain â€” processes text commands and returns responses.

    Public API (unchanged): process(), get_history().
    New state read by the UI:
      last_action_ok      -> did the last automation actually succeed?
      last_action_summary -> short human message to flash.
    """

    def __init__(self, automation: Optional[AutomationEngine] = None):
        self.automation = automation or AutomationEngine()
        self._build_patterns()
        self.conversation_history: list[dict] = []
        self._context: dict = {}
        self._pending_plan: Optional[tuple[ActionPlan, str]] = None

        # Local-first AI provider (None when disabled or cloud not approved).
        self.ai = create_ai_provider()

        # Read by the UI to flash honest success/failure.
        self.last_action_ok: bool = False
        self.last_action_summary: str = ""

    # ------------------------------------------------------------------ util
    def _ok(self, summary: str, response: Optional[str] = None):
        self.last_action_ok = True
        self.last_action_summary = summary
        return (response or summary, "execute")

    def _fail(self, summary: str, response: Optional[str] = None):
        self.last_action_ok = False
        self.last_action_summary = summary
        return (response or f"I couldn't complete that because {summary.lower()}", "execute")

    def _extract_number(self, text: str) -> Optional[int]:
        m = re.search(r"\b(\d{1,3})\b", text or "")
        if m:
            return min(int(m.group(1)), 1000)
        low = (text or "").lower()
        for word in sorted(_HINDI_NUMBERS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(word)}\b", low):
                return _HINDI_NUMBERS[word]
        return None

    def _extract_name(self, text: str) -> Optional[str]:
        """Name after naam/named/name/à¤¨à¤¾à¤®, cleaned of trailing stopwords."""
        m = _NAAM_KEYWORDS.search(text or "")
        if not m:
            return None
        tail = text[m.end():]
        m2 = re.match(r"\s*[:\-]?\s*[\"â€œ']?([\w\u0900-\u097F\u0300-\u036F\- .]+)[\"â€']?", tail)
        if not m2:
            return None
        return self._clean_name(m2.group(1), spatial=True)

    def _clean_name(self, raw: str, spatial: bool = False) -> str:
        tokens = raw.strip().split()
        stop = {"karo", "kar", "do", "de", "banao", "banaiye", "kare",
                "create", "make", "please", "folder", "file", "à¤•à¤¾",
                "à¤•à¤°à¥‹", "à¤¦à¥‹", "à¤¬à¤¨à¤¾à¤“", }
        if spatial:
            stop |= {"on", "in", "pe", "par", "mein", "main", "mat",
                     "à¤ªà¤°", "à¤®à¥‡à¤‚", "à¤ªà¥‡", "à¤®à¥ˆà¤‚"}
        while tokens and tokens[-1].lower() in stop:
            tokens.pop()
        name = " ".join(tokens).strip()
        return name.strip('"').strip("'").rstrip(".").rstrip(",")

    def _location_path(self, text: str) -> str:
        """Resolve a spoken location in `text`, defaulting to Desktop."""
        return resolve_location(text) or default_folder("desktop")

    def _run(self, steps: list[ActionStep], text: str = "", approved: bool = False) -> str:
        """Execute a plan via the engine and build the honest response."""
        if not steps:
            return "I couldn't work out how to do that."
        plan = ActionPlan(steps=steps,
                          rationale=f"user said: {text}" if text else "")
        plan_res = self.automation.execute_plan(plan, approved=approved)

        if plan_res.blocked:
            self.last_action_ok = False
            self.last_action_summary = plan_res.blocker_message
            return self.last_action_summary

        if plan_res.all_ok:
            self.last_action_ok = True
            msgs = [s.message for s in plan_res.results() if s.message]
            self.last_action_summary = msgs[0] if msgs else "Task complete"
            return " ".join(msgs) if msgs else "Done."
        for r in plan_res.results():
            if not r.ok:
                self.last_action_ok = False
                self.last_action_summary = r.message
                return r.message
        self.last_action_ok = False
        return "I couldn't complete that."

    def _stage_confirmation(self, plan: ActionPlan, ask: str) -> Tuple[str, str]:
        """Park a plan and ask the user to confirm before it runs."""
        self._pending_plan = (plan, ask)
        self.last_action_ok = False
        self.last_action_summary = "Waiting for confirmation"
        return (ask, "speak")

    def _run_pending(self, confirmed: bool) -> Tuple[str, str]:
        if not self._pending_plan:
            return ("I don't have anything waiting for confirmation.", "speak")
        plan, ask = self._pending_plan
        self._pending_plan = None
        if not confirmed:
            self.last_action_ok = False
            self.last_action_summary = "Cancelled"
            return ("Okay, I've cancelled that.", "speak")
        return (self._run(plan.steps, approved=True), "execute")

    # ------------------------------------------------------------------ setup
    def _build_patterns(self):
        self.PATTERNS = [
            # -- refusal for high-risk phrasing (never executes silently) ---
            (re.compile(r"\b(format|wipe|partition|firewall|uac|defender|mbr|bios|registry|delete system)\b", re.I),
             "_handle_high_risk_refusal"),

            # Greetings (guarded so "hello" inside "hello.txt" is not a greeting)
            (re.compile(r"\b(hello|hi|hey|namaste|namaskar)\b(?![.\w])"
                        r"|(?<!\S)(à¤¨à¤®à¤¸à¥à¤¤à¥‡|à¤¨à¤®à¤¸à¥à¤•à¤¾à¤°|à¤¹à¥ˆà¤²à¥‹|à¤¹à¤¾à¤¯|à¤¨à¤®à¥‹)(?=\s|$)", re.I),
             "_handle_greeting"),
            (re.compile(r"(hello\s*nova|hi\s*nova|hey\s*nova)", re.I),
             "_handle_greeting"),

            # What can you do
            (re.compile(r"what can you do|tum kya kar sakti|kya kar sakti ho"
                        r"|your capabilities|capabilities"
                        r"|(à¤¤à¥à¤® à¤•à¥à¤¯à¤¾ à¤•à¤° à¤¸à¤•à¤¤à¥€ à¤¹à¥‹|à¤•à¥à¤¯à¤¾ à¤•à¤° à¤¸à¤•à¤¤à¥€ à¤¹à¥‹)", re.I),
             "_handle_capabilities"),

            # Time / Date (question forms only, so file op keywords don't collide)
            (re.compile(r"(what time|what's the time|the time|kitne baje|kya time"
                        r"|time kya hai|samay batao|vakt batao|kya samay)"
                        r"|(à¤¸à¤®à¤¯ à¤•à¥à¤¯à¤¾ à¤¹à¥à¤†|à¤•à¤¿à¤¤à¤¨à¥‡ à¤¬à¤œà¥‡|à¤•à¥à¤¯à¤¾ à¤¸à¤®à¤¯|à¤µà¤•à¥à¤¤ à¤¬à¤¤à¤¾à¤“)", re.I),
             "_handle_time"),
            (re.compile(r"(what date|what's the date|what is the date|today's date"
                        r"|aaj ki date|kya date hai|kya tarikh hai|tarikh batao)"
                        r"|(à¤†à¤œ à¤•à¥€ à¤¤à¤¾à¤°à¥€à¤–|à¤¤à¤¾à¤°à¥€à¤– à¤¬à¤¤à¤¾à¤“)", re.I),
             "_handle_date"),

            # Who are you / Thanks / Quit
            (re.compile(r"(who are you|tum\s+kaun|kaun ho|your name|tumhara naam"
                        r"|apna naam|naam kya hai|naam batao)"
                        r"|(à¤¤à¥à¤® à¤•à¥Œà¤¨ à¤¹à¥‹|à¤•à¥Œà¤¨ à¤¹à¥‹)", re.I),
             "_handle_identity"),
            (re.compile(r"\b(thanks?|thank you|shukriya|dhanyavaad)\b"
                        r"|(à¤¶à¥à¤•à¥à¤°à¤¿à¤¯à¤¾|à¤§à¤¨à¥à¤¯à¤µà¤¾à¤¦)", re.I),
             "_handle_thanks"),
            (re.compile(r"\b(quit|exit|bye|goodbye)\b|(à¤…à¤²à¤µà¤¿à¤¦à¤¾)", re.I),
             "_handle_quit"),

# --- memory: remember / preferences / recall / forget / clear ---
            (re.compile(r"(remember\s+(?:that\s+|this\s+)?|yaad rakho|yaad rakhna"
                        r"|yaad rakhenge|note karo"
                        r"|\u092f\u093e\u0926 \u0930\u0916\u0928\u093e"
                        r"|\u092f\u093e\u0926 \u0930\u0916\u094b|\u0928\u094b\u091f \u0915\u0930\u094b)"
                        r"|(mostly use|use karta hoon|use karti hoon|prefer|"
                        r"my name is|mera naam|\u092e\u0947\u0930\u093e \u0928\u093e\u092e"
                        r"|call me|i like|main .{1,20} use"
                        r" karta|\u092e\u0941\u091d\u0947 .{1,20} \u092a\u0938\u0902\u0926)", re.I),
             "_handle_remember"),
            (re.compile(r"(what do you remember|what do you know about me"
                        r"|kya yaad hai|tumhe kya yaad|kya yaad rakha"
                        r"|apni yaadein batao"
                        r"|\u0924\u0941\u092e\u094d\u0939\u0947\u0902 \u0915\u094d\u092f\u093e \u092f\u093e\u0926"
                        r"|\u0905\u092a\u0928\u0940 \u092f\u093e\u0926\u0947\u0902 \u092c\u0924\u093e\u0913)", re.I),
             "_handle_memory_recall"),
            (re.compile(r"\b(forget|yaad mat rakho|bhool jao"
                        r"|\u092e\u0924 \u0930\u0916\u094b|\u092d\u0942\u0932 \u091c\u093e\u0913)\b", re.I),
             "_handle_forget"),
            (re.compile(r"(clear your memory|memory clear karo|memory saaf karo"
                        r"|all memory"
                        r"|\u0938\u092c \u092f\u093e\u0926\u0947\u0902 \u0938\u093e\u092b)", re.I),
             "_handle_clear_memory"),

            # --- compound action: "Open VS Code and create a new file" ----
            (re.compile(r"(open|start|launch)\s+(.+?)\s+(and|aur|à¤”à¤°)\s+(create|make|new)\s+a\s+new\s+file|create a new file", re.I),
             "_handle_open_app_new_file"),

            # --- volume ---
            (re.compile(r"(?<!\S)(?:volume|sound|aawaz|à¤†à¤µà¤¾à¤œà¤¼|à¤†à¤µà¤¾à¤œ|à¤µà¥‰à¤²à¥à¤¯à¥‚à¤®)(?=\s|$)", re.I),
             "_handle_volume"),

            # --- screenshot ---
            (re.compile(r"\b(take|let's take|lets take|screenshot|capture)\s*(a\s+)?(screenshot|screen shot|screen)"
                        r"|(à¤¸à¥à¤•à¥à¤°à¥€à¤¨à¤¶à¥‰à¤Ÿ|à¤¸à¥à¤•à¥à¤°à¥€à¤¨ à¤«à¥‹à¤Ÿà¥‹|screenshot lo|screenshot le)", re.I),
             "_handle_screenshot"),

            # --- install (confirmation required) ---
            (re.compile(r"\b(install|download and install)\s+(?:software|app|application|program)?\s*[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"â€]?", re.I),
             "_handle_install"),

            # --- delete / remove (confirmation required) ---
            (re.compile(r"\b(delete|remove|erase|delete kar)\s+(?:the\s+|this\s+)?\s*(file|folder)?\s*[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?\s*(please)?$", re.I),
             "_handle_delete"),

            # --- file ops: move / copy / rename ---
            (re.compile(r"\bmove\s+(?:file\s+)?[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?\s+(?:to|ko|mein|à¤®à¥‡à¤‚)\s+[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?$", re.I),
             "_handle_move"),
            (re.compile(r"\bcopy\s+(?:file\s+)?[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?\s+(?:to|ko|mein|à¤®à¥‡à¤‚)\s+[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?$", re.I),
             "_handle_copy"),
            (re.compile(r"\brename\s+(?:file\s+)?[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?\s+(?:to|as|ko)\s+[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"â€]?$", re.I),
             "_handle_rename"),

            # --- create folder / file ---
            (re.compile(r"\b(create|make|banao|banaiye|create karo|bana kar do)\b"
                        r"|(à¤¬à¤¨à¤¾à¤“|à¤¬à¤¨à¤¾à¤ˆà¤¯à¥‡|à¤•à¥à¤°à¤¿à¤à¤Ÿ à¤•à¤°à¥‹)", re.I),
             "_handle_create"),

            # --- browser automation: read page / scroll / web search ---
            # (kept before "search files" so "search X on YouTube" hits the web)
            (re.compile(r"\b(read|open|summari[sz]e)\s+(?:this\s+)?"
                        r"(?:page|website|site|tab|web\s*page)\b"
                        r"|(?:this\s+|us\s+)?(?:page|website)\s+"
                        r"(?:ka\s+|ke\s+)?(?:summary|content|kya)\b", re.I),
             "_handle_browser_read"),
            (re.compile(r"\bscroll\s+(?:down|up|to\s+(?:bottom|top))\b"
                        r"|(?:scroll|skroll)\s+(?:karo|karen|kar)\b"
                        r"|(?:niche|neeche|upar)\s+(?:scroll|skroll)\b"
                        r"|\u0928\u0940\u091a\u0947 \u0938\u094d\u0915\u094d\u0930\u0949\u0932", re.I),
             "_handle_browser_scroll"),
            (re.compile(r"\b(search|google)\s+(?:for\s+)?(.{2,60}?)\s*"
                        r"(?:on\s+|pe\s+|ke\s+)(youtube|google|bing)\b"
                        r"|\b(youtube|google|bing)\s+(?:pe\s+)?(.{1,60}?)\s+"
                        r"(?:search|karo|dhoondho)", re.I),
             "_handle_browser_search"),

            # --- search files ---
            (re.compile(r"\b(find|search|search for|look for|dhoondo|à¤¢à¥‚à¤‚à¤¢à¥‹|à¤–à¥‹à¤œà¥‹)\b", re.I),
             "_handle_search"),

            # --- close app ---
            (re.compile(r"\b(close|close karo|band karo|à¤¬à¤‚à¤¦ à¤•à¤°à¥‹|à¤¬à¤‚à¤¦ à¤•à¤°)\s+(?:the\s+)?([\w\u0900-\u097F\u0300-\u036F\- .]+)$"
                        r"|(.+?)\s+(band karo|close karo|à¤¬à¤‚à¤¦ à¤•à¤°à¥‹|à¤¬à¤‚à¤¦ à¤•à¤°)$", re.I),
             "_handle_close_app"),

            # --- open folder / known location ---
            (re.compile(r"\b(open|show|kholo|khol|à¤–à¥‹à¤²à¥‹|à¤–à¥‹à¤²)\s+(?:the\s+|my\s+)?(desktop|downloads?|documents?|pictures|music|videos|my computer|this pc|home)", re.I),
             "_handle_open_folder"),

            # --- open website ---
            (re.compile(r"\b(open|start|go to|visit|kholo|khol|à¤–à¥‹à¤²à¥‹)\s+(?:the\s+|website\s+)?([\w.\-]+(?:\.(?:com|in|org|net|io|co|dev|me|xyz|ai))\b|youtube|google|gmail|github|stackoverflow|reddit|wikipedia|twitter|instagram|facebook|whatsapp|netflix|spotify|amazon|à¤¯à¥‚à¤Ÿà¥à¤¯à¥‚à¤¬|à¤—à¥‚à¤—à¤²|à¤œà¥€à¤®à¥‡à¤²)", re.I),
             "_handle_open_site"),

            # --- open/play a video on YouTube (keep before open-app) ---
            (re.compile(
                r"(?:open|start|play|watch|chalao|dikhao|"
                r"\u091a\u0932\u093e\u0913|\u0926\u093f\u0916\u093e\u0913)\s+"
                r"(?:a\s+|an\s+|the\s+|some\s+)?"
                r"(?:video\b|videos\b|\u0935\u0940\u0921\u093f\u092f\u094b)\s+"
                r"(?:in|on|pe)\s+youtube\b"
                r"|"
                r"(?:open|play|watch)\s+(?:the\s+)?"
                r"([\w\u0900-\u097F\u0300-\u036F'\- .]{2,60}?)\s+"
                r"(?:video\b|videos\b|\u0935\u0940\u0921\u093f\u092f\u094b)?\s*"
                r"(?:in|on|pe)\s+youtube\b",
                re.I),
             "_handle_open_youtube_video"),

            # --- open application (generic, EN + Hinglish + Devanagari) ---
            (re.compile(r"^(open|start|launch|open up|kholo|à¤–à¥‹à¤²à¥‹|à¤šà¤²à¤¾à¤“|\u0916\u094b\u0932\u094b|\u091a\u0932\u093e\u0913)\s+([\w\u0900-\u097F\u0300-\u036F\- .]+)$", re.I),
             "_handle_open_app"),
            (re.compile(r"^([\w\u0900-\u097F\u0300-\u036F\- .]+)\s+(kholo|khol|open karo|karo|à¤–à¥‹à¤²à¥‹|à¤šà¤²à¤¾à¤“|\u0916\u094b\u0932\u094b|\u091a\u0932\u093e\u0913)$", re.I),
             "_handle_open_app"),

            # --- type / press key / mouse click ---
            (re.compile(r"^\s*(type|type out|typewrite|likho|à¤²à¤¿à¤–à¥‹)\s*(?:text\s+|out\s+)?[\"â€œ]?(.+?)[\"â€]?$", re.I),
             "_handle_type"),
            (re.compile(r"^\s*(press|press key|press keys|dabao|à¤¦à¤¬à¤¾à¤“)\s+([\w +\-]+)$", re.I),
             "_handle_press_key"),
            (re.compile(r"^\s*(double\s+click|click\s+twice)\s*(?:at\s*)?(\d+)?(?:\s*[, ]\s*(\d+))?$", re.I),
             "_handle_mouse"),
            (re.compile(r"^\s*click\s*(?:at\s*)?(\d+)?(?:\s*[, ]\s*(\d+))?$", re.I),
             "_handle_mouse"),
        ]

    def _remember(self, role: str, text: str):
        """Store a conversation entry per the privacy retention policy."""
        ts = datetime.now().isoformat()
        entry = {"role": role, "text": text, "timestamp": ts}
        self.conversation_history.append(entry)
        append_conversation(role, text, ts)   # no-op unless retention=disk

    # ------------------------------------------------------------------ flow
    def process(self, user_input: str) -> Tuple[str, str]:
        if not user_input or not user_input.strip():
            return ("I didn't catch that. Could you repeat?", "speak")

        text = user_input.strip()
        log.info("User command received (%d chars)", len(text))
        self.last_user_lang = detect_lang(text)
        self._remember("user", text)
        telemetry_record("command_processed", count=1,
                         provider=getattr(self.ai, "name", "none"),
                         language=self.last_user_lang)

        # Explicit high-risk phrasing -> refusal, never silent.
        if classify_text_high_risk(text):
            self.last_action_ok = False
            self.last_action_summary = "Blocked high-risk action"
            response = ("That action is too risky for me to perform. "
                        "I won't touch system files, disk formats, or security "
                        "settings unless that policy is explicitly changed.")
            self._log_response(response, "speak")
            return (response, "speak")

        # Pending confirmation flow overrides normal matching.
        if self._pending_plan:
            if _CONFIRM_YES.match(text.strip()):
                return self._finish_and_return(self._run_pending(True), text)
            if _CONFIRM_NO.match(text.strip()):
                return self._finish_and_return(self._run_pending(False), text)

        for pattern, handler_name in self.PATTERNS:
            if pattern.search(text):
                handler = getattr(self, handler_name)
                response, action = handler(text)
                return self._finish_and_return((response, action), text)

        # Unknown intent -> local AI (no cloud fallback, ever).
        return self._finish_and_return(self._handle_with_ai(text), text)

    # ------------------------------------------------------------ AI flow
    def _handle_with_ai(self, text: str) -> Tuple[str, str]:
        provider = getattr(self, "ai", None)
        if provider is None:
            return self._fallback_unknown(text)

# Redact before anything reaches a model (local or cloud).
        safe = redact_secrets(text)

        if getattr(provider, "kind", "local") != "local":
            blocked = self._cloud_privacy_guard(safe, text)
            if blocked:
                return blocked
        else:
            # Memory context is private and only ever trusted locally.
            ctx = memory_store.context_facts(8)
            if ctx:
                safe = ("Private memory (use naturally, never quote unless "
                        f"asked):\n{ctx}\n\nUser: {safe}")

        try:
            plan = provider.plan(safe)
        except (AIUnavailable, AIBlocked):
            self.last_action_ok = False
            self.last_action_summary = "Local AI unavailable"
            telemetry_record("ai_unavailable", provider=provider.name)
            return (_LOCAL_UNAVAILABLE, "speak")
        except Exception as e:
            log.warning("AI plan failed: %s", e)
            return self._fallback_unknown(text)
        telemetry_record("ai_plan", provider=provider.name,
                         count=1 if plan else 0)

        if not plan:
            return self._fallback_unknown(text)

        if plan.get("intent") == "chat":
            return self._chat_from_model(plan.get("message", ""))

        # Structured tool proposal -> reuse the deterministic pipeline so
        # every action still passes allowlist + risk classification.
        tool, params = plan.get("tool", ""), plan.get("params", {})
        if str(tool) not in TOOL_BASE_RISK:
            return self._fallback_unknown(text)
        risk = classify(text, tool, params)
        if risk >= RiskLevel.HIGH_RISK:
            self.last_action_ok = False
            self.last_action_summary = "Blocked high-risk AI action"
            return ("I won't do that automatically \u2014 it's a high-risk "
                    "action, even coming from a local model.", "speak")

        step = ActionStep(tool, params, label=f"{tool} (planned by AI)",
                          risk=risk)
        return self._run_ai_step(step, text)

    def _run_ai_step(self, step: ActionStep, text: str) -> Tuple[str, str]:
        if step.risk >= RiskLevel.CONFIRMATION_REQUIRED:
            plan = ActionPlan(steps=[step], rationale="planned by local AI")
            ask = ("This needs your confirmation before I run it. "
                   "Say yes to confirm, or say cancel.")
            return self._stage_confirmation(plan, ask)
        response = self._run([step], text)
        return (response, "execute")

    def _cloud_privacy_guard(self, safe: str, raw: str):
        """Extra gate: sensitive content never auto-sends to a cloud model,
        even when Cloud AI is enabled. Refuses rather than transmits.
        `raw` (pre-redaction) is what determines sensitivity â€” redaction
        must not launder a secret past the firewall."""
        if looks_sensitive(raw or safe):
            self.last_action_ok = False
            self.last_action_summary = "Sensitive content not sent to cloud"
            return (
                "That request looks sensitive, so I won't send it to a "
                "cloud model. Enable local AI (Ollama) to handle it on "
                "this machine.", "speak")
        return None

    def _chat_from_model(self, message: str) -> Tuple[str, str]:
        if not (message or "").strip():
            return self._fallback_unknown("")
        self.last_action_ok = True
        self.last_action_summary = "Replied"
        return (message, "speak")

    def _fallback_unknown(self, text: str) -> Tuple[str, str]:
        response = self._handle_unknown(text)
        return (response, "speak")

    def _log_response(self, response: str, action: str, text: str = ""):
        self._remember("nova", response)
        # Log metadata only â€” never the reply body.
        log.info("Reply ready (action=%s, %d chars)", action, len(response))

    def _finish_and_return(self, result: Tuple[str, str], text: str) -> Tuple[str, str]:
        # Natural success prefix in the user's language (only after a
        # verified, successfully executed action).
        response, action = result
        if action == "execute" and self.last_action_ok:
            lang = getattr(self, "last_user_lang", "en")
            if lang == "hi":
                response = f"à¤œà¤¼à¤°à¥‚à¤°, {response}"
            elif lang == "hinglish":
                response = f"Sure, {response}"
            result = (response, action)
        self._log_response(result[0], result[1], text)
        return result

    # ------------------------------------------------------------ query handlers
    def _handle_greeting(self, text: str) -> Tuple[str, str]:
        hour = datetime.now().hour
        greeting = ("Good morning" if hour < 12 else
                    "Good afternoon" if hour < 17 else "Good evening")
        return (f"{greeting}! I'm NOVA, your AI assistant. How can I help you?", "speak")

    def _handle_capabilities(self, text: str) -> Tuple[str, str]:
        return (
            "I can open and close applications, open websites and folders, "
            "create folders and files, move, copy, rename, search and delete "
            "files with your confirmation, take screenshots, control volume, "
            "type text, and press keys. Just say something like "
            "\u201cOpen Chrome\u201d or \u201cVolume 50 percent karo\u201d.",
            "speak",
        )

    def _handle_time(self, text: str) -> Tuple[str, str]:
        return (f"The current time is {datetime.now().strftime('%I:%M %p')}.", "speak")

    def _handle_date(self, text: str) -> Tuple[str, str]:
        return (f"Today is {datetime.now().strftime('%A, %B %d, %Y')}.", "speak")

    def _handle_identity(self, text: str) -> Tuple[str, str]:
        return (
            "I'm NOVA, your personal AI voice assistant. "
            "Think of me as your futuristic digital companion.",
            "speak",
        )

    def _handle_thanks(self, text: str) -> Tuple[str, str]:
        return ("You're welcome! Let me know if you need anything else.", "speak")

    def _handle_quit(self, text: str) -> Tuple[str, str]:
        return ("Goodbye! See you soon.", "quit")

# ------------------------------------------------------------ memory
    @staticmethod
    def _mem_key(name: str) -> str:
        """Namespace a memory key so user facts are easy to browse/care."""
        return f"user_{name}"

    def _remember_ok_reply(self) -> str:
        lang = getattr(self, "last_user_lang", "en")
        if lang == "hi":
            return "Theek hai, main ye yaad rakhungi. \u2764\ufe0f"
        if lang == "hinglish":
            return "Okay, main ye yaad rakhungi \u2764\ufe0f"
        return "Got it \u2014 I'll remember that. \u2764\ufe0f"

    def _handle_remember(self, text: str) -> Tuple[str, str]:
        value, key = self._extract_memory(text)
        if not value:
            return self._fail("I couldn't figure out what to remember.")
        ok = memory_store.remember(key, value)
        if not ok:
            self.last_action_ok = True
            self.last_action_summary = "Memory refused (sensitive)"
            return ("I'd rather not store that \u2014 it looks sensitive. "
                    "Secrets never go into my memory.", "speak")
        self.last_action_ok = True
        self.last_action_summary = f"Remembered: {key}"
        return (self._remember_ok_reply(), "speak")

    def _extract_memory(self, text: str):
        """Return (value, key) for a remember/preference/name phrase."""
        low = text
        name = re.search(
            r"(?:my name is|mera naam|call me|"
            r"\u092e\u0947\u0930\u093e \u0928\u093e\u092e)\s+[\"\u201c]?"
            r"([A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F .]{1,40})", low, re.I)
        if name:
            return (self._clean_name(name.group(1)),
                    self._mem_key("name"))

        app = re.search(
            r"(?:mostly use|use karta hoon|use karti hoon|prefer|i like|i like "
            r"using|i use)\s+(?:the\s+|to\s+use\s+)?[\"\u201c]?"
            r"([A-Za-z\u0900-\u097F0-9][A-Za-z\u0900-\u097F0-9 .\-]{1,40})",
            low, re.I)
        lang = re.search(r"(?i)\b(hindi|english|hinglish)\b", low)
        if app and lang:
            return (lang.group(1).lower(),
                    self._mem_key("preferred_language"))
        if app:
            return (self._clean_name(app.group(1)),
                    self._mem_key(f"favorite_app_{app.group(1).strip().lower()[:24]}"))

        catch = re.search(
            r"(?:remember\s+(?:that\s+|this\s+|to\s+|ye\s+)?|note karo"
            r"|\u0928\u094b\u091f \u0915\u0930\u094b"
            r"|\u092f\u093e\u0926 \u0930\u0916\u0928\u093e"
            r"|\u092f\u093e\u0926 \u0930\u0916\u094b)\s*(.+)$", low, re.I)
        if catch and catch.group(1).strip():
            value = self._clean_name(catch.group(1))
            slug = re.sub(r"[^a-z0-9]+", "_", value.lower())[:34].strip("_")
            return (value, self._mem_key(f"fact_{slug}" if slug else "fact"))
        # fallback: entire cleaned remainder after any keyword
        m = re.search(r"(?:main|mein|main mostly|mujhe)\s+(?:mostly\s+|bahut\s+)?"
                      r"(.{1,60})$", low, re.I)
        if m:
            value = self._clean_name(m.group(1))
            slug = re.sub(r"[^a-z0-9]+", "_", value.lower())[:34].strip("_")
            return (value, self._mem_key(f"fact_{slug}" if slug else "fact"))
        return ("", "")

    def _handle_memory_recall(self, text: str) -> Tuple[str, str]:
        entries = memory_store.all()
        if not entries:
            return ("My memory is empty right now \u2014 but I'm happy to learn "
                    "about you. \u2764\ufe0f", "speak")
        facts = " \u2022 ".join(f"{e['key']}: {e['value']}" for e in entries[:10])
        self.last_action_ok = True
        self.last_action_summary = f"{len(entries)} memories"
        return (f"I remember: {facts}", "speak")

    def _handle_forget(self, text: str) -> Tuple[str, str]:
        m = re.search(r"(?:forget|yaad mat rakho|bhool jao"
                      r"|\u092e\u0924 \u0930\u0916\u094b"
                      r"|\u092d\u0942\u0932 \u091c\u093e\u0913)\s*(.+)?$",
                      text, re.I)
        target = (self._clean_name(m.group(1)) if m and m.group(1) else "").lower()
        if not target:
            return ("What should I forget?", "speak")
        target = re.sub(r"^(?:my|the|a|an|mera|apna|aapka)\s+", "", target)
        if target in ("name", "naam", "user name"):
            target = "name"
        removed = 0
        for e in memory_store.all():
            if target in e["key"].lower() or target in e["value"].lower():
                if memory_store.forget(e["key"]):
                    removed += 1
        if removed:
            self.last_action_ok = True
            return (f"Okay, I've forgotten that ({removed} item{'s' if removed != 1 else ''}).",
                    "speak")
        return ("I don't think I remembered that one. \u2764\ufe0f", "speak")

    def _handle_clear_memory(self, text: str) -> Tuple[str, str]:
        n = memory_store.clear()
        self.last_action_ok = True
        self.last_action_summary = "Memory cleared"
        return (f"My memory is cleared ({n} items). \u2764\ufe0f", "speak")

    def _handle_high_risk_refusal(self, text: str) -> Tuple[str, str]:
        return (
            "I won't do that â€” it's a high-risk operation and NOVA never "
            "executes high-risk actions silently.",
            "speak",
        )

    def _handle_unknown(self, text: str) -> str:
        self.last_action_ok = False
        self.last_action_summary = "I didn't understand that"
        return (
            f"I heard you say \u201c{text}\u201d, but I'm not sure how to help with that yet. "
            "Try \u201cOpen Chrome\u201d, \u201cDesktop pe ek folder banao naam Projects\u201d, "
            "\u201cVolume 50 percent karo\u201d, or \u201cTake a screenshot\u201d."
        )

    # -------------------------------------------------------- automation handlers
    def _handle_open_app_new_file(self, text: str) -> Tuple[str, str]:
        m = re.search(r"(open|start|launch)\s+(.+?)\s+(and|aur|à¤”à¤°)\s+create", text, re.I)
        try:
            app = self._clean_name(m.group(2)) if m else ""
        except IndexError:
            app = ""
        if not app:
            return self._fail("I couldn't tell which app to open.")
        steps = [
            ActionStep("open_application", {"name": app},
                       label=f"Open {app}", risk=RiskLevel.SAFE),
            ActionStep("press_key", {"keys": ["ctrl", "n"]},
                       label="Create a new file (Ctrl+N)",
                       risk=RiskLevel.SAFE),
        ]
        response = self._run(steps, text)
        return (response, "execute")

    def _handle_open_app(self, text: str) -> Tuple[str, str]:
        name = self._extract_open_app_name(text)
        if not name:
            return self._fail("I couldn't tell which app to open.")
        steps = [ActionStep("open_application", {"name": name},
                            label=f"Open {name}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _extract_open_app_name(self, text: str) -> Optional[str]:
        low = text.strip()
        m = re.match(r"^(?:open|start|launch|open up|kholo|à¤–à¥‹à¤²à¥‹|à¤šà¤²à¤¾à¤“|\u0916\u094b\u0932\u094b|\u091a\u0932\u093e\u0913)\s+(.+)$", low, re.I)
        if m:
            return self._clean_name(m.group(1))
        m = re.match(r"^(.+?)\s+(?:kholo|khol|open karo|karo|à¤–à¥‹à¤²à¥‹|à¤šà¤²à¤¾à¤“|\u0916\u094b\u0932\u094b|\u091a\u0932\u093e\u0913)$", low, re.I)
        if m:
            return self._clean_name(m.group(1))
        return None

    def _handle_open_site(self, text: str) -> Tuple[str, str]:
        site = self._extract_site(text)
        if not site:
            return self._fail("I couldn't find that website.")
        url = _SITE_MAP.get(site.lower(), site if site.startswith(("http", "www.")) else "https://" + site)
        steps = [ActionStep("open_url", {"url": url},
                            label=f"Open {site}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _extract_site(self, text: str) -> Optional[str]:
        m = re.search(r"(?:open|start|go to|visit|kholo|khol|à¤–à¥‹à¤²à¥‹)\s+(?:the\s+|website\s+)?([\w.\-]+\.[a-z]{2,}|youtube|google|gmail|github|stackoverflow|reddit|wikipedia|twitter|instagram|facebook|whatsapp|netflix|spotify|amazon|à¤¯à¥‚à¤Ÿà¥à¤¯à¥‚à¤¬|à¤—à¥‚à¤—à¤²|à¤œà¥€à¤®à¥‡à¤²)", text, re.I)
        return (m.group(1) if m else None)

    # -------------------------------------------------------- browser handlers
    def _browser_offline(self) -> bool:
        if nova_config.browser.enabled:
            return False
        self.last_action_ok = False
        self.last_action_summary = "Browser automation disabled"
        return True

    def _handle_browser_read(self, text: str) -> Tuple[str, str]:
        if self._browser_offline():
            return ("Browser automation is disabled right now. You can turn it "
                    "on in Settings.", "speak")
        steps = [ActionStep("browser_read", {},
                            label="Read the current page",
                            risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_browser_scroll(self, text: str) -> Tuple[str, str]:
        if self._browser_offline():
            return ("Browser automation is disabled right now. You can turn it "
                    "on in Settings.", "speak")
        low = text.lower()
        if "top" in low or "upar" in low or re.search(r"\bup\b", low):
            direction = "up"
        elif "bottom" in low:
            direction = "bottom"
        else:
            direction = "down"
        steps = [ActionStep("browser_scroll", {"direction": direction},
                            label=f"Scroll {direction}",
                            risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_browser_search(self, text: str) -> Tuple[str, str]:
        if self._browser_offline():
            return ("Browser automation is disabled right now. You can turn it "
                    "on in Settings.", "speak")
        q, site = None, "google"
        m = re.search(r"(?:search|google)\s+(?:for\s+)?(.{2,60}?)\s*(?:on\s+|pe\s+|ke\s+)(youtube|google|bing)\b", text, re.I)
        if m:
            q, site = m.group(1), m.group(2).lower()
        else:
            m = re.search(r"(youtube|google|bing)\s+(?:pe\s+)?(.{1,60}?)\s+"
                          r"(?:search|karo|dhoondho"
                          r"|\u0916\u094b\u091c\u094b|\u0922\u0942\u0902\u0922\u094b)\b",
                          text, re.I)
            if m:
                site, q = m.group(1).lower(), m.group(2)
        if not q:
            m = re.search(r"google\s+(?:it\s+|karo\s+)?(.{1,60})$", text, re.I)
            if m:
                q = m.group(1)
        if not q:
            return self._fail("I couldn't work out what to search for.")
        q = self._clean_name(q).strip()
        if site == "yt":
            site = "youtube"
        steps = [ActionStep("browser_search", {"query": q, "engine": site},
                            label=f"Search {q} on {site}",
                            risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_open_youtube_video(self, text: str) -> Tuple[str, str]:
        if self._browser_offline():
            return ("Browser automation is disabled right now. You can turn it "
                    "on in Settings.", "speak")
        if re.search(
                r"(?:open|start|play|watch|chalao|dikhao|"
                r"\u091a\u0932\u093e\u0913|\u0926\u093f\u0916\u093e\u0913)\s+"
                r"(?:a\s+|an\s+|the\s+|some\s+)?"
                r"(?:video\b|videos\b|\u0935\u0940\u0921\u093f\u092f\u094b)\s+"
                r"(?:in|on|pe)\s+youtube\b", text, re.I):
            steps = [ActionStep("browser_open_url", {"url": "youtube.com"},
                                label="Open YouTube",
                                risk=RiskLevel.SAFE)]
            return self._finish_tool(steps, text)
        m = re.search(
            r"(?:open|play|watch)\s+(?:the\s+)?"
            r"([\w\u0900-\u097F\u0300-\u036F'\- .]{2,60}?)\s+"
            r"(?:video\b|videos\b|\u0935\u0940\u0921\u093f\u092f\u094b)?\s*"
            r"(?:in|on|pe)\s+youtube\b", text, re.I)
        if not m:
            return self._fail("I couldn't work out what video you'd like.")
        q = self._clean_name(m.group(1)).strip()
        steps = [ActionStep("browser_search", {"query": q, "engine": "youtube"},
                            label=f"Search {q} on YouTube",
                            risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_open_folder(self, text: str) -> Tuple[str, str]:
        loc = self._extract_folder_keyword(text)
        if loc in ("this_pc", "my_computer"):
            clsid = "{20D04FE0-3AEA-1069-A2D8-08002B30309D}"  # This PC
            steps = [ActionStep("open_folder", {"path": "::" + clsid},
                                label="Open This PC", risk=RiskLevel.SAFE)]
            return self._finish_tool(steps, text)
        path = resolve_location(loc) or default_folder(loc)
        steps = [ActionStep("open_folder", {"path": path},
                            label=f"Open {loc}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _extract_folder_keyword(self, text: str) -> str:
        low = text.lower()
        for key in ("downloads", "download", "documents", "document",
                    "desktop", "pictures", "music", "videos", "home",
                    "my computer", "this pc"):
            if key in low:
                if key in ("my computer", "this pc"):
                    return "this_pc"
                return key
        return "desktop"

    def _handle_volume(self, text: str) -> Tuple[str, str]:
        action, value, mute = self._volume_command(text)
        if action is None and mute is None:
            from automation.verifier import volume_level
            now = volume_level()
            level = (now * 100 if now is not None else None)
            if level is None:
                return self._fail("I couldn't read the current volume.")
            return (f"The volume is currently {level:.0f} percent.", "speak")
        params = {"action": action} if action else {}
        if action in ("set", "up", "down"):
            params["value"] = value
        if mute is not None:
            params["mute"] = mute
        steps = [ActionStep("volume_control", params,
                            label="Adjust volume", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _volume_command(self, text: str):
        low = text.lower()
        if re.search(r"(?<!\S)(?:unmute|aawaz chalu|à¤†à¤µà¤¾à¤œà¤¼ à¤šà¤¾à¤²à¥‚)(?=\s|$)", low):
            return (None, None, False)
        if re.search(r"\bmute\b|(?<!\S)à¤†à¤µà¤¾à¤œà¤¼ à¤¬à¤‚à¤¦(?=\s|$)", low):
            return (None, None, True)
        number = self._extract_number(text)
        kam = bool(re.search(r"\b(kam|kum|ghata|decrease|dheema|slow)\b|(?<!\S)(à¤•à¤®|à¤˜à¤Ÿà¤¾à¤“|à¤§à¥€à¤®à¤¾)(?=\s|$)", low))
        up = bool(re.search(r"\b(up|zyada|badhao|increase|tez|high)\b|(?<!\S)(à¤¬à¤¢à¤¼à¤¾à¤“|à¤œà¤¼à¥à¤¯à¤¾à¤¦à¤¾)(?=\s|$)", low))
        if number is not None and up and kam:
            return ("set", number, None)
        if number is not None:
            if kam and re.search(r"\b(thoda|zara|little)\b|(?<!\S)à¤¥à¥‹à¤¡à¤¼à¤¾(?=\s|$)", low):
                return ("down", number, None)
            return ("set", number, None)
        if up:
            return ("up", 10, None)
        if kam:
            return ("down", 15, None)
        return (None, None, None)

    def _handle_screenshot(self, text: str) -> Tuple[str, str]:
        steps = [ActionStep("take_screenshot", {}, label="Take screenshot",
                            risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_install(self, text: str) -> Tuple[str, str]:
        pkg = self._extract_package(text)
        if not pkg:
            return self._fail("I couldn't tell which software to install.")
        step = ActionStep("install_software", {"package": pkg},
                          label=f"Install {pkg}",
                          risk=classify_step("install_software", {"package": pkg}))
        plan = ActionPlan(steps=[step])
        ask = f"This will install {pkg} using the Windows Package Manager. Say yes to confirm, or say cancel."
        return self._stage_confirmation(plan, ask)

    def _extract_package(self, text: str) -> Optional[str]:
        m = re.search(r"(?:install|download and install)\s+(?:software|app|application|program|the\s+)?[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"â€]?\s*(?:please)?$", text, re.I)
        return self._clean_name(m.group(1)) if m else None

    def _handle_delete(self, text: str) -> Tuple[str, str]:
        target = self._extract_target(text)
        if not target:
            return self._fail("I couldn't tell which file to delete.")
        is_dir = bool(re.search(r"\b(folder|directory)\b", text, re.I))
        # put back any leading 'file'/'folder' keyword
        step = ActionStep("delete_file", {"path": target, "is_dir": is_dir},
                          label=f"Delete {target}",
                          risk=classify_step("delete_file", {"path": target}))
        if step.risk >= RiskLevel.HIGH_RISK:
            return self._high_risk_blocked()
        plan = ActionPlan(steps=[step])
        ask = f"You asked me to delete {target}. That needs your confirmation â€” say yes to confirm, or say cancel."
        return self._stage_confirmation(plan, ask)

    def _high_risk_blocked(self) -> Tuple[str, str]:
        self.last_action_ok = False
        return ("I won't delete that â€” it's in a protected system area, which is a high-risk action.", "speak")

    def _extract_target(self, text: str) -> Optional[str]:
        m = re.search(r"(?:delete|remove|erase|delete kar)\s+(?:the\s+|this\s+)?(?:file|folder)?\s*[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?\s*(please)?$", text, re.I)
        return (m.group(1).strip() if m else None)

    def _handle_move(self, text: str) -> Tuple[str, str]:
        m = re.match(r"move\s+(?:file\s+)?[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?\s+(?:to|ko|mein|à¤®à¥‡à¤‚)\s+[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?$", text, re.I)
        if not m:
            return self._fail("I couldn't work out what to move where.")
        src, dst = m.group(1).strip(), m.group(2).strip()
        steps = [ActionStep("move_file", {"source": src, "destination": dst},
                            label=f"Move {src}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_copy(self, text: str) -> Tuple[str, str]:
        m = re.match(r"copy\s+(?:file\s+)?[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?\s+(?:to|ko|mein|à¤®à¥‡à¤‚)\s+[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?$", text, re.I)
        if not m:
            return self._fail("I couldn't work out what to copy where.")
        src, dst = m.group(1).strip(), m.group(2).strip()
        steps = [ActionStep("copy_file", {"source": src, "destination": dst},
                            label=f"Copy {src}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_rename(self, text: str) -> Tuple[str, str]:
        m = re.match(r"rename\s+(?:file\s+)?[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"â€]?\s+(?:to|as|ko)\s+[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"â€]?$", text, re.I)
        if not m:
            return self._fail("I couldn't work out what to rename.")
        src, new = m.group(1).strip(), m.group(2).strip()
        steps = [ActionStep("rename_file", {"source": src, "new_name": new},
                            label=f"Rename {src}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_create(self, text: str) -> Tuple[str, str]:
        low = text.lower()
        is_folder = bool(re.search(r"\b(folder|à¤«à¥‹à¤²à¥à¤¡à¤°|directory)\b", low))
        is_file = bool(re.search(r"\b(file|à¤«à¤¾à¤‡à¤²|document)\b", low))
        if not (is_folder or is_file):
            return self._fail("I could create a folder or a file â€” which one did you mean?")
        name = self._extract_name(text)
        if not name:
            name = self._derive_name(text, is_folder)
        if not name:
            return self._fail("I couldn't tell what to name it.")
        base = self._location_path(text)
        tool = "create_folder" if is_folder else "create_file"
        params = {"name": name, "location": base}
        steps = [ActionStep(tool, params, label=f"Create {name}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _derive_name(self, text: str, is_folder: bool) -> Optional[str]:
        low = text.lower()
        # "<location> mein X folder" form (no 'naam' keyword)
        m = re.search(r"(?:mein|main|in|à¤®à¥‡à¤‚)\s+[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"â€]?\s*(?:folder|file|à¤«à¥‹à¤²à¥à¤¡à¤°|à¤«à¤¾à¤‡à¤²)", low, re.I)
        if m:
            return self._clean_name(m.group(1))
        # trailing-word form: "create file expenses" -> expenses
        m = re.search(r"(?:create|make|banao)\s+(?:a\s+|an\s+|the\s+)?(?:folder|file|à¤«à¥‹à¤²à¥à¤¡à¤°|à¤«à¤¾à¤‡à¤²)\s+(?:named\s+|naam\s+|à¤•à¤¾\s+)?[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"â€]?$", low, re.I)
        if m:
            return self._clean_name(m.group(1))
        return None

    def _handle_search(self, text: str) -> Tuple[str, str]:
        query, loc = self._search_params(text)
        params = {"query": query}
        if loc:
            params["location"] = loc
        steps = [ActionStep("search_files", params, label="Search files",
                            risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _search_params(self, text: str) -> Tuple[str, str]:
        low = text.lower()
        m = re.search(r"(?:find|search|search for|look for|dhoondo|à¤¢à¥‚à¤‚à¤¢à¥‹|à¤–à¥‹à¤œà¥‹)\s+(?:for\s+|files?\s+(?:named|called|naam)\s+)?[\"â€œ]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"â€]?\s*(?:in|mein|à¤®à¥‡à¤‚|on)\s+([\w\u0900-\u097F\u0300-\u036F\- .]+)?$", low, re.I)
        if m:
            query = m.group(1).strip()
            loc = m.group(2).strip() if m.group(2) else ""
            return (query, resolve_location(loc) if loc else "")
        m = re.search(r"(?:find|search for)\s+(?:files?\s+)?(.*?)$", low, re.I)
        return ((m.group(1).strip() if m and m.group(1) else "*"), "")

    def _handle_close_app(self, text: str) -> Tuple[str, str]:
        name = self._extract_close_app(text)
        if not name:
            return self._fail("I couldn't tell which app to close.")
        steps = [ActionStep("close_application", {"name": name},
                            label=f"Close {name}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _extract_close_app(self, text: str) -> Optional[str]:
        m = re.match(r"(?:close|close karo|band karo)\s+(?:the\s+)?([\w\u0900-\u097F\u0300-\u036F\- .]+)$", text, re.I)
        if m:
            return self._clean_name(m.group(1))
        m = re.match(r"([\w\u0900-\u097F\u0300-\u036F\- .]+)\s+(?:band karo|close karo|à¤¬à¤‚à¤¦ à¤•à¤°à¥‹|à¤¬à¤‚à¤¦ à¤•à¤°)$", text, re.I)
        if m:
            return self._clean_name(m.group(1))
        return None

    def _handle_type(self, text: str) -> Tuple[str, str]:
        m = re.match(r"^\s*(?:type|type out|typewrite|likho|à¤²à¤¿à¤–à¥‹)\s*(?:text\s+|out\s+)?[\"â€œ]?(.+?)[\"â€]?$", text, re.I)
        if not m or not m.group(1).strip():
            return self._fail("I couldn't tell what to type.")
        steps = [ActionStep("type_text", {"text": m.group(1)},
                            label="Type text", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_press_key(self, text: str) -> Tuple[str, str]:
        m = re.match(r"^\s*(?:press|press key|press keys|dabao|à¤¦à¤¬à¤¾à¤“)\s+([\w +\-]+)$", text, re.I)
        if not m:
            return self._fail("I couldn't tell which key to press.")
        chord = m.group(1).strip()
        keys = self._chord_parse(chord)
        if not keys:
            return self._fail("I don't recognise that key.")
        steps = [ActionStep("press_key", {"keys": keys},
                            label=f"Press {chord}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _chord_parse(self, chord: str) -> Optional[list[str]]:
        from automation.tools.input_tools import _parse_keys
        return _parse_keys(chord)

    def _handle_mouse(self, text: str) -> Tuple[str, str]:
        double = bool(re.match(r"\s*double\s+click", text, re.I))
        nums = re.findall(r"\d+", text)
        params = {"double": double}
        if len(nums) >= 2:
            params["x"], params["y"] = int(nums[0]), int(nums[1])
        steps = [ActionStep("mouse_click", params, label="Mouse click",
                            risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    # shared finalizer for tool handlers ------------------------------------
    def _finish_tool(self, steps: list[ActionStep], text: str) -> Tuple[str, str]:
        for s in steps:
            s.risk = max(s.risk, classify(text, s.tool, s.params))
        response = self._run(steps, text)
        return (response, "execute")

    def get_history(self, limit: int = 50) -> list[dict]:
        return self.conversation_history[-limit:]
