from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

from operator_assist_runtime.pause_recognition import (
    OwnedWord,
    PauseAwareWhisperConfig,
    PauseAwareWhisperEngine,
    select_owned_words,
)
from operator_assist_runtime.recognition_engines import PreciseEngineBundle


def pcm(seconds, value=500):
    return np.full(round(seconds * 16000), value, dtype=np.int16).tobytes()


def segment(probability, *words):
    values = [
        SimpleNamespace(word=text, start=start, end=end)
        for text, start, end in words
    ]
    return SimpleNamespace(
        text="".join(word.word for word in values),
        words=values,
        no_speech_prob=probability,
    )


class Detector:
    def inspect(self, audio, start, owner):
        values = np.frombuffer(audio, dtype=np.int16)
        fresh = values[max(0, owner - start) :]
        nonzero = np.flatnonzero(values)
        quiet = len(values) - nonzero[-1] - 1 if len(nonzero) else len(values)
        return bool(np.any(fresh)), quiet / 16000.0


class Model:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def transcribe(self, audio, **options):
        self.calls.append((audio.copy(), options))
        return iter(next(self.responses, ())), SimpleNamespace()


def engine(model):
    bundle = PreciseEngineBundle(model, "fixture", "cpu", "int8", Path("."))
    return PauseAwareWhisperEngine(
        bundle,
        detector=Detector(),
        text_postprocessor=lambda text, **_kwargs: text,
    )


class WordOwnershipTests(unittest.TestCase):
    def test_crossing_word_is_owned_by_only_the_next_window(self):
        values = [segment(0.1, (" edge", 3.9, 4.1))]

        left, pending = select_owned_words(
            values, window_start=0, owner_start=0, owner_end=4
        )
        right, _ = select_owned_words(
            values, window_start=0, owner_start=4, owner_end=8
        )

        self.assertEqual([], left)
        self.assertTrue(pending)
        self.assertEqual([" edge"], [word.text for word in right])

    def test_overlapping_copy_is_removed_but_real_repetition_is_preserved(self):
        previous = OwnedWord(" yes", 3.8, 4.1)
        overlapping = [segment(0.1, (" yes", 3.98, 4.13), (" next", 4.2, 4.5))]
        repeated = [segment(0.1, (" yes", 4.2, 4.5), (" yes", 4.5, 4.8))]

        deduplicated, _ = select_owned_words(
            overlapping,
            window_start=0,
            owner_start=4,
            owner_end=8,
            previous=previous,
        )
        genuine, _ = select_owned_words(
            repeated,
            window_start=0,
            owner_start=4,
            owner_end=8,
            previous=previous,
        )

        self.assertEqual([" next"], [word.text for word in deduplicated])
        self.assertEqual([" yes", " yes"], [word.text for word in genuine])

    def test_untimed_text_is_rejected_instead_of_guessed(self):
        with self.assertRaisesRegex(ValueError, "timestamps"):
            select_owned_words(
                [SimpleNamespace(text="text", words=None)],
                window_start=0,
                owner_start=0,
                owner_end=4,
            )


class PauseAwareWhisperTests(unittest.TestCase):
    def test_default_pause_waits_for_stable_phrase_boundary(self):
        self.assertEqual(600, PauseAwareWhisperConfig().pause_ms)

    def test_silence_never_starts_decoder_and_memory_stays_bounded(self):
        model = Model()
        candidate = engine(model)

        self.assertEqual([], candidate.consume_chunk(pcm(60, 0)))
        self.assertEqual([], candidate.finalize())

        self.assertEqual([], model.calls)
        self.assertLessEqual(candidate.peak_buffer_seconds, 2.25)

    def test_short_reply_flushes_after_a_real_pause(self):
        model = Model([segment(0.1, (" yes", 0.1, 0.4))])
        candidate = engine(model)

        updates = candidate.consume_chunk(pcm(0.5) + pcm(2.0, 0))

        self.assertEqual(["yes"], [update.text for update in updates])
        self.assertEqual(1, len(model.calls))
        self.assertTrue(model.calls[0][1]["word_timestamps"])
        self.assertFalse(model.calls[0][1]["condition_on_previous_text"])

    def test_guard_rejects_non_speech_without_matching_its_words(self):
        model = Model([segment(0.91, (" arbitrary", 0.1, 0.4))])
        candidate = engine(model)

        updates = candidate.consume_chunk(pcm(0.5) + pcm(2.0, 0))

        self.assertEqual([], updates)
        self.assertEqual(1, candidate.rejected_no_speech_segments)

    def test_continuous_speech_uses_bounded_windows(self):
        model = Model([segment(0.1, (" first phrase", 0.2, 1.0))])
        candidate = engine(model)

        updates = candidate.consume_chunk(pcm(5.0))

        self.assertEqual(["first phrase"], [update.text for update in updates])
        self.assertLessEqual(candidate.peak_buffer_seconds, 5.0)
        self.assertAlmostEqual(4.6, len(model.calls[0][0]) / 16000, places=6)

    def test_single_character_tail_is_suppressed_but_yes_is_preserved(self):
        debris = engine(Model([segment(0.1, (" у", 0.1, 0.2))]))
        debris.consume_chunk(pcm(0.5))
        reply = engine(Model([segment(0.1, (" да", 0.1, 0.3))]))
        reply.consume_chunk(pcm(0.5))

        self.assertEqual([], debris.finalize())
        self.assertEqual(["да"], [update.text for update in reply.finalize()])

    def test_finalize_is_idempotent_and_rejects_late_audio(self):
        candidate = engine(Model([segment(0.1, (" tail", 0.1, 0.4))]))
        candidate.consume_chunk(pcm(0.5))

        self.assertEqual(["tail"], [update.text for update in candidate.finalize()])
        self.assertEqual([], candidate.finalize())
        with self.assertRaisesRegex(RuntimeError, "finalized"):
            candidate.consume_chunk(pcm(0.25))


if __name__ == "__main__":
    unittest.main()
