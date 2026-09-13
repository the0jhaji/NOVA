"""
NetworkManager tests: the fail-closed privacy firewall for outbound calls.
"""

import unittest

from privacy.network_manager import (
    NetworkManager, NetworkDecision, is_loopback,
)
from privacy.state import (
    privacy_state, NETWORK_LOCAL_ONLY, NETWORK_USER_APPROVED_CLOUD,
)


class LoopbackTests(unittest.TestCase):

    def test_localhost_is_loopback(self):
        self.assertTrue(is_loopback("http://localhost:11434/api/chat"))
        self.assertTrue(is_loopback("http://127.0.0.1:11434"))

    def test_remote_is_not_loopback(self):
        self.assertFalse(is_loopback("https://api.example.com/v1"))


def _reset_state():
    privacy_state.network_mode = NETWORK_LOCAL_ONLY


class NetworkManagerTests(unittest.TestCase):

    def setUp(self):
        _reset_state()
        self.nm = NetworkManager()

    def tearDown(self):
        # Never leave cloud state persisted in .env after tests run.
        privacy_state.disable_cloud()
        _reset_state()

    def test_local_is_allowed_in_local_mode(self):
        self.assertEqual(
            self.nm.request(url="http://localhost:11434", scope="ai"),
            NetworkDecision.ALLOWED_LOCAL)

    def test_cloud_refused_by_default(self):
        self.assertEqual(
            self.nm.request(url="https://api.example.com", scope="ai"),
            NetworkDecision.BLOCKED)

    def test_cloud_requires_enable_approve_and_mode(self):
        privacy_state.enable_cloud(True)
        self.assertEqual(self.nm.request_cloud("ai"),
                         NetworkDecision.ALLOWED_CLOUD)

    def test_cloud_blocked_when_enabled_but_not_approved(self):
        privacy_state.cloud_enabled = True
        privacy_state.cloud_approved = False
        privacy_state.network_mode = NETWORK_USER_APPROVED_CLOUD
        self.assertEqual(self.nm.request_cloud("ai"),
                         NetworkDecision.BLOCKED)

    def test_blocked_mode_blocks_everything(self):
        privacy_state.network_mode = "blocked"
        self.assertEqual(self.nm.request_cloud("ai"),
                         NetworkDecision.BLOCKED)

    def test_unknown_scope_blocked(self):
        privacy_state.enable_cloud(True)
        self.assertEqual(self.nm.request_cloud("surveillance"),
                         NetworkDecision.BLOCKED)

    def test_disabling_cloud_revokes(self):
        privacy_state.enable_cloud(True)
        self.nm.approve_scope("ai")
        privacy_state.disable_cloud()
        self.assertEqual(self.nm.request_cloud("ai"),
                         NetworkDecision.BLOCKED)


if __name__ == "__main__":
    unittest.main()