"""Tests for NOVA's language detection + response language routing."""

import unittest

from voice.language import (detect_lang, has_devanagari,
                            effective_language)


class LanguageDetectionTests(unittest.TestCase):
    def test_devanagari_script(self):
        self.assertTrue(has_devanagari("क्रोम खोलो"))
        self.assertFalse(has_devanagari("open chrome"))

    def test_detect_hindi_script(self):
        self.assertEqual(detect_lang("क्रोम खोलो"), "hi")
        self.assertEqual(detect_lang("फाइल बनाओ"), "hi")

    def test_detect_hinglish(self):
        self.assertEqual(detect_lang("Chrome kholo"), "hinglish")
        self.assertEqual(detect_lang("Volume thoda kam karo"), "hinglish")

    def test_detect_english(self):
        self.assertEqual(detect_lang("Open Chrome"), "en")
        self.assertEqual(detect_lang("What is the time?"), "en")

    def test_empty_is_english(self):
        self.assertEqual(detect_lang(""), "en")


class EffectiveLanguageTests(unittest.TestCase):
    def test_auto_follows_user(self):
        self.assertEqual(effective_language("hi", "AUTO", True), "hi")
        self.assertEqual(effective_language("hinglish", "AUTO", True), "hinglish")
        self.assertEqual(effective_language("en", "AUTO", True), "en")

    def test_auto_no_detect(self):
        self.assertEqual(effective_language("hi", "AUTO", False), "hi")
        self.assertEqual(effective_language("", "AUTO", False), "en")

    def test_fixed_modes_override(self):
        self.assertEqual(effective_language("hi", "ENGLISH"), "en")
        self.assertEqual(effective_language("en", "HINDI"), "hi")
        self.assertEqual(effective_language("hi", "HINGLISH"), "hinglish")

    def test_lowercase_mode_is_normalised(self):
        self.assertEqual(effective_language("hi", "auto"), "hi")
        self.assertEqual(effective_language("hi", "english"), "en")


if __name__ == "__main__":
    unittest.main()