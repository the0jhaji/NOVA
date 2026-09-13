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
from automation.safety import classify, classify_text_high_risk, classify_step
from automation.paths import resolve_location, default_folder
from voice.language import detect_lang


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
    "यूट्यूब": "https://www.youtube.com",
    "गूगल": "https://www.google.com",
    "जीमेल": "https://mail.google.com",
}

_NAAM_KEYWORDS = re.compile(
    r"\b(naam|named|name|called|called as|named as|नाम)\b", re.I
)
_LOCATION_WORDS = {
    "desktop", "downloads", "download", "documents", "document",
    "pictures", "music", "videos", "home",
}

_CONFIRM_YES = re.compile(
    r"^(yes|haan|hum|han|confirm|yeah|yep|ok|okay|theek hai|kar do|karo"
    r"|हाँ|हां|ठीक है|करो|हैजा)$",
    re.I,
)
_CONFIRM_NO = re.compile(
    r"^(no|cancel|nahi|na|nope|mat karo|rook do|stop|रद्द|नहीं|मत करो|रोको)$",
    re.I,
)


class NovaAgent:
    """
    NOVA's brain — processes text commands and returns responses.

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
        """Name after naam/named/name/नाम, cleaned of trailing stopwords."""
        m = _NAAM_KEYWORDS.search(text or "")
        if not m:
            return None
        tail = text[m.end():]
        m2 = re.match(r"\s*[:\-]?\s*[\"“']?([\w\u0900-\u097F\u0300-\u036F\- .]+)[\"”']?", tail)
        if not m2:
            return None
        return self._clean_name(m2.group(1), spatial=True)

    def _clean_name(self, raw: str, spatial: bool = False) -> str:
        tokens = raw.strip().split()
        stop = {"karo", "kar", "do", "de", "banao", "banaiye", "kare",
                "create", "make", "please", "folder", "file", "का",
                "करो", "दो", "बनाओ", }
        if spatial:
            stop |= {"on", "in", "pe", "par", "mein", "main", "mat",
                     "पर", "में", "पे", "मैं"}
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
                        r"|(?<!\S)(नमस्ते|नमस्कार|हैलो|हाय|नमो)(?=\s|$)", re.I),
             "_handle_greeting"),
            (re.compile(r"(hello\s*nova|hi\s*nova|hey\s*nova)", re.I),
             "_handle_greeting"),

            # What can you do
            (re.compile(r"what can you do|tum kya kar sakti|kya kar sakti ho"
                        r"|your capabilities|capabilities"
                        r"|(तुम क्या कर सकती हो|क्या कर सकती हो)", re.I),
             "_handle_capabilities"),

            # Time / Date (question forms only, so file op keywords don't collide)
            (re.compile(r"(what time|what's the time|the time|kitne baje|kya time"
                        r"|time kya hai|samay batao|vakt batao|kya samay)"
                        r"|(समय क्या हुआ|कितने बजे|क्या समय|वक्त बताओ)", re.I),
             "_handle_time"),
            (re.compile(r"(what date|what's the date|what is the date|today's date"
                        r"|aaj ki date|kya date hai|kya tarikh hai|tarikh batao)"
                        r"|(आज की तारीख|तारीख बताओ)", re.I),
             "_handle_date"),

            # Who are you / Thanks / Quit
            (re.compile(r"(who are you|tum\s+kaun|kaun ho|your name|tumhara naam"
                        r"|apna naam|naam kya hai|naam batao)"
                        r"|(तुम कौन हो|कौन हो)", re.I),
             "_handle_identity"),
            (re.compile(r"\b(thanks?|thank you|shukriya|dhanyavaad)\b"
                        r"|(शुक्रिया|धन्यवाद)", re.I),
             "_handle_thanks"),
            (re.compile(r"\b(quit|exit|bye|goodbye)\b|(अलविदा)", re.I),
             "_handle_quit"),

            # --- compound action: "Open VS Code and create a new file" ----
            (re.compile(r"(open|start|launch)\s+(.+?)\s+(and|aur|और)\s+(create|make|new)\s+a\s+new\s+file|create a new file", re.I),
             "_handle_open_app_new_file"),

            # --- volume ---
            (re.compile(r"(?<!\S)(?:volume|sound|aawaz|आवाज़|आवाज|वॉल्यूम)(?=\s|$)", re.I),
             "_handle_volume"),

            # --- screenshot ---
            (re.compile(r"\b(take|let's take|lets take|screenshot|capture)\s*(a\s+)?(screenshot|screen shot|screen)"
                        r"|(स्क्रीनशॉट|स्क्रीन फोटो|screenshot lo|screenshot le)", re.I),
             "_handle_screenshot"),

            # --- install (confirmation required) ---
            (re.compile(r"\b(install|download and install)\s+(?:software|app|application|program)?\s*[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"”]?", re.I),
             "_handle_install"),

            # --- delete / remove (confirmation required) ---
            (re.compile(r"\b(delete|remove|erase|delete kar)\s+(?:the\s+|this\s+)?\s*(file|folder)?\s*[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?\s*(please)?$", re.I),
             "_handle_delete"),

            # --- file ops: move / copy / rename ---
            (re.compile(r"\bmove\s+(?:file\s+)?[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?\s+(?:to|ko|mein|में)\s+[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?$", re.I),
             "_handle_move"),
            (re.compile(r"\bcopy\s+(?:file\s+)?[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?\s+(?:to|ko|mein|में)\s+[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?$", re.I),
             "_handle_copy"),
            (re.compile(r"\brename\s+(?:file\s+)?[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?\s+(?:to|as|ko)\s+[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"”]?$", re.I),
             "_handle_rename"),

            # --- create folder / file ---
            (re.compile(r"\b(create|make|banao|banaiye|create karo|bana kar do)\b"
                        r"|(बनाओ|बनाईये|क्रिएट करो)", re.I),
             "_handle_create"),

            # --- search files ---
            (re.compile(r"\b(find|search|search for|look for|dhoondo|ढूंढो|खोजो)\b", re.I),
             "_handle_search"),

            # --- close app ---
            (re.compile(r"\b(close|close karo|band karo|बंद करो|बंद कर)\s+(?:the\s+)?([\w\u0900-\u097F\u0300-\u036F\- .]+)$"
                        r"|(.+?)\s+(band karo|close karo|बंद करो|बंद कर)$", re.I),
             "_handle_close_app"),

            # --- open folder / known location ---
            (re.compile(r"\b(open|show|kholo|khol|खोलो|खोल)\s+(?:the\s+|my\s+)?(desktop|downloads?|documents?|pictures|music|videos|my computer|this pc|home)", re.I),
             "_handle_open_folder"),

            # --- open website ---
            (re.compile(r"\b(open|start|go to|visit|kholo|khol|खोलो)\s+(?:the\s+|website\s+)?([\w.\-]+(?:\.(?:com|in|org|net|io|co|dev|me|xyz|ai))\b|youtube|google|gmail|github|stackoverflow|reddit|wikipedia|twitter|instagram|facebook|whatsapp|netflix|spotify|amazon|यूट्यूब|गूगल|जीमेल)", re.I),
             "_handle_open_site"),

            # --- open application (generic, EN + Hinglish + Devanagari) ---
            (re.compile(r"^(open|start|launch|open up|kholo|खोलो|चलाओ)\s+([\w\u0900-\u097F\u0300-\u036F\- .]+)$", re.I),
             "_handle_open_app"),
            (re.compile(r"^([\w\u0900-\u097F\u0300-\u036F\- .]+)\s+(kholo|khol|open karo|karo|खोलो|चलाओ)$", re.I),
             "_handle_open_app"),

            # --- type / press key / mouse click ---
            (re.compile(r"^\s*(type|type out|typewrite|likho|लिखो)\s*(?:text\s+|out\s+)?[\"“]?(.+?)[\"”]?$", re.I),
             "_handle_type"),
            (re.compile(r"^\s*(press|press key|press keys|dabao|दबाओ)\s+([\w +\-]+)$", re.I),
             "_handle_press_key"),
            (re.compile(r"^\s*(double\s+click|click\s+twice)\s*(?:at\s*)?(\d+)?(?:\s*[, ]\s*(\d+))?$", re.I),
             "_handle_mouse"),
            (re.compile(r"^\s*click\s*(?:at\s*)?(\d+)?(?:\s*[, ]\s*(\d+))?$", re.I),
             "_handle_mouse"),
        ]

    # ------------------------------------------------------------------ flow
    def process(self, user_input: str) -> Tuple[str, str]:
        if not user_input or not user_input.strip():
            return ("I didn't catch that. Could you repeat?", "speak")

        text = user_input.strip()
        log.info("Brain processing: %s", text)
        self.last_user_lang = detect_lang(text)
        self.conversation_history.append({
            "role": "user", "text": text,
            "timestamp": datetime.now().isoformat(),
        })

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

        response = self._handle_unknown(text)
        return self._finish_and_return((response, "speak"), text)

    def _log_response(self, response: str, action: str, text: str = ""):
        self.conversation_history.append({
            "role": "nova", "text": response,
            "timestamp": datetime.now().isoformat(),
        })
        log.info("Response: %s (action=%s)%s", response, action,
                 f" for: {text}" if text else "")

    def _finish_and_return(self, result: Tuple[str, str], text: str) -> Tuple[str, str]:
        # Natural success prefix in the user's language (only after a
        # verified, successfully executed action).
        response, action = result
        if action == "execute" and self.last_action_ok:
            lang = getattr(self, "last_user_lang", "en")
            if lang == "hi":
                response = f"ज़रूर, {response}"
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

    def _handle_high_risk_refusal(self, text: str) -> Tuple[str, str]:
        return (
            "I won't do that — it's a high-risk operation and NOVA never "
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
        m = re.search(r"(open|start|launch)\s+(.+?)\s+(and|aur|और)\s+create", text, re.I)
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
        m = re.match(r"^(?:open|start|launch|open up|kholo|खोलो|चलाओ)\s+(.+)$", low, re.I)
        if m:
            return self._clean_name(m.group(1))
        m = re.match(r"^(.+?)\s+(?:kholo|khol|open karo|karo|खोलो|चलाओ)$", low, re.I)
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
        m = re.search(r"(?:open|start|go to|visit|kholo|khol|खोलो)\s+(?:the\s+|website\s+)?([\w.\-]+\.[a-z]{2,}|youtube|google|gmail|github|stackoverflow|reddit|wikipedia|twitter|instagram|facebook|whatsapp|netflix|spotify|amazon|यूट्यूब|गूगल|जीमेल)", text, re.I)
        return (m.group(1) if m else None)

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
        if re.search(r"(?<!\S)(?:unmute|aawaz chalu|आवाज़ चालू)(?=\s|$)", low):
            return (None, None, False)
        if re.search(r"\bmute\b|(?<!\S)आवाज़ बंद(?=\s|$)", low):
            return (None, None, True)
        number = self._extract_number(text)
        kam = bool(re.search(r"\b(kam|kum|ghata|decrease|dheema|slow)\b|(?<!\S)(कम|घटाओ|धीमा)(?=\s|$)", low))
        up = bool(re.search(r"\b(up|zyada|badhao|increase|tez|high)\b|(?<!\S)(बढ़ाओ|ज़्यादा)(?=\s|$)", low))
        if number is not None and up and kam:
            return ("set", number, None)
        if number is not None:
            if kam and re.search(r"\b(thoda|zara|little)\b|(?<!\S)थोड़ा(?=\s|$)", low):
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
        m = re.search(r"(?:install|download and install)\s+(?:software|app|application|program|the\s+)?[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"”]?\s*(?:please)?$", text, re.I)
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
        ask = f"You asked me to delete {target}. That needs your confirmation — say yes to confirm, or say cancel."
        return self._stage_confirmation(plan, ask)

    def _high_risk_blocked(self) -> Tuple[str, str]:
        self.last_action_ok = False
        return ("I won't delete that — it's in a protected system area, which is a high-risk action.", "speak")

    def _extract_target(self, text: str) -> Optional[str]:
        m = re.search(r"(?:delete|remove|erase|delete kar)\s+(?:the\s+|this\s+)?(?:file|folder)?\s*[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?\s*(please)?$", text, re.I)
        return (m.group(1).strip() if m else None)

    def _handle_move(self, text: str) -> Tuple[str, str]:
        m = re.match(r"move\s+(?:file\s+)?[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?\s+(?:to|ko|mein|में)\s+[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?$", text, re.I)
        if not m:
            return self._fail("I couldn't work out what to move where.")
        src, dst = m.group(1).strip(), m.group(2).strip()
        steps = [ActionStep("move_file", {"source": src, "destination": dst},
                            label=f"Move {src}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_copy(self, text: str) -> Tuple[str, str]:
        m = re.match(r"copy\s+(?:file\s+)?[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?\s+(?:to|ko|mein|में)\s+[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?$", text, re.I)
        if not m:
            return self._fail("I couldn't work out what to copy where.")
        src, dst = m.group(1).strip(), m.group(2).strip()
        steps = [ActionStep("copy_file", {"source": src, "destination": dst},
                            label=f"Copy {src}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_rename(self, text: str) -> Tuple[str, str]:
        m = re.match(r"rename\s+(?:file\s+)?[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .:\\\\]+?)[\"”]?\s+(?:to|as|ko)\s+[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"”]?$", text, re.I)
        if not m:
            return self._fail("I couldn't work out what to rename.")
        src, new = m.group(1).strip(), m.group(2).strip()
        steps = [ActionStep("rename_file", {"source": src, "new_name": new},
                            label=f"Rename {src}", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_create(self, text: str) -> Tuple[str, str]:
        low = text.lower()
        is_folder = bool(re.search(r"\b(folder|फोल्डर|directory)\b", low))
        is_file = bool(re.search(r"\b(file|फाइल|document)\b", low))
        if not (is_folder or is_file):
            return self._fail("I could create a folder or a file — which one did you mean?")
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
        m = re.search(r"(?:mein|main|in|में)\s+[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"”]?\s*(?:folder|file|फोल्डर|फाइल)", low, re.I)
        if m:
            return self._clean_name(m.group(1))
        # trailing-word form: "create file expenses" -> expenses
        m = re.search(r"(?:create|make|banao)\s+(?:a\s+|an\s+|the\s+)?(?:folder|file|फोल्डर|फाइल)\s+(?:named\s+|naam\s+|का\s+)?[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"”]?$", low, re.I)
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
        m = re.search(r"(?:find|search|search for|look for|dhoondo|ढूंढो|खोजो)\s+(?:for\s+|files?\s+(?:named|called|naam)\s+)?[\"“]?([\w\u0900-\u097F\u0300-\u036F\- .]+?)[\"”]?\s*(?:in|mein|में|on)\s+([\w\u0900-\u097F\u0300-\u036F\- .]+)?$", low, re.I)
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
        m = re.match(r"([\w\u0900-\u097F\u0300-\u036F\- .]+)\s+(?:band karo|close karo|बंद करो|बंद कर)$", text, re.I)
        if m:
            return self._clean_name(m.group(1))
        return None

    def _handle_type(self, text: str) -> Tuple[str, str]:
        m = re.match(r"^\s*(?:type|type out|typewrite|likho|लिखो)\s*(?:text\s+|out\s+)?[\"“]?(.+?)[\"”]?$", text, re.I)
        if not m or not m.group(1).strip():
            return self._fail("I couldn't tell what to type.")
        steps = [ActionStep("type_text", {"text": m.group(1)},
                            label="Type text", risk=RiskLevel.SAFE)]
        return self._finish_tool(steps, text)

    def _handle_press_key(self, text: str) -> Tuple[str, str]:
        m = re.match(r"^\s*(?:press|press key|press keys|dabao|दबाओ)\s+([\w +\-]+)$", text, re.I)
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