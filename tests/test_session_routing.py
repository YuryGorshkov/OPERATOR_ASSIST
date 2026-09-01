import unittest

from operator_assist_runtime.session_routing import (
    CAPTURE_MODE_BOTH,
    CAPTURE_MODE_MIC_ONLY,
    CAPTURE_MODE_SPEAKER_ONLY,
    capture_mode_key_from_label,
    capture_mode_label,
    capture_mode_uses_mic,
    capture_mode_uses_speaker,
    select_best_signal_source,
)


class SessionRoutingTests(unittest.TestCase):
    def test_capture_modes_enable_only_the_requested_channels(self):
        self.assertTrue(capture_mode_uses_mic(CAPTURE_MODE_BOTH))
        self.assertTrue(capture_mode_uses_speaker(CAPTURE_MODE_BOTH))
        self.assertFalse(capture_mode_uses_mic(CAPTURE_MODE_SPEAKER_ONLY))
        self.assertTrue(capture_mode_uses_speaker(CAPTURE_MODE_SPEAKER_ONLY))
        self.assertTrue(capture_mode_uses_mic(CAPTURE_MODE_MIC_ONLY))
        self.assertFalse(capture_mode_uses_speaker(CAPTURE_MODE_MIC_ONLY))

    def test_capture_mode_labels_round_trip(self):
        for mode_key in (CAPTURE_MODE_BOTH, CAPTURE_MODE_SPEAKER_ONLY, CAPTURE_MODE_MIC_ONLY):
            self.assertEqual(mode_key, capture_mode_key_from_label(capture_mode_label(mode_key)))

    def test_signal_probe_selects_the_strongest_live_source(self):
        best = select_best_signal_source(
            [
                {"label": "WASAPI", "level_percent": 0, "error": ""},
                {"label": "Stereo Mix", "level_percent": 31, "error": ""},
                {"label": "Broken", "level_percent": 90, "error": "open failed"},
            ]
        )

        self.assertEqual("Stereo Mix", best["label"])

    def test_signal_probe_rejects_silence(self):
        best = select_best_signal_source(
            [
                {"label": "WASAPI", "level_percent": 0, "error": ""},
                {"label": "Stereo Mix", "level_percent": 7, "error": ""},
            ]
        )

        self.assertIsNone(best)


if __name__ == "__main__":
    unittest.main()
