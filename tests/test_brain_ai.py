"""
Brain + AI integration tests. Uses a pretend local provider so no model
is needed, and a stub automation engine so nothing really executes.
Core privacy invariants under test:
  - local AI handles unknown intents,
  - a failed local model NEVER forwards to cloud (specific message),
  - sensitive text is never sent to a cloud provider,
  - AI-proposed actions still pass risk classification / allowlist.
"""

import unittest

from ai.providers.base import AIProvider, AIUnavailable
from automation.result import PlanResult, ToolResult
from automation import AutomationEngine
from brain.agent import NovaAgent


class StubAI(AIProvider):
    name = "stub"
    kind = "local"

    def __init__(self, plan=None, exc=None, chat_text="hi"):
        self._plan = plan
        self._exc = exc
        self.chat_text = chat_text
        self.plan_called = False

    def available(self):
        return True

    def chat(self, text, system="", history=None, temperature=0.4):
        return self.chat_text

    def plan(self, text):
        self.plan_called = True
        if self._exc:
            raise self._exc
        return self._plan


class StubCloudAI(StubAI):
    kind = "cloud"


class StubEngine(AutomationEngine):
    def __init__(self):
        super().__init__()   # registry built, but execute_plan overridden
        self.ran = []

    def execute_plan(self, plan, approved=False):
        self.ran.append([(s.tool, s.params) for s in plan.steps])
        results = [ToolResult(tool=s.tool, success=True,
                              message=f"Done {s.tool}") for s in plan.steps]
        return PlanResult(steps=results, all_ok=True)


CHAT_PLAN = {"intent": "chat", "message": "That's a good question!"}
TOOL_PLAN = {"intent": "tool", "tool": "open_application",
             "params": {"name": "chrome"}, "message": "open"}


def make_agent(engine=None, initial_ai=None):
    engine = engine or StubEngine()
    agent = NovaAgent(automation=engine)
    agent.ai = initial_ai
    return agent, engine


class BrainAITests(unittest.TestCase):

    def test_chat_intent_returns_model_message(self):
        agent, _ = make_agent(initial_ai=StubAI(plan=CHAT_PLAN))
        response, action = agent.process("what is ai?")
        self.assertEqual(action, "speak")
        self.assertEqual(response, "That's a good question!")

    def test_tool_intent_runs_through_engine(self):
        engine = StubEngine()
        agent, _ = make_agent(engine=engine, initial_ai=StubAI(plan=TOOL_PLAN))
        response, action = agent.process("open chrome")
        self.assertEqual(action, "execute")
        self.assertTrue(agent.last_action_ok)
        self.assertEqual(engine.ran, [[("open_application", {"name": "chrome"})]])

    def test_unavailable_local_ai_never_forwards(self):
        agent, _ = make_agent(initial_ai=StubAI(exc=AIUnavailable("down")))
        response, action = agent.process("explain black holes")
        self.assertEqual(action, "speak")
        self.assertIn("haven't sent", response)
        self.assertIn("cloud", response.lower())

    def test_no_provider_falls_back_to_unknown(self):
        agent, _ = make_agent(initial_ai=None)
        response, action = agent.process("xyzzy plugh")
        self.assertEqual(action, "speak")
        self.assertIn("not sure how to help", response)

    def test_cloud_provider_refuses_sensitive_text(self):
        stub = StubCloudAI(plan=TOOL_PLAN)
        agent, _ = make_agent(initial_ai=stub)
        response, action = agent.process(
            "my api key is sk-abcdef1234567890abcdef1234567890")
        self.assertEqual(action, "speak")
        self.assertIn("won't send", response)
        self.assertFalse(stub.plan_called, "plan must not run on sensitive text")

    def test_cloud_provider_allows_benign_text(self):
        stub = StubCloudAI(plan=CHAT_PLAN)
        agent, _ = make_agent(initial_ai=stub)
        _, action = agent.process("what is the weather")
        self.assertEqual(action, "speak")
        self.assertTrue(stub.plan_called)

    def test_high_risk_ai_action_blocked(self):
        plan = {"intent": "tool",
                "tool": "delete_file",
                "params": {"path": r"C:\Windows\System32\svchost.exe"},
                "message": "del"}
        engine = StubEngine()
        agent, _ = make_agent(engine=engine, initial_ai=StubAI(plan=plan))
        response, action = agent.process("clean up my pc")
        self.assertEqual(action, "speak")
        self.assertIn("high-risk", response.lower())
        self.assertEqual(engine.ran, [])

    def test_invalid_tool_in_ai_proposal_ignored(self):
        plan = {"intent": "tool", "tool": "format_c_drive",
                "params": {}, "message": "nope"}
        agent, _ = make_agent(initial_ai=StubAI(plan=plan))
        response, action = agent.process("run the snapshot thingy")
        self.assertEqual(action, "speak")
        self.assertIn("not sure how to help", response)


if __name__ == "__main__":
    unittest.main()