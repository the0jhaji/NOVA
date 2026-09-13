"""
NOVA Voice Assistant - Automation Engine
Gates risk, invokes tools, assembles verified results.

The brain builds an ActionPlan; the engine either refuses it (risk too high or
user hasn't confirmed yet) or runs each step, logging and verifying outcomes.
"""

import os
from typing import Callable, Optional

from utils.logger import log
from config import config
from automation.safety import RiskLevel, classify_step
from automation.result import (
    ToolResult, ActionStep, ActionPlan, PlanResult,
)
from automation.tools import build_registry


class AutomationEngine:
    """
    Central executor used by NovaAgent. The brain passes a fully-formed
    ActionPlan (each step already carries its risk rating); the engine
    decides whether the plan can proceed.

    Confirmation flow:
      risk == CONFIRMATION_REQUIRED and `approved` is False
          → returns a PlanResult with `blocked = True`.
      The brain then asks the user and calls execute_plan again with
      approved = True once the user says yes.

    High-risk flow:
      risk >= HIGH_RISK and AUTOMATION_ALLOW_HIGH_RISK is False
          → always returns `blocked = True`.
    """

    def __init__(self, registry: Optional[dict[str, Callable]] = None):
        self._registry = registry or build_registry()

    # ------------------------------------------------------------------
    # Public helpers (also handy for tests)
    # ------------------------------------------------------------------

    def register_tool(self, name: str, fn: Callable[[dict], ToolResult]) -> None:
        self._registry[name] = fn

    def has_tool(self, name: str) -> bool:
        return name in self._registry

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_plan(
        self,
        plan: ActionPlan,
        approved: bool = False,
        on_step: Optional[Callable[[int, int, str], None]] = None,
    ) -> PlanResult:
        total = len(plan.steps)
        if total == 0:
            return PlanResult()

        result = PlanResult()
        for idx, step in enumerate(plan.steps, 1):
            if on_step:
                try:
                    on_step(idx, total, step.describe())
                except Exception:
                    pass

            # --- risk gate ---
            if step.risk >= RiskLevel.HIGH_RISK:
                if getattr(config.automation, "allow_high_risk", False) and approved:
                    log.warning("HIGH_RISK step approved by config+user: tool=%s", step.tool)
                else:
                    msg = (
                        "That action is too risky for me to perform, even with your confirmation."
                        if approved else
                        "I won't do that automatically — it's a high-risk operation."
                    )
                    result.steps.append(ToolResult(
                        tool=step.tool, success=False, verified=False,
                        message=msg, details={"blocked_by": "risk_high"},
                    ))
                    result.all_ok = False
                    result.blocked = True
                    result.blocker_message = msg
                    continue

            if step.risk >= RiskLevel.CONFIRMATION_REQUIRED and not approved:
                msg = f"I'd need your confirmation before doing: {step.describe()}"
                result.steps.append(ToolResult(
                    tool=step.tool, success=False, verified=False,
                    message=msg, details={"blocked_by": "risk_confirmation"},
                ))
                result.all_ok = False
                result.blocked = True
                result.blocker_message = msg
                continue

            # --- invoke ---
            tr = self._invoke(step.tool, step.params)
            result.steps.append(tr)
            if not tr.ok:
                result.all_ok = False
                break

        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _invoke(self, tool_name: str, params: dict) -> ToolResult:
        params_with_tool = {"tool": tool_name, **(params or {})}
        runner = self._registry.get(tool_name)
        if runner is None:
            log.error("Unknown tool: %s", tool_name)
            return ToolResult(
                tool=tool_name, success=False, verified=False,
                message=f"I don't know how to run that tool.",
            )
        log.info("Engine execute: %s (%d params)", tool_name, len(params or {}))
        try:
            tr = runner(params_with_tool)
        except Exception as exc:
            log.error("Tool %s raised: %s", tool_name, exc)
            tr = ToolResult(
                tool=tool_name, success=False, verified=False,
                message=f"An internal error occurred.",
                details={"exception": str(exc)},
            )
        log.info(
            "Tool result: ok=%s verified=%s  msg=%s",
            tr.ok, tr.verified, tr.message,
        )
        return tr