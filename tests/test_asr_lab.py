import itertools
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

import numpy as np

from asr_lab.corpus import corpus_summary, load_manifest, read_pcm
from asr_lab.engine import ObservedModel, make_engine
from asr_lab.metrics import aggregate, edit_counts, score_terms, score_text, tokens
from asr_lab.preparation import convert_audio, export_training_pairs
from asr_lab.profiles import PROFILES
from operator_assist_runtime.pause_recognition import PauseAwareWhisperEngine
from operator_assist_runtime.recognition_engines import FasterWhisperBufferedEngine, PreciseEngineBundle


def write_wav(path, *, seconds=3, rate=16000, channels=1, tone=False):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        values = np.arange(int(seconds * rate))
        samples = (np.sin(values * (2 * np.pi * 440 / rate)) * 2000).astype(np.int16) if tone else np.zeros(len(values), dtype=np.int16)
        if channels != 1:
            samples = np.repeat(samples[:, None], channels, axis=1)
        audio.writeframes(samples.tobytes())


def write_manifest(root, rows):
    manifest = root / "corpus.jsonl"
    manifest.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    return manifest


def row(**changes):
    return {"id": "one", "audio": "audio.wav", "text": "correct words", "start": 0,
            "end": 1, "split": "dev", "book_id": "book01", "speaker_id": "actor01",
            "passage_id": "p01", "critical_terms": [], "license": "synthetic unit-test fixture",
            "verified": True, **changes}


def bundle(model):
    return PreciseEngineBundle(model, "fake", "cpu", "int8", Path("."))


class FakeModel:
    def __init__(self, *texts):
        self.texts = iter(texts)
        self.calls = []

    def transcribe(self, audio, **options):
        self.calls.append((len(audio), options))
        return iter((SimpleNamespace(text=next(self.texts)),)), SimpleNamespace()


class MetricsTests(unittest.TestCase):
    def test_normalization_does_not_hide_acronym_errors(self):
        self.assertEqual(["c++", "c#", "php", "sql"], tokens("C++, C#; PHP SQL"))
        self.assertGreater(score_text("PHP SQL", "\u043f\u0438 \u0448\u043f\u0438 \u044d\u0441\u043a\u0438\u0432\u0435\u043b\u044c")["wer"]["errors"], 0)

    def test_case_punctuation_and_yo_normalization(self):
        self.assertEqual(0, score_text("\u0415\u0451, \u043a\u043d\u0438\u0433\u0430!", "\u0435\u0435 \u043a\u043d\u0438\u0433\u0430")["wer"]["errors"])

    def test_all_edit_operations(self):
        counts = edit_counts("abc", "axc")
        self.assertEqual((1, 0, 0), (counts.substitutions, counts.deletions, counts.insertions))
        self.assertEqual(1, edit_counts("abc", "ac").deletions)
        self.assertEqual(1, edit_counts("ac", "abc").insertions)

    def test_silence_has_insertions_without_fake_zero_rate(self):
        score = score_text("", "invented words")["wer"]
        self.assertEqual(2, score["insertions"])
        self.assertIsNone(score["rate"])

    def test_corpus_rate_is_weighted_by_reference_length(self):
        scores = [score_text("a", "x"), score_text("a b c d e f g h i", "a b c d e f g h i")]
        self.assertAlmostEqual(0.1, aggregate(scores, "wer")["rate"])

    def test_critical_terms_are_token_bounded_and_extras_are_visible(self):
        scores = score_terms("SQL C++", "NoSQL SQL SQL C++ Marvel", ("SQL", "C++", "Laravel", "Marvel"))
        self.assertEqual((1, 1), (scores[0]["recognized"], scores[0]["extra"]))
        self.assertEqual(1, scores[1]["recognized"])
        self.assertEqual(0, scores[2]["recognized"])
        self.assertEqual(1, scores[3]["extra"])

    def test_dp_cost_matches_independent_edit_distance(self):
        strings = ["".join(items) for length in range(4) for items in itertools.product("ab", repeat=length)]
        for reference in strings:
            for hypothesis in strings:
                table = [[0] * (len(hypothesis) + 1) for _ in range(len(reference) + 1)]
                for i in range(len(reference) + 1):
                    table[i][0] = i
                for j in range(len(hypothesis) + 1):
                    table[0][j] = j
                for i in range(1, len(reference) + 1):
                    for j in range(1, len(hypothesis) + 1):
                        table[i][j] = min(table[i - 1][j] + 1, table[i][j - 1] + 1,
                                          table[i - 1][j - 1] + (reference[i - 1] != hypothesis[j - 1]))
                self.assertEqual(table[-1][-1], edit_counts(reference, hypothesis).errors)


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_wav(self.root / "audio.wav")

    def load(self, *rows):
        return load_manifest(write_manifest(self.root, rows))

    def test_verified_interval_loads_without_changing_files(self):
        before = (self.root / "audio.wav").read_bytes()
        sample = self.load(row(start=0.2, end=0.8))[0]
        self.assertEqual(19200, len(read_pcm(sample)))
        self.assertEqual(before, (self.root / "audio.wav").read_bytes())

    def test_reference_can_be_a_utf8_file(self):
        (self.root / "reference.txt").write_text("\u0422\u043e\u0447\u043d\u044b\u0439 \u0442\u0435\u043a\u0441\u0442", encoding="utf-8-sig")
        data = row(text_file="reference.txt")
        del data["text"]
        self.assertEqual("\u0422\u043e\u0447\u043d\u044b\u0439 \u0442\u0435\u043a\u0441\u0442", self.load(data)[0].text)

    def test_unverified_transcript_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "human-verified"):
            self.load(row(verified=False))

    def test_empty_transcript_is_allowed_for_silence(self):
        self.assertEqual("", self.load(row(text=""))[0].text)

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate sample"):
            self.load(row(), row())

    def test_missing_audio_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing audio"):
            self.load(row(audio="missing.wav"))

    def test_wrong_audio_format_is_rejected(self):
        write_wav(self.root / "stereo.wav", rate=48000, channels=2)
        with self.assertRaisesRegex(ValueError, "mono PCM16"):
            self.load(row(audio="stereo.wav"))

    def test_invalid_intervals_are_rejected(self):
        for changes in ({"start": -1}, {"end": 9}, {"start": 1, "end": 1}, {"end": float("nan")}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "interval"):
                self.load(row(**changes))

    def test_same_passage_with_different_actor_cannot_leak(self):
        write_wav(self.root / "other.wav", tone=True)
        with self.assertRaisesRegex(ValueError, "Same book passage"):
            self.load(row(split="train"), row(id="two", audio="other.wav", speaker_id="actor02", split="test"))

    def test_identical_audio_with_different_metadata_cannot_leak(self):
        (self.root / "copy.wav").write_bytes((self.root / "audio.wav").read_bytes())
        with self.assertRaisesRegex(ValueError, "Overlapping audio"):
            self.load(row(split="train"), row(id="two", audio="copy.wav", book_id="other", passage_id="other", split="test"))

    def test_adjacent_intervals_are_allowed_but_shared_voices_are_warned(self):
        samples = self.load(row(split="train"), row(id="two", passage_id="p02", start=1, end=2, split="test"))
        summary = corpus_summary(samples)
        self.assertEqual(1, summary["splits"]["train"]["samples"])
        self.assertEqual(2, len(summary["warnings"]))

    def test_missing_license_and_ambiguous_reference_are_rejected(self):
        for changes in ({"license": ""}, {"text_file": "anything.txt"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.load(row(**changes))

    def test_empty_manifest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no samples"):
            self.load()

    def test_export_keeps_splits_and_source_intact_without_training(self):
        samples = self.load(row(split="train"), row(id="two", passage_id="p02", start=1, end=2))
        source = (self.root / "audio.wav").read_bytes()
        report = export_training_pairs(samples, self.root / "export")
        self.assertFalse(report["training_started"])
        self.assertEqual(source, (self.root / "audio.wav").read_bytes())
        exported = json.loads((self.root / "export" / "train.jsonl").read_text())
        self.assertEqual("one", exported["id"])
        with wave.open(str(self.root / "export" / exported["audio"]), "rb") as audio:
            self.assertEqual(16000, audio.getnframes())
        with self.assertRaises(FileExistsError):
            export_training_pairs(samples, self.root / "export")

    def test_conversion_requires_permission_and_never_overwrites(self):
        with self.assertRaisesRegex(ValueError, "permission"):
            convert_audio(self.root / "audio.wav", self.root / "converted.wav")
        report = convert_audio(self.root / "audio.wav", self.root / "converted.wav", permission_confirmed=True)
        self.assertAlmostEqual(3.0, report["seconds"])
        expected = (self.root / "converted.wav").read_bytes()
        with self.assertRaises(FileExistsError):
            convert_audio(self.root / "audio.wav", self.root / "converted.wav", permission_confirmed=True)
        self.assertEqual(expected, (self.root / "converted.wav").read_bytes())

    def test_conversion_failure_cleans_only_its_new_output(self):
        invalid = self.root / "invalid.bin"
        invalid.write_bytes(b"not audio")
        target = self.root / "failed.wav"
        with self.assertRaises(Exception):
            convert_audio(invalid, target, permission_confirmed=True)
        self.assertFalse(target.exists())
        self.assertEqual(b"not audio", invalid.read_bytes())

    def test_failed_export_is_marked_instead_of_looking_complete(self):
        samples = self.load(row())
        with patch("asr_lab.preparation.read_pcm", side_effect=ValueError("changed audio")):
            with self.assertRaisesRegex(ValueError, "changed audio"):
                export_training_pairs(samples, self.root / "failed-export")
        status = json.loads((self.root / "failed-export" / "export.json").read_text(encoding="utf-8"))
        self.assertEqual("failed", status["status"])
        self.assertFalse(status["training_started"])


class EngineTests(unittest.TestCase):
    def test_baseline_preserves_the_fixed_window_control(self):
        model = FakeModel("recognized")
        engine, observed = make_engine(bundle(model), PROFILES["baseline"], text_postprocessor=lambda text, **_: text)
        self.assertIs(type(engine), FasterWhisperBufferedEngine)
        engine.consume_chunk(np.ones(96000, dtype=np.int16).tobytes())
        options = observed.calls[0]["options"]
        self.assertEqual("ru", options["language"])
        self.assertEqual(5, options["beam_size"])
        self.assertNotIn("hotwords", options)
        self.assertIsNone(options["initial_prompt"])

    def test_production_profile_uses_pause_aware_desktop_engine(self):
        engine, _observed = make_engine(
            bundle(FakeModel("recognized")),
            PROFILES["production_pause"],
            text_postprocessor=lambda text, **_: text,
        )

        self.assertIs(type(engine), PauseAwareWhisperEngine)
        self.assertFalse(PROFILES["production_pause"].preprocessing)
        self.assertEqual(8, engine.config.beam_size)

    def test_preview_control_profile_disables_only_preview_updates(self):
        candidate, _observed = make_engine(
            bundle(FakeModel("recognized")),
            PROFILES["pause_preview_off"],
            text_postprocessor=lambda text, **_: text,
        )

        self.assertFalse(candidate.config.preview_enabled)
        self.assertEqual(12.0, candidate.config.flush_seconds)
        self.assertEqual(8, candidate.config.beam_size)

    def test_pause_tuning_profiles_change_only_declared_runtime_setting(self):
        expected = {
            "pause_initial_6": ("initial_flush_seconds", 6.0),
            "pause_initial_8": ("initial_flush_seconds", 8.0),
            "pause_flush_16": ("flush_seconds", 16.0),
            "pause_overlap_1_5": ("overlap_seconds", 1.5),
            "pause_guard_0_9": ("boundary_guard_seconds", 0.9),
            "pause_ms_450": ("pause_ms", 450),
            "pause_beam_5": ("beam_size", 5),
            "pause_beam_10": ("beam_size", 10),
        }

        for profile_name, (field, value) in expected.items():
            with self.subTest(profile=profile_name):
                candidate, _observed = make_engine(
                    bundle(FakeModel("recognized")),
                    PROFILES[profile_name],
                    text_postprocessor=lambda text, **_: text,
                )
                self.assertIs(type(candidate), PauseAwareWhisperEngine)
                self.assertEqual(value, getattr(candidate.config, field))
                self.assertFalse(PROFILES[profile_name].preprocessing)

    def test_raw_context_does_not_feed_dictionary_corrections_back(self):
        model = FakeModel("Marvel", "next")
        engine, _ = make_engine(bundle(model), PROFILES["raw_context"], text_postprocessor=lambda text, **_: text.replace("Marvel", "Laravel"))
        chunk = np.ones(96000, dtype=np.int16).tobytes()
        self.assertEqual("Laravel", engine.consume_chunk(chunk)[0].text)
        engine.consume_chunk(chunk)
        self.assertEqual("Marvel", model.calls[1][1]["initial_prompt"])

    def test_context_off_disables_both_context_paths(self):
        model = FakeModel("first", "second")
        engine, _ = make_engine(bundle(model), PROFILES["context_off"], text_postprocessor=lambda text, **_: text)
        chunk = np.ones(96000, dtype=np.int16).tobytes()
        engine.consume_chunk(chunk)
        engine.consume_chunk(chunk)
        for _, options in model.calls:
            self.assertFalse(options["condition_on_previous_text"])
            self.assertIsNone(options["initial_prompt"])

    def test_short_phrase_is_preserved_only_in_opt_in_profile(self):
        chunk = np.ones(4800, dtype=np.int16).tobytes()
        stable, _ = make_engine(bundle(FakeModel("unused")), PROFILES["baseline"], text_postprocessor=lambda text, **_: text)
        candidate, _ = make_engine(bundle(FakeModel("yes")), PROFILES["preserve_short"], text_postprocessor=lambda text, **_: text)
        stable.consume_chunk(chunk)
        candidate.consume_chunk(chunk)
        self.assertEqual([], stable.consume_gap())
        self.assertEqual("yes", candidate.consume_gap()[0].text)

    def test_hotwords_are_opt_in_and_never_a_forced_replacement(self):
        model = FakeModel("Marvel")
        engine, _ = make_engine(bundle(model), PROFILES["term_hints"], text_postprocessor=lambda text, **_: text, hotwords="Laravel PHP")
        self.assertEqual("Marvel", engine.consume_chunk(np.ones(96000, dtype=np.int16).tobytes())[0].text)
        self.assertEqual("Laravel PHP", model.calls[0][1]["hotwords"])
        with self.assertRaisesRegex(ValueError, "hotwords"):
            make_engine(bundle(model), PROFILES["term_hints"], text_postprocessor=lambda text, **_: text)

    def test_observer_captures_lazy_generator_failures(self):
        class FailingModel:
            def transcribe(self, _audio, **_):
                def failed():
                    raise RuntimeError("lazy failure")
                    yield
                return failed(), None
        observed = ObservedModel(FailingModel())
        with self.assertRaisesRegex(RuntimeError, "lazy failure"):
            observed.transcribe(np.zeros(16000))
        self.assertEqual("lazy failure", observed.calls[0]["error"])

    def test_finalize_preserves_the_tail(self):
        engine, _ = make_engine(bundle(FakeModel("tail")), PROFILES["raw_context"], text_postprocessor=lambda text, **_: text)
        self.assertEqual([], engine.consume_chunk(np.ones(800, dtype=np.int16).tobytes()))
        self.assertEqual("tail", engine.finalize()[0].text)
        self.assertEqual([], engine.finalize())


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_wav(self.root / "audio.wav", seconds=1, tone=True)
        self.manifest = write_manifest(self.root, [row()])
        self.samples = load_manifest(self.manifest)
        self.terms = self.root / "terms.json"
        self.terms.write_text('{"enabled":false}', encoding="utf-8")
        self.model_dir = self.root / "model"
        self.model_dir.mkdir()
        (self.model_dir / "model.bin").write_bytes(b"synthetic fixture, not model weights")

    def evaluate(self, **changes):
        from asr_lab.benchmark import evaluate
        options = dict(manifest_path=self.manifest, profiles=[PROFILES["baseline"], PROFILES["context_off"]],
                       model_dir=self.model_dir, device="cpu", terms_path=self.terms, it_mode=False,
                       hotwords="", output_dir=self.root / "reports")
        options.update(changes)
        return evaluate(self.samples, **options)

    def test_offline_replay_reports_raw_and_corrected_results(self):
        from asr_lab.benchmark import replay_sample
        result = replay_sample(bundle(FakeModel("correct words")), PROFILES["baseline"], self.samples[0],
                               postprocessor=lambda text, **_: text)
        self.assertEqual(0, result["scores"]["wer"]["errors"])
        self.assertEqual(1, result["first_result_buffer_seconds"])
        self.assertIsNone(result["first_preview_buffer_seconds"])
        self.assertEqual(0, result["preview_updates"])
        self.assertEqual("correct words", result["raw_hypothesis"])
        self.assertEqual("ru", result["trace"][0]["options"]["language"])

    def test_report_is_reproducible_and_does_not_hide_failures(self):
        model = FakeModel("", "correct words", "correct words")
        with patch("asr_lab.benchmark.load_local_bundle", return_value=(bundle(model), 0.2, [])):
            self.assertTrue(self.evaluate())
        run = json.loads((self.root / "reports" / "run.json").read_text(encoding="utf-8"))
        summary = json.loads((self.root / "reports" / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual("complete", run["status"])
        self.assertEqual("cpu", run["actual_device"])
        self.assertEqual(64, len(run["model_sha256"]))
        self.assertEqual(0, summary[0]["wer"]["errors"])
        with self.assertRaises(FileExistsError):
            self.evaluate()

    def test_closed_test_and_missing_hotwords_fail_before_model_load(self):
        with patch("asr_lab.benchmark.load_local_bundle") as loader:
            with self.assertRaisesRegex(ValueError, "allow-test"):
                self.evaluate(split="test")
            with self.assertRaisesRegex(ValueError, "hotwords-file"):
                self.evaluate(profiles=[PROFILES["term_hints"]])
            loader.assert_not_called()
        self.assertFalse((self.root / "reports").exists())

    def test_fatal_load_error_is_preserved_in_report(self):
        with patch("asr_lab.benchmark.load_local_bundle", side_effect=RuntimeError("load failed")):
            with self.assertRaisesRegex(RuntimeError, "load failed"):
                self.evaluate()
        run = json.loads((self.root / "reports" / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(("failed", "load failed"), (run["status"], run["error"]))

    def test_inference_failure_makes_run_unsuccessful(self):
        model = FakeModel("", "correct words")
        with patch("asr_lab.benchmark.load_local_bundle", return_value=(bundle(model), 0.2, [])):
            with self.assertLogs("asr_lab", level="ERROR"):
                self.assertFalse(self.evaluate())
        summary = json.loads((self.root / "reports" / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(1, summary[1]["failed_samples"])

    def test_it_mode_uses_the_actual_dictionary_key(self):
        from asr_lab.benchmark import make_postprocessor
        self.terms.write_text(json.dumps({"enabled": True, "modes": {"it_mode": {
            "replacements": {"laravel phonetic": "Laravel"}}}}), encoding="utf-8")
        self.assertEqual("Laravel", make_postprocessor(self.terms, True)("laravel phonetic"))
        self.assertEqual("laravel phonetic", make_postprocessor(self.terms, False)("laravel phonetic"))

    def test_it_mode_missing_dictionary_is_not_silently_ignored(self):
        from asr_lab.benchmark import make_postprocessor
        with self.assertRaisesRegex(ValueError, "it_mode"):
            make_postprocessor(self.terms, True)


if __name__ == "__main__":
    unittest.main()
