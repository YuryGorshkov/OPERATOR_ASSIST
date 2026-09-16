import unittest
import logging
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy as np

from operator_assist_runtime import recognition_engines


class RecognitionEnginePlanTests(unittest.TestCase):
    @unittest.skipUnless(recognition_engines.os.name == "nt", "Windows DLL loading test")
    def test_prepare_cuda_runtime_uses_system_dll_search_as_fallback(self):
        original_candidates = recognition_engines._candidate_cublas_bin_dirs
        original_win_dll = recognition_engines.ctypes.WinDLL
        loaded = []

        try:
            recognition_engines._candidate_cublas_bin_dirs = lambda: []
            recognition_engines.ctypes.WinDLL = lambda dll_name: loaded.append(dll_name)

            ready, _details = recognition_engines.prepare_cuda_runtime()

            self.assertTrue(ready)
            self.assertEqual(["cublasLt64_12.dll", "cublas64_12.dll"], loaded)
        finally:
            recognition_engines._candidate_cublas_bin_dirs = original_candidates
            recognition_engines.ctypes.WinDLL = original_win_dll

    def test_precise_engine_attempt_plan_prefers_cuda_then_fallbacks_to_cpu(self):
        original_device = recognition_engines.preferred_precise_device
        original_supported = recognition_engines.supported_precise_compute_types
        try:
            recognition_engines.preferred_precise_device = lambda: "cuda"
            recognition_engines.supported_precise_compute_types = lambda device: (
                {"int8", "int8_float32", "float32"} if device == "cuda" else {"int8", "float32"}
            )

            plan = recognition_engines.precise_engine_attempt_plan()

            self.assertEqual(
                [
                    ("cuda", "int8"),
                    ("cuda", "int8_float32"),
                    ("cuda", "float32"),
                    ("cpu", "int8"),
                    ("cpu", "float32"),
                ],
                plan,
            )
        finally:
            recognition_engines.preferred_precise_device = original_device
            recognition_engines.supported_precise_compute_types = original_supported

    def test_precise_engine_attempt_plan_for_cpu_keeps_two_safe_modes(self):
        original_device = recognition_engines.preferred_precise_device
        original_supported = recognition_engines.supported_precise_compute_types
        try:
            recognition_engines.preferred_precise_device = lambda: "cpu"
            recognition_engines.supported_precise_compute_types = lambda _device: {"int8", "float32"}

            plan = recognition_engines.precise_engine_attempt_plan()

            self.assertEqual([("cpu", "int8"), ("cpu", "float32")], plan)
        finally:
            recognition_engines.preferred_precise_device = original_device
            recognition_engines.supported_precise_compute_types = original_supported

    def test_cpu_preference_never_schedules_cuda(self):
        original_device = recognition_engines.preferred_precise_device
        original_supported = recognition_engines.supported_precise_compute_types
        try:
            recognition_engines.preferred_precise_device = lambda: "cuda"
            recognition_engines.supported_precise_compute_types = lambda _device: {"int8", "float32"}

            plan = recognition_engines.precise_engine_attempt_plan(
                recognition_engines.PRECISE_DEVICE_CPU
            )

            self.assertEqual([("cpu", "int8"), ("cpu", "float32")], plan)
        finally:
            recognition_engines.preferred_precise_device = original_device
            recognition_engines.supported_precise_compute_types = original_supported

    def test_gpu_preference_keeps_cpu_as_a_safe_fallback(self):
        original_device = recognition_engines.preferred_precise_device
        original_supported = recognition_engines.supported_precise_compute_types
        try:
            recognition_engines.preferred_precise_device = lambda: "cuda"
            recognition_engines.supported_precise_compute_types = lambda device: (
                {"float16"} if device == "cuda" else {"int8"}
            )

            plan = recognition_engines.precise_engine_attempt_plan(
                recognition_engines.PRECISE_DEVICE_GPU
            )

            self.assertEqual([("cuda", "float16"), ("cpu", "int8")], plan)
        finally:
            recognition_engines.preferred_precise_device = original_device
            recognition_engines.supported_precise_compute_types = original_supported

    def test_unknown_device_preference_is_rejected(self):
        with self.assertRaises(ValueError):
            recognition_engines.precise_engine_attempt_plan("quantum")

    def test_precise_engine_loader_reports_attempt_progress(self):
        original_available = recognition_engines.precise_engine_available
        original_plan = recognition_engines.precise_engine_attempt_plan
        original_model = recognition_engines.WhisperModel
        progress = []

        class FakeWhisperModel:
            def __init__(self, model_name, **kwargs):
                self.model_name = model_name
                self.kwargs = kwargs

        try:
            recognition_engines.precise_engine_available = lambda: True
            recognition_engines.precise_engine_attempt_plan = lambda _preference=None: [("cpu", "int8")]
            recognition_engines.WhisperModel = FakeWhisperModel
            with TemporaryDirectory() as models_dir:
                bundle = recognition_engines.load_precise_engine_bundle(
                    models_dir,
                    logger=logging.getLogger("test.precise-loader"),
                    progress_callback=lambda *args: progress.append(args),
                )

            self.assertEqual("cpu", bundle.device)
            self.assertEqual("int8", bundle.compute_type)
            self.assertEqual(
                [(recognition_engines.DEFAULT_PRECISE_MODEL_NAME, "cpu", "int8", 1, 1)],
                progress,
            )
        finally:
            recognition_engines.precise_engine_available = original_available
            recognition_engines.precise_engine_attempt_plan = original_plan
            recognition_engines.WhisperModel = original_model

    def test_precise_buffer_reuses_previous_text_as_context(self):
        transcribe_calls = []
        returned_texts = iter(("Первая длинная фраза.", "Вторая фраза."))

        class FakeModel:
            def transcribe(self, _audio, **kwargs):
                transcribe_calls.append(kwargs)
                segment = SimpleNamespace(text=next(returned_texts))
                return iter((segment,)), SimpleNamespace()

        engine = recognition_engines.FasterWhisperBufferedEngine(
            SimpleNamespace(model=FakeModel()),
            text_postprocessor=lambda text, **_kwargs: text,
            sample_rate=10,
            flush_after_seconds=1.0,
            min_segment_seconds=0.1,
        )
        chunk = np.ones(10, dtype=np.int16).tobytes()

        first_updates = engine.consume_chunk(chunk)
        second_updates = engine.consume_chunk(chunk)

        self.assertEqual("Первая длинная фраза.", first_updates[0].text)
        self.assertEqual("Вторая фраза.", second_updates[0].text)
        self.assertIsNone(transcribe_calls[0]["initial_prompt"])
        self.assertEqual("Первая длинная фраза.", transcribe_calls[1]["initial_prompt"])
        self.assertTrue(transcribe_calls[0]["condition_on_previous_text"])


if __name__ == "__main__":
    unittest.main()
