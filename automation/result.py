"""
NOVA Voice Assistant - Automation Result & Plan Types
Typed contract between the brain, the action planner, and the executor.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from automation.safety import RiskLevel


@dataclass
class ToolResult:
    """Outcome of executing a single tool with verification metadata."""

    tool: str
    success: bool
    message: str
    verified: Optional[bool] = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.success


@dataclass
class ActionStep:
    """One planned tool invocation."""

    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    label: str = ""
    risk: RiskLevel = RiskLevel.SAFE

    def describe(self) -> str:
        return self.label or f"{self.tool}({self.params})"


@dataclass
class ActionPlan:
    """Ordered list of steps produced by the action planner."""

    steps: list[ActionStep] = field(default_factory=list)
    rationale: str = ""

    @property
    def risk_level(self) -> RiskLevel:
        if not self.steps:
            return RiskLevel.SAFE
        return max((s.risk for s in self.steps), default=RiskLevel.SAFE)

    def describes(self, tool: str) -> bool:
        return any(s.tool == tool for s in self.steps)


@dataclass
class PlanResult:
    """Result of executing a whole plan."""

    steps: list[ToolResult] = field(default_factory=list)
    all_ok: bool = True
    blocked: bool = False
    blocker_message: str = ""

    def results(self) -> list[ToolResult]:
        return self.steps