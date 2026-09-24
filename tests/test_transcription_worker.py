import queue
import threading
import unittest

from operator_assist_runtime.base_runtime import TranscriptionWorker


class TranscriptionWorkerQueueTests(unittest.TestCase):
    def _worker(self):
        worker = object.__new__(TranscriptionWorker)
        worker.label = "speaker"
        worker.stop_event = threading.Event()
        worker.audio_queue = queue.Queue(maxsize=4)
        worker.audio_preprocessor = None
        worker.audio_observer = None
        worker.chunk_count = 0
        worker.drop_count = 0
        worker.suppressed_chunk_count = 0
        worker.gap_marker_queued = False
        worker.last_audio_captured_at = None
        worker._emit_level = lambda _chunk: None
        return worker

    def test_captured_chunk_keeps_monotonic_timestamp_in_queue(self):
        worker = self._worker()

        worker._enqueue_captured_chunk(b"\x01\x00", 12.5)

        self.assertEqual((b"\x01\x00", 12.5), worker.audio_queue.get_nowait())
        self.assertEqual(12.5, worker.last_audio_captured_at)

    def test_suppressed_chunk_keeps_timestamp_on_gap_marker(self):
        worker = self._worker()
        worker.audio_preprocessor = type(
            "Suppressor",
            (),
            {"process_pcm16": staticmethod(lambda _chunk: b"")},
        )()

        worker._enqueue_captured_chunk(b"\x01\x00", 21.25)

        self.assertEqual((None, 21.25), worker.audio_queue.get_nowait())
        self.assertEqual(1, worker.suppressed_chunk_count)

    def test_audio_observer_receives_raw_chunk_and_capture_time(self):
        worker = self._worker()
        observed = []
        worker.audio_observer = lambda chunk, captured_at: observed.append((chunk, captured_at))

        worker._enqueue_captured_chunk(b"\x01\x00", 31.5)

        self.assertEqual([(b"\x01\x00", 31.5)], observed)

    def test_time_aware_preprocessor_receives_capture_time(self):
        worker = self._worker()
        calls = []
        worker.audio_preprocessor = type(
            "TimeAwareSuppressor",
            (),
            {"process_pcm16_at": staticmethod(lambda chunk, captured_at: calls.append((chunk, captured_at)) or chunk)},
        )()

        worker._enqueue_captured_chunk(b"\x02\x00", 41.25)

        self.assertEqual([(b"\x02\x00", 41.25)], calls)
        self.assertEqual((b"\x02\x00", 41.25), worker.audio_queue.get_nowait())


if __name__ == "__main__":
    unittest.main()
