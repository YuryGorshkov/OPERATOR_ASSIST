import unittest
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy as np

from operator_assist_runtime import recognition_engines


class RecognitionEnginePlanTests(unittest.TestCase):
    def test_cached_precise_model_path_resolves_complete_main_snapshot(self):
        with TemporaryDirectory() as root:
            cache_root = Path(root)
            repository = cache_root / "models--Systran--faster-whisper-large-v3"
            snapshot = repository / "snapshots" / "abc123"
            snapshot.mkdir(parents=True)
            (repository / "refs").mkdir()
            (repository / "refs" / "main").write_text("abc123\n", encoding="utf-8")
            for file_name in ("model.bin", "config.json", "tokenizer.json"):
                (snapshot / file_name).write_text("fixture", encoding="utf-8")

            resolved = recognition_engines.cached_precise_model_path(cache_root, "large-v3")

            self.assertEqual(snapshot, resolved)

    def test_cached_precise_model_path_rejects_incomplete_snapshot(self):
        with TemporaryDirectory() as root:
            cache_root = Path(root)
            snapshot = (
                cache_root
                / "models--Systran--faster-whisper-large-v3"
                / "snapshots"
                / "abc123"
            )
            snapshot.mkdir(parents=True)
            (snapshot / "config.json").write_text("{}", encoding="utf-8")

            self.assertIsNone(
                recognition_engines.cached_precise_model_path(cache_root, "large-v3")
            )

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
            self.assertEqual(recognition_engines.DEFAULT_PRECISE_MODEL_NAME, bundle.model.model_name)
            self.assertFalse(bundle.model.kwargs["local_files_only"])
            self.assertEqual(
                [(recognition_engines.DEFAULT_PRECISE_MODEL_NAME, "cpu", "int8", 1, 1)],
                progress,
            )
        finally:
            recognition_engines.precise_engine_available = original_available
            recognition_engines.precise_engine_attempt_plan = original_plan
            recognition_engines.WhisperModel = original_model

    def test_precise_engine_loader_opens_cached_snapshot_directly(self):
        original_available = recognition_engines.precise_engine_available
        original_plan = recognition_engines.precise_engine_attempt_plan
        original_model = recognition_engines.WhisperModel

        class FakeWhisperModel:
            def __init__(self, model_source, **kwargs):
                self.model_source = model_source
                self.kwargs = kwargs

        try:
            recognition_engines.precise_engine_available = lambda: True
            recognition_engines.precise_engine_attempt_plan = lambda _preference=None: [("cpu", "int8")]
            recognition_engines.WhisperModel = FakeWhisperModel
            with TemporaryDirectory() as models_dir:
                snapshot = (
                    Path(models_dir)
                    / "whisper-cache"
                    / "models--Systran--faster-whisper-large-v3"
                    / "snapshots"
                    / "abc123"
                )
                snapshot.mkdir(parents=True)
                for file_name in ("model.bin", "config.json", "tokenizer.json"):
                    (snapshot / file_name).write_text("fixture", encoding="utf-8")

                bundle = recognition_engines.load_precise_engine_bundle(
                    models_dir,
                    logger=logging.getLogger("test.precise-cached-loader"),
                )

            self.assertEqual(str(snapshot), bundle.model.model_source)
            self.assertTrue(bundle.model.kwargs["local_files_only"])
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
        self.assertIsNotNone(first_updates[0].inference_seconds)
        self.assertEqual("buffer", first_updates[0].trigger_reason)
        self.assertIsNone(transcribe_calls[0]["initial_prompt"])
        self.assertEqual("Первая длинная фраза.", transcribe_calls[1]["initial_prompt"])
        self.assertTrue(transcribe_calls[0]["condition_on_previous_text"])

    def test_precise_buffer_suppresses_single_character_tail(self):
        engine = self._make_precise_engine((SimpleNamespace(text="у"),))

        updates = engine.consume_chunk(np.ones(10, dtype=np.int16).tobytes())

        self.assertEqual([], updates)

    def test_vosk_finalize_keeps_optional_latency_metadata_empty(self):
        original_recognizer = recognition_engines.KaldiRecognizer

        class FakeRecognizer:
            def __init__(self, _model, _sample_rate):
                pass

            def SetWords(self, _enabled):
                pass

            def FinalResult(self):
                return '{"text": "готово"}'

        try:
            recognition_engines.KaldiRecognizer = FakeRecognizer
            engine = recognition_engines.VoskRecognitionEngine(
                object(),
                16000,
                text_postprocessor=lambda text, **_kwargs: text,
            )

            update = engine.finalize()[0]

            self.assertEqual("готово", update.text)
            self.assertIsNone(update.inference_seconds)
            self.assertEqual("", update.trigger_reason)
        finally:
            recognition_engines.KaldiRecognizer = original_recognizer

    def test_precise_buffer_preserves_short_meaningful_reply(self):
        engine = self._make_precise_engine((SimpleNamespace(text="да"),))

        updates = engine.consume_chunk(np.ones(10, dtype=np.int16).tobytes())

        self.assertEqual("да", updates[0].text)

    def _make_precise_engine(self, returned_segments, **kwargs):
        class FakeModel:
            def transcribe(self, _audio, **_transcribe_kwargs):
                return iter(returned_segments), SimpleNamespace()

        return recognition_engines.FasterWhisperBufferedEngine(
            SimpleNamespace(model=FakeModel()),
            text_postprocessor=lambda text, **_postprocess_kwargs: text,
            sample_rate=10,
            flush_after_seconds=1.0,
            min_segment_seconds=0.1,
            **kwargs,
        )

    def test_precise_buffer_rejects_high_no_speech_segment(self):
        engine = self._make_precise_engine(
            (SimpleNamespace(text="Субтитры сделал кто-то", no_speech_prob=0.84),)
        )

        updates = engine.consume_chunk(np.ones(10, dtype=np.int16).tobytes())

        self.assertEqual([], updates)
        self.assertEqual(1, engine.rejected_no_speech_segments)

    def test_precise_buffer_preserves_same_words_at_low_no_speech_probability(self):
        engine = self._make_precise_engine(
            (SimpleNamespace(text="Субтитры сделал кто-то", no_speech_prob=0.12),)
        )

        updates = engine.consume_chunk(np.ones(10, dtype=np.int16).tobytes())

        self.assertEqual("Субтитры сделал кто-то", updates[0].text)
        self.assertEqual(0, engine.rejected_no_speech_segments)

    def test_precise_buffer_suppresses_reproduced_metadata_hallucination(self):
        engine = self._make_precise_engine(
            (
                SimpleNamespace(
                    text="Субтитры создавал DimaTorzok",
                    no_speech_prob=0.01,
                ),
            )
        )

        updates = engine.consume_chunk(np.ones(10, dtype=np.int16).tobytes())

        self.assertEqual([], updates)
        self.assertEqual(1, engine.rejected_known_hallucinations)

    def test_precise_buffer_suppresses_reproduced_outro_hallucination(self):
        engine = self._make_precise_engine(
            (
                SimpleNamespace(
                    text="Продолжение следует...",
                    no_speech_prob=0.01,
                ),
            )
        )

        updates = engine.consume_chunk(np.ones(10, dtype=np.int16).tobytes())

        self.assertEqual([], updates)
        self.assertEqual(1, engine.rejected_known_hallucinations)

    def test_metadata_hallucination_filter_preserves_other_subtitle_phrases(self):
        segments = (
            SimpleNamespace(text="Субтитры создавал DimaTorzok"),
            SimpleNamespace(text="Субтитры создавал Дмитрий"),
        )

        accepted, rejected = recognition_engines.filter_known_metadata_hallucinations(
            segments
        )

        self.assertEqual([segments[1]], accepted)
        self.assertEqual([segments[0]], rejected)

    def test_metadata_hallucination_filter_handles_split_decoder_segments(self):
        segments = (
            SimpleNamespace(text="Субтитры создавал"),
            SimpleNamespace(text="DimaTorzok"),
        )

        accepted, rejected = recognition_engines.filter_known_metadata_hallucinations(
            segments
        )

        self.assertEqual([], accepted)
        self.assertEqual(list(segments), rejected)

    def test_precise_buffer_keeps_real_segment_from_mixed_decode(self):
        engine = self._make_precise_engine(
            (
                SimpleNamespace(text="Ложный текст", no_speech_prob=0.91),
                SimpleNamespace(text="Настоящая речь", no_speech_prob=0.08),
            )
        )

        updates = engine.consume_chunk(np.ones(10, dtype=np.int16).tobytes())

        self.assertEqual("Настоящая речь", updates[0].text)
        self.assertEqual(1, engine.rejected_no_speech_segments)

    def test_precise_buffer_rejects_segment_at_exact_threshold(self):
        engine = self._make_precise_engine(
            (SimpleNamespace(text="Граница", no_speech_prob=0.8),)
        )

        updates = engine.consume_chunk(np.ones(10, dtype=np.int16).tobytes())

        self.assertEqual([], updates)

    def test_precise_buffer_preserves_segment_without_probability_metadata(self):
        engine = self._make_precise_engine((SimpleNamespace(text="Совместимый сегмент"),))

        updates = engine.consume_chunk(np.ones(10, dtype=np.int16).tobytes())

        self.assertEqual("Совместимый сегмент", updates[0].text)

    def test_rejected_segment_is_not_used_as_next_prompt(self):
        transcribe_calls = []
        returned_segments = iter(
            (
                (SimpleNamespace(text="Ложный контекст", no_speech_prob=0.95),),
                (SimpleNamespace(text="Настоящая речь", no_speech_prob=0.1),),
            )
        )

        class FakeModel:
            def transcribe(self, _audio, **kwargs):
                transcribe_calls.append(kwargs)
                return iter(next(returned_segments)), SimpleNamespace()

        engine = recognition_engines.FasterWhisperBufferedEngine(
            SimpleNamespace(model=FakeModel()),
            text_postprocessor=lambda text, **_kwargs: text,
            sample_rate=10,
            flush_after_seconds=1.0,
            min_segment_seconds=0.1,
        )
        chunk = np.ones(10, dtype=np.int16).tobytes()

        self.assertEqual([], engine.consume_chunk(chunk))
        self.assertEqual("Настоящая речь", engine.consume_chunk(chunk)[0].text)
        self.assertIsNone(transcribe_calls[1]["initial_prompt"])

    def test_precise_buffer_rejects_invalid_no_speech_threshold(self):
        with self.assertRaises(ValueError):
            self._make_precise_engine((), no_speech_reject_threshold=0.0)


if __name__ == "__main__":
    unittest.main()
