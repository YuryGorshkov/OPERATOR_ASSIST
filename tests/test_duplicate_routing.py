import unittest
from collections import deque
from unittest import mock

from operator_assist_runtime.base_runtime import OperatorAssistApp


class DuplicateRoutingTests(unittest.TestCase):
    def _make_app(self):
        app = OperatorAssistApp.__new__(OperatorAssistApp)
        app.pending_mic_finals = deque()
        app.committed_mic_finals = deque()
        app.mic_final_tag_serial = 0
        app.recent_mic_finals = deque()
        app.recent_speaker_finals = deque()
        app._capture_speaker_enabled = lambda: True
        app.my_text = object()
        app.appended_text = []
        app._append_text = lambda _widget, text: app.appended_text.append(text)
        return app

    def test_speaker_result_removes_an_earlier_pending_mic_duplicate(self):
        app = self._make_app()
        app._queue_pending_mic_final("проверяем распознавание системного звука", 100.0)

        match = app._discard_pending_mic_overlap(
            "проверяем распознавание системного звука",
            100.6,
        )

        self.assertEqual("exact", match[0])
        self.assertEqual([], list(app.pending_mic_finals))
        self.assertEqual([], app.appended_text)

    def test_audio_aligned_time_uses_capture_tail_instead_of_decoder_finish(self):
        app = self._make_app()

        match_time = app._recognition_match_time(
            112.0,
            {"captured_at": 108.0, "audio_tail_seconds": 7.5},
        )

        self.assertEqual(100.5, match_time)

    def test_delayed_speaker_result_removes_a_committed_mic_duplicate(self):
        app = self._make_app()
        app.committed_mic_finals.append(
            ("проверяем распознавание системного звука", 100.0, 101.0, "mic-tag")
        )

        with mock.patch.object(app, "_remove_mic_text_tag", return_value=True) as remove_tag:
            match = app._discard_committed_mic_overlap(
                "проверяем распознавание системного звука",
                100.8,
            )

        self.assertEqual("exact", match[0])
        self.assertEqual([], list(app.committed_mic_finals))
        remove_tag.assert_called_once_with("mic-tag", delete_text=True)

    def test_non_duplicate_mic_result_is_flushed_after_hold_window(self):
        app = self._make_app()
        app._queue_pending_mic_final("это отдельная реплика оператора", 100.0)

        app._flush_pending_mic_finals(force=True)

        self.assertEqual(["это отдельная реплика оператора "], app.appended_text)
        self.assertEqual([], list(app.pending_mic_finals))


if __name__ == "__main__":
    unittest.main()
