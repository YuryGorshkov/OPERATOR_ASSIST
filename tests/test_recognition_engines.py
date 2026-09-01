import unittest
import logging
from tempfile import TemporaryDirectory

from operator_assist_runtime import recognition_engines


class RecognitionEnginePlanTests(unittest.TestCase):
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
            recognition_engines.precise_engine_attempt_plan = lambda: [("cpu", "int8")]
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


if __name__ == "__main__":
    unittest.main()
