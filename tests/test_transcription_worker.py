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


if __name__ == "__main__":
    unittest.main()
