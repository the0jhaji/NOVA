"""Tests for the voice provider architecture (no audio device / no network).

Only pure mapping logic + the silent null provider are exercised.
"""

import unittest

from voice.providers import VoiceProvider
from voice.providers.edge import EdgeVoiceProvider, NullVoiceProvider


class VoiceVoiceMappingTests(unittest.TestCase):
    def setUp(self):
        self.provider = EdgeVoiceProvider()

    def test_edge_blueprint_voices(self):
        # Indian female neural voices NOVA defaults to
        self.assertEqual(self.provider._pick_voice("", "hi"),
                         "hi-IN-SwaraNeural")
        self.assertEqual(self.provider._pick_voice("", "hinglish"),
                         "hi-IN-SwaraNeural")
        self.assertEqual(self.provider._pick_voice("", "en"),
                         "en-IN-NeerjaNeural")

    def test_auto_selects_hindi_for_devanagari(self):
        self.assertEqual(self.provider._pick_voice("क्रोम खोलो", "auto"), "hi-IN-SwaraNeural")
        # Hinglish text also goes to the bilingual Hindi voice
        self.assertEqual(self.provider._pick_voice("Chrome kholo", "auto"), "hi-IN-SwaraNeural")

    def test_auto_selects_english_for_english(self):
        self.assertEqual(self.provider._pick_voice("Open Chrome", "auto"),
                         "en-IN-NeerjaNeural")

    def test_custom_voice_falls_back_gracefully(self):
        p = EdgeVoiceProvider(voice="en-US-AvaNeural")
        self.assertNotIn(p.voice, (p._pick_voice("", "hi")))
        self.assertEqual(p._pick_voice("", "hi"), "hi-IN-SwaraNeural")


class NullVoiceTests(unittest.TestCase):
    def test_is_a_provider(self):
        p = NullVoiceProvider()
        self.assertIsInstance(p, VoiceProvider)

    def test_speak_does_nothing(self):
        # must never raise, even with audio disabled
        NullVoiceProvider().speak("hello", lang="auto")

    def test_volume_speed_are_noops(self):
        NullVoiceProvider().apply(50, -10)


class ProviderContractTests(unittest.TestCase):
    def test_provider_array_interface(self):
        for p in (EdgeVoiceProvider(), NullVoiceProvider()):
            self.assertHasAttr(p, "speak")
            self.assertHasAttr(p, "stop")

    def assertHasAttr(self, obj, name):
        self.assertTrue(hasattr(obj, name), f"missing {name}")


if __name__ == "__main__":
    unittest.main()