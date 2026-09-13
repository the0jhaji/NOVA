"""
End-to-end file automation tests against a temporary sandbox directory.
Uses the real engine + real file tools; never touches the user's Desktop.
"""

import os
import shutil
import tempfile
import unittest

from automation import AutomationEngine, ActionStep, ActionPlan, RiskLevel
from automation.safety import classify_step


class FileAutomationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sandbox = tempfile.mkdtemp(prefix="nova_sandbox_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.sandbox, ignore_errors=True)

    def _run(self, steps, approved=False):
        engine = AutomationEngine()
        plan = ActionPlan(steps=steps)
        results = engine.execute_plan(plan, approved=approved)
        self.assertTrue(results.all_ok, results.all_ok)
        self.assertFalse(results.blocked)
        return results

    def test_create_folder(self):
        self._run([ActionStep("create_folder",
                              {"name": "Projects", "location": self.sandbox},
                              risk=RiskLevel.SAFE)])
        self.assertTrue(os.path.isdir(os.path.join(self.sandbox, "Projects")))

    def test_create_move_rename_copy_search_delete(self):
        path = self.sandbox
        engine = AutomationEngine()

        # create file
        plan = ActionPlan(steps=[ActionStep("create_file",
                                            {"name": "notes.txt",
                                             "location": path,
                                             "content": "hello nova"},
                                            risk=RiskLevel.SAFE)])
        self.assertTrue(engine.execute_plan(plan).all_ok)
        self.assertTrue(os.path.isfile(os.path.join(path, "notes.txt")))

        # copy into a subfolder
        sub = os.path.join(path, "backup")
        os.makedirs(sub, exist_ok=True)
        plan = ActionPlan(steps=[ActionStep("copy_file",
                                            {"source": os.path.join(path, "notes.txt"),
                                             "destination": sub},
                                            risk=RiskLevel.SAFE)])
        self.assertTrue(engine.execute_plan(plan).all_ok)
        self.assertTrue(os.path.isfile(os.path.join(sub, "notes.txt")))

        # rename
        plan = ActionPlan(steps=[ActionStep("rename_file",
                                            {"source": os.path.join(path, "notes.txt"),
                                             "new_name": "notes2.txt"},
                                            risk=RiskLevel.SAFE)])
        self.assertTrue(engine.execute_plan(plan).all_ok)
        self.assertTrue(os.path.isfile(os.path.join(path, "notes2.txt")))
        self.assertFalse(os.path.exists(os.path.join(path, "notes.txt")))

        # move
        plan = ActionPlan(steps=[ActionStep("move_file",
                                            {"source": os.path.join(path, "notes2.txt"),
                                             "destination": sub},
                                            risk=RiskLevel.SAFE)])
        self.assertTrue(engine.execute_plan(plan).all_ok)
        self.assertTrue(os.path.isfile(os.path.join(sub, "notes2.txt")))

        # search
        plan = ActionPlan(steps=[ActionStep("search_files",
                                            {"query": "notes2", "location": path},
                                            risk=RiskLevel.SAFE)])
        res = engine.execute_plan(plan)
        self.assertTrue(res.all_ok)
        found = res.results()[0].details.get("count")
        self.assertGreaterEqual(found, 1)

        # delete requires approval; then actually delete
        step = ActionStep("delete_file",
                          {"path": os.path.join(sub, "notes2.txt"), "is_dir": False},
                          risk=classify_step("delete_file", {"path": sub}))
        blocked = engine.execute_plan(ActionPlan(steps=[step]))
        self.assertTrue(blocked.blocked, "delete must be gated without approval")

        ok = engine.execute_plan(ActionPlan(steps=[step]), approved=True)
        self.assertTrue(ok.all_ok)
        self.assertFalse(os.path.exists(os.path.join(sub, "notes2.txt")))

    def test_high_risk_tool_never_runs(self):
        engine = AutomationEngine()
        step = ActionStep("format_disk", {}, risk=RiskLevel.HIGH_RISK)
        plan = ActionPlan(steps=[step])
        res = engine.execute_plan(plan, approved=False)
        self.assertTrue(res.blocked)
        self.assertFalse(res.all_ok)


if __name__ == "__main__":
    unittest.main()