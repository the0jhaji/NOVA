"""
NOVA Voice Assistant - Automation Package
Controlled, tool-based Windows automation.

Pipeline: intent -> action planner -> tool selection -> tool execution
                                                   -> verification -> response

Design rules:
- NOVA never composes an unrestricted shell command. Every tool is a fixed,
  audited function with typed parameters.
- Every tool declares a risk level (SAFE / CONFIRMATION_REQUIRED / HIGH_RISK).
- High-risk actions must never execute silently.
- After an action, the tool verifies the outcome where technically possible
  and reports verified / best-effort / failed honestly.
"""

from automation.result import ToolResult, ActionStep, ActionPlan, PlanResult
from automation.safety import RiskLevel, classify_step, TOOL_BASE_RISK
from automation.engine import AutomationEngine

__all__ = [
    "ToolResult",
    "ActionStep",
    "ActionPlan",
    "PlanResult",
    "RiskLevel",
    "classify_step",
    "TOOL_BASE_RISK",
    "AutomationEngine",
]