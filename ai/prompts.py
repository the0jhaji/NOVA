"""
NOVA Voice Assistant - Prompt templates & action schema
The schema the model fills in is deliberately tiny and strictly validated
downstream (tool allowlist + risk classification). Prompts enforce NOVA's
privacy behaviour and multilingual (EN/HI/Hinglish) replies.
"""

import json
import re
from typing import Optional

from automation.safety import TOOL_BASE_RISK

_ALLOWED_TOOLS = ", ".join(sorted(TOOL_BASE_RISK.keys()))

PLAN_SYSTEM = (
    "You are NOVA, a local AI assistant living on the user's own computer. "
    "You are NOT connected to the internet or to any cloud service. "
    "Your data never leaves this machine.\n\n"
    "Rules:\n"
    "- The user speaks English, Hindi, or Hinglish. Reply in the user's "
    "language (same as theirs: English stays English, Hindi stays Hindi, "
    "Hinglish stays Hinglish).\n"
    "- You drive the GUI with structured tool calls only. Never propose "
    "shell commands, PowerShell, or raw text to execute.\n"
    "- Never output secrets, credentials, API keys, .env contents, file "
    "contents, or anything personal.\n"
    "- If the request does not need a tool, respond conversationally with "
    "intent 'chat'.\n\n"
    f"Allowed tools: {_ALLOWED_TOOLS}\n\n"
    "Respond with ONLY one JSON object using this exact schema:\n"
    "[{'intent': 'chat', 'message': 'your reply'}]  OR\n"
    "[{'intent': 'tool', 'tool': 'tool_name', 'params': {...}, "
    "'message': 'short ack'}]\n"
    "No markdown fences. No text outside the JSON."
)

SCHEMA_SAMPLE = (
    '{"intent":"tool","tool":"open_application","params":{"name":"chrome"},'
    '"message":"Open Chrome"}'
)


def plan_messages(user_text: str) -> list:
    return [{"role": "user", "content": user_text}]


def _extract_json(raw: str):
    if not raw:
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()
    # locate the first complete {...} block
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    return None
    return None


def parse_action_json(raw: str) -> Optional[dict]:
    """Validate a model response into a structured action (or chat intent)."""
    obj = _extract_json(raw)
    if not isinstance(obj, dict):
        return None
    intent = str(obj.get("intent", "chat")).lower()
    if intent == "chat":
        return {"intent": "chat",
                "message": str(obj.get("message", ""))[:600]}
    if intent == "tool":
        tool = str(obj.get("tool", "")).strip()
        params = obj.get("params")
        if not isinstance(params, dict):
            params = {}
        params = {str(k): v for k, v in params.items()
                  if not str(k).startswith("_")}
        if tool not in TOOL_BASE_RISK:
            return None
        return {"intent": "tool", "tool": tool, "params": params,
                "message": str(obj.get("message", ""))[:300]}
    return None