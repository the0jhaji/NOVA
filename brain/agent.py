"""
NOVA Voice Assistant - Brain / Agent
Processes user commands and generates responses.
Phase 1: Pattern-matching commands with simulated automation.
Architecture is ready for LLM integration in future phases.
"""

import re
import time
from datetime import datetime
from typing import Optional, Tuple

from utils.logger import log


class NovaAgent:
    """
    NOVA's brain — processes text commands and returns responses.
    
    Current capabilities:
    - Greetings
    - Time/date queries
    - App opening (simulated)
    - Basic info queries
    
    Future: LLM integration, memory, multi-step automation.
    """

    # Command patterns: (compiled_regex, handler_method_name)
    # Supports English, Hindi, and Hinglish patterns
    PATTERNS = []

    def __init__(self):
        self._build_patterns()
        self.conversation_history: list[dict] = []
        self._context: dict = {}

    def _build_patterns(self):
        """Define command patterns with multilingual support."""
        self.PATTERNS = [
            # Greetings (incl. Hindi/Devanagari)
            (
                re.compile(
                    r"\b(hello|hi|hey|namaste|namaskar)\b"
                    r"|(नमस्ते|नमस्कार|हैलो|हाय|नमो)",
                    re.I,
                ),
                "_handle_greeting",
            ),
            (
                re.compile(r"(hello\s*nova|hi\s*nova|hey\s*nova)", re.I),
                "_handle_greeting",
            ),

            # What can you do
            (
                re.compile(
                    r"what can you do|tum kya kar sakti|kya kar sakti ho"
                    r"|your capabilities|capabilities"
                    r"|(तुम क्या कर सकती हो|क्या कर सकती हो)",
                    re.I,
                ),
                "_handle_capabilities",
            ),

            # Time
            (
                re.compile(
                    r"(what time|time|kya time|samay|kitne baje|what's the time|vakt)"
                    r"|(समय क्या हुआ|कितने बजे|क्या समय|वक्त बताओ)",
                    re.I,
                ),
                "_handle_time",
            ),

            # Date
            (
                re.compile(
                    r"(what date|date|aaj ki date|today's date|what day)"
                    r"|(आज की तारीख)",
                    re.I,
                ),
                "_handle_date",
            ),

            # Open Chrome
            (
                re.compile(
                    r"(open\s+chrome|chrome\s+(kholo|khol|open)|chrome\s+open)"
                    r"|(क्रोम खोलो|क्रोम ओपन करो)",
                    re.I,
                ),
                "_handle_open_chrome",
            ),

            # Open Notepad
            (
                re.compile(
                    r"(open\s+notepad|notepad\s+(kholo|khol|open)|notepad\s+open|notepad)"
                    r"|(नोटपैड खोलो|नोटपैड ओपन करो)",
                    re.I,
                ),
                "_handle_open_notepad",
            ),

            # Open YouTube
            (
                re.compile(
                    r"(open\s+youtube|youtube\s+(kholo|khol|open)|youtube\s+open)"
                    r"|(यूट्यूब खोलो|यूट्यूब ओपन करो)",
                    re.I,
                ),
                "_handle_open_youtube",
            ),
            (re.compile(r"youtube\s+(open\s+)?karo", re.I), "_handle_open_youtube"),

            # Open Calculator
            (
                re.compile(
                    r"(open\s+calculator|calculator\s+(kholo|khol|open)|calculator)"
                    r"|(कैलकुलेटर खोलो)",
                    re.I,
                ),
                "_handle_open_calculator",
            ),

            # Who are you
            (
                re.compile(
                    r"(who are you|tum\s+kaun|kaun ho|your name|naam)"
                    r"|(तुम कौन हो|कौन हो)",
                    re.I,
                ),
                "_handle_identity",
            ),

            # Thank you
            (
                re.compile(
                    r"\b(thanks?|thank you|shukriya|dhanyavaad)\b"
                    r"|(शुक्रिया|धन्यवाद)",
                    re.I,
                ),
                "_handle_thanks",
            ),

            # Quit/exit
            (
                re.compile(
                    r"\b(quit|exit|bye|goodbye|band|close)\b"
                    r"|(अलविदा|बंद करो)",
                    re.I,
                ),
                "_handle_quit",
            ),
        ]

    def process(self, user_input: str) -> Tuple[str, str]:
        """
        Process user input and return (response_text, action_type).
        
        action_type can be:
        - "speak" : just speak the response
        - "execute" : an automation was triggered
        - "quit" : app should close
        """
        if not user_input or not user_input.strip():
            return ("I didn't catch that. Could you repeat?", "speak")

        text = user_input.strip()
        log.info("Brain processing: %s", text)

        # Record in conversation history
        self.conversation_history.append({
            "role": "user",
            "text": text,
            "timestamp": datetime.now().isoformat(),
        })

        # Match against patterns
        for pattern, handler_name in self.PATTERNS:
            if pattern.search(text):
                handler = getattr(self, handler_name)
                response, action = handler(text)
                self.conversation_history.append({
                    "role": "nova",
                    "text": response,
                    "timestamp": datetime.now().isoformat(),
                })
                log.info("Response: %s (action=%s)", response, action)
                return (response, action)

        # Default: unknown command
        response = self._handle_unknown(text)
        self.conversation_history.append({
            "role": "nova",
            "text": response,
            "timestamp": datetime.now().isoformat(),
        })
        return (response, "speak")

    def _handle_greeting(self, text: str) -> Tuple[str, str]:
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        return (f"{greeting}! I'm NOVA, your AI assistant. How can I help you?", "speak")

    def _handle_capabilities(self, text: str) -> Tuple[str, str]:
        return (
            "I can help you with opening applications like Chrome, Notepad, "
            "YouTube, and Calculator. I can tell you the time and date. "
            "More automation features are coming soon.",
            "speak",
        )

    def _handle_time(self, text: str) -> Tuple[str, str]:
        now = datetime.now().strftime("%I:%M %p")
        return (f"The current time is {now}.", "speak")

    def _handle_date(self, text: str) -> Tuple[str, str]:
        today = datetime.now().strftime("%A, %B %d, %Y")
        return (f"Today is {today}.", "speak")

    def _handle_open_chrome(self, text: str) -> Tuple[str, str]:
        log.info("ACTION: Opening Chrome (simulated)")
        return ("Opening Chrome for you.", "execute")

    def _handle_open_notepad(self, text: str) -> Tuple[str, str]:
        log.info("ACTION: Opening Notepad (simulated)")
        return ("Opening Notepad.", "execute")

    def _handle_open_youtube(self, text: str) -> Tuple[str, str]:
        log.info("ACTION: Opening YouTube (simulated)")
        return ("Opening YouTube in your browser.", "execute")

    def _handle_open_calculator(self, text: str) -> Tuple[str, str]:
        log.info("ACTION: Opening Calculator (simulated)")
        return ("Opening Calculator.", "execute")

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

    def _handle_unknown(self, text: str) -> str:
        return (
            f"I heard you say \"{text}\", but I'm not sure how to help with that yet. "
            "Try asking me to open an app, or ask for the time."
        )

    def get_history(self, limit: int = 50) -> list[dict]:
        """Get recent conversation history."""
        return self.conversation_history[-limit:]
