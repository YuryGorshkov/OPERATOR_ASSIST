import unittest

from operator_assist_runtime.latency_metrics import (
    RecognitionLatencyTracker,
    calculate_recognition_latency,
)


class RecognitionLatencyTests(unittest.TestCase):
    def test_breakdown_includes_detected_audio_tail(self):
        sample = calculate_recognition_latency(
            captured_at=10.0,
            dequeued_at=10.1,
            recognized_at=11.0,
            displayed_at=11.12,
            inference_seconds=0.85,
            audio_tail_seconds=0.62,
        )

        self.assertAlmostEqual(0.1, sample.queue_seconds)
        self.assertAlmostEqual(0.9, sample.processing_seconds)
        self.assertAlmostEqual(0.12, sample.ui_dispatch_seconds)
        self.assertAlmostEqual(1.12, sample.trigger_to_ui_seconds)
        self.assertAlmostEqual(1.74, sample.speech_end_to_ui_seconds)
        self.assertAlmostEqual(0.85, sample.inference_seconds)

    def test_invalid_timestamp_order_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "monotonic"):
            calculate_recognition_latency(
                captured_at=10.0,
                dequeued_at=9.9,
                recognized_at=11.0,
                displayed_at=11.1,
            )

    def test_tracker_reports_nearest_rank_percentiles(self):
        tracker = RecognitionLatencyTracker()
        summary = None
        for delay in (1.0, 2.0, 3.0, 4.0, 10.0):
            sample = calculate_recognition_latency(
                captured_at=0.0,
                dequeued_at=0.0,
                recognized_at=delay,
                displayed_at=delay,
            )
            summary = tracker.record("speaker", "final", sample)

        self.assertEqual(5, summary["count"])
        self.assertEqual(4.0, summary["mean_seconds"])
        self.assertEqual(3.0, summary["p50_seconds"])
        self.assertEqual(10.0, summary["p95_seconds"])
        self.assertEqual(10.0, summary["max_seconds"])


if __name__ == "__main__":
    unittest.main()
