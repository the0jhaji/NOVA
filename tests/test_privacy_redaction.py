"""
Privacy tests: secret redaction + sensitive-content classification.
Ensures logs, prompts and network statements never carry credentials.
"""

import unittest

from privacy.redactor import redact_secrets, looks_sensitive


class RedactionTests(unittest.TestCase):

    def test_openai_key_redacted(self):
        out = redact_secrets("key sk-1234567890abcdef1234567890abcdef")
        self.assertNotIn("sk-1234567890abcdef", out)
        self.assertIn("[REDACTED]", out)

    def test_aws_access_key_redacted(self):
        out = redact_secrets("AKIAIOSFODNN7EXAMPLE value")
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", out)

    def test_bearer_token_redacted(self):
        out = redact_secrets(
            "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")
        self.assertIn("[REDACTED]", out)

    def test_password_keyword_redacted(self):
        out = redact_secrets("password=donttell; user=me")
        self.assertNotIn("donttell", out)

    def test_env_sensitive_values_redacted(self):
        out = redact_secrets(
            "My token is MY_SECRET_VALUE_123",
            secret_values={"OPENAI_API_KEY": "MY_SECRET_VALUE_123"})
        self.assertNotIn("MY_SECRET_VALUE_123", out)

    def test_plain_text_survives(self):
        out = redact_secrets("open chrome please")
        self.assertEqual(out, "open chrome please")

    def test_looks_sensitive_positive(self):
        self.assertTrue(looks_sensitive("sk-abcdef1234567890ABCDEF1234567890"))
        self.assertTrue(looks_sensitive("password=hunter2 in here"))
        self.assertTrue(looks_sensitive("api key AKIAXXXXXXXXXXXXXXXX value"))

    def test_looks_sensitive_negative(self):
        self.assertFalse(looks_sensitive("open youtube"))
        self.assertFalse(looks_sensitive("what time is it"))


if __name__ == "__main__":
    unittest.main()