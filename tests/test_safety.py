"""
Safety model tests: risk classification and the refusal layer.
"""

import unittest

from automation.safety import (
    RiskLevel,
    classify_step,
    classify,
    classify_text_high_risk,
    TOOL_BASE_RISK,
)


class SafetyTests(unittest.TestCase):

    def test_safe_tools_are_safe(self):
        for tool in ("open_application", "open_url", "open_folder",
                     "create_folder", "create_file", "take_screenshot",
                     "volume_control"):
            self.assertEqual(TOOL_BASE_RISK[tool], RiskLevel.SAFE)

    def test_confirmation_required_tools(self):
        self.assertEqual(TOOL_BASE_RISK["delete_file"], RiskLevel.CONFIRMATION_REQUIRED)
        self.assertEqual(TOOL_BASE_RISK["install_software"], RiskLevel.CONFIRMATION_REQUIRED)

    def test_one_delete_in_public_area_is_confirmation_required(self):
        risk = classify_step("delete_file", {"path": r"C:\Users\Me\Desktop\f.txt"})
        self.assertEqual(risk, RiskLevel.CONFIRMATION_REQUIRED)

    def test_delete_in_protected_root_escalates_to_high(self):
        risk = classify_step("delete_file", {"path": r"C:\Windows\System32\svchost.exe"})
        self.assertEqual(risk, RiskLevel.HIGH_RISK)

    def test_file_ops_in_program_files_are_high_risk(self):
        risk = classify_step("move_file", {"source": r"C:\Program Files\a.exe",
                                           "destination": r"C:\Users\Me"})
        self.assertEqual(risk, RiskLevel.HIGH_RISK)

    def test_bulk_delete_is_flagged(self):
        risk = classify_step("delete_file", {"path": r"C:\Users\Me\Desktop",
                                             "many": True})
        self.assertEqual(risk, RiskLevel.CONFIRMATION_REQUIRED)

    def test_high_risk_phrases(self):
        for phrase in ("format drive c", "wipe the disk", "change partitions",
                       "disable firewall", "delete system files"):
            self.assertTrue(classify_text_high_risk(phrase), phrase)

    def test_safe_phrases_are_not_flagged(self):
        for phrase in ("open chrome", "volume 50 percent", "take a screenshot",
                       "create a folder on desktop"):
            self.assertFalse(classify_text_high_risk(phrase), phrase)

    def test_text_risk_wins_over_tool(self):
        # Even an otherwise-safe tool never overrides a high-risk phrase.
        risk = classify("format my drive", "open_application", {"name": "x"})
        self.assertEqual(risk, RiskLevel.HIGH_RISK)


if __name__ == "__main__":
    unittest.main()