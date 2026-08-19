import unittest

from operator_assist_runtime.audio_diagnostics import (
    NO_SIGNAL_GRACE_SEC,
    SIGNAL_LIVE_THRESHOLD,
    build_route_diagnostic_message,
    describe_signal_state,
)


class AudioDiagnosticsTests(unittest.TestCase):
    def test_describe_signal_state_maps_thresholds(self):
        self.assertEqual("тишина", describe_signal_state(0))
        self.assertEqual("слабый", describe_signal_state(SIGNAL_LIVE_THRESHOLD))
        self.assertEqual("есть", describe_signal_state(30))
        self.assertEqual("сильный", describe_signal_state(80))

    def test_missing_both_channels_requests_selection(self):
        message = build_route_diagnostic_message(
            workers_active=False,
            mic_mode_label="физический вход",
            speaker_mode_label="loopback",
            mic_selected=False,
            speaker_selected=False,
        )

        self.assertIn("выберите микрофон оператора", message.lower())
        self.assertIn("источник собеседника", message.lower())

    def test_running_without_speaker_signal_gets_targeted_hint(self):
        message = build_route_diagnostic_message(
            workers_active=True,
            mic_mode_label="физический вход",
            speaker_mode_label="loopback",
            mic_selected=True,
            speaker_selected=True,
            mic_has_live_signal=True,
            speaker_has_live_signal=False,
            seconds_since_start=NO_SIGNAL_GRACE_SEC + 0.5,
        )

        self.assertIn("канал собеседника", message.lower())
        self.assertIn("stereo mix", message.lower())

    def test_running_with_both_live_signals_confirms_health(self):
        message = build_route_diagnostic_message(
            workers_active=True,
            mic_mode_label="физический вход",
            speaker_mode_label="loopback",
            mic_selected=True,
            speaker_selected=True,
            mic_has_live_signal=True,
            speaker_has_live_signal=True,
            seconds_since_start=1.0,
        )

        self.assertIn("оба канала", message.lower())
        self.assertIn("дублируются", message.lower())


if __name__ == "__main__":
    unittest.main()
