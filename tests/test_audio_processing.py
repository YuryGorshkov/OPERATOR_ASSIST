import unittest

try:
    import numpy as np
    from operator_assist_runtime.audio_processing import (
        SpeechAudioPreprocessor,
        adaptive_downmix,
    )
    AUDIO_PROCESSING_AVAILABLE = True
except ModuleNotFoundError:
    np = None
    SpeechAudioPreprocessor = None
    adaptive_downmix = None
    AUDIO_PROCESSING_AVAILABLE = False


def _pcm_from_value(value, count=2048):
    return np.full(count, value, dtype=np.int16).tobytes()


def _pcm_tone(amplitude, count=2048, cycles=6):
    angles = np.linspace(0.0, np.pi * 2.0 * cycles, count, endpoint=False)
    samples = np.rint(np.sin(angles) * amplitude).astype(np.int16)
    return samples.tobytes()


@unittest.skipUnless(AUDIO_PROCESSING_AVAILABLE, "numpy-dependent audio processing tests require installed runtime dependencies")
class AudioProcessingTests(unittest.TestCase):
    def test_adaptive_downmix_prefers_stronger_channel_when_imbalanced(self):
        frames = np.column_stack(
            (
                np.full(32, 0.85, dtype=np.float32),
                np.full(32, 0.05, dtype=np.float32),
            )
        )

        mono = adaptive_downmix(frames)

        self.assertGreater(float(np.mean(mono)), 0.75)

    def test_adaptive_downmix_averages_balanced_channels(self):
        frames = np.column_stack(
            (
                np.full(32, 0.4, dtype=np.float32),
                np.full(32, 0.6, dtype=np.float32),
            )
        )

        mono = adaptive_downmix(frames)

        self.assertAlmostEqual(0.5, float(np.mean(mono)), places=3)

    def test_speaker_preprocessor_drops_low_level_noise(self):
        preprocessor = SpeechAudioPreprocessor.speaker_default()

        result = preprocessor.process_pcm16(_pcm_tone(8))

        self.assertEqual(b"", result)

    def test_speaker_preprocessor_keeps_short_tail_after_speech(self):
        preprocessor = SpeechAudioPreprocessor.speaker_default()

        voiced = preprocessor.process_pcm16(_pcm_tone(900))
        tail_1 = preprocessor.process_pcm16(_pcm_tone(12))
        tail_2 = preprocessor.process_pcm16(_pcm_tone(12))
        tail_3 = preprocessor.process_pcm16(_pcm_tone(12))
        tail_4 = preprocessor.process_pcm16(_pcm_tone(12))

        self.assertNotEqual(b"", voiced)
        self.assertNotEqual(b"", tail_1)
        self.assertNotEqual(b"", tail_2)
        self.assertEqual(b"", tail_4)

    def test_speaker_preprocessor_boosts_quiet_speech_without_clipping(self):
        preprocessor = SpeechAudioPreprocessor.speaker_default()
        source = _pcm_tone(320)

        result = preprocessor.process_pcm16(source)

        self.assertNotEqual(b"", result)
        input_samples = np.frombuffer(source, dtype=np.int16).astype(np.float32)
        output_samples = np.frombuffer(result, dtype=np.int16).astype(np.float32)
        self.assertGreater(float(np.sqrt(np.mean(output_samples * output_samples))), float(np.sqrt(np.mean(input_samples * input_samples))))
        self.assertLessEqual(float(np.max(np.abs(output_samples))), 32767.0)


if __name__ == "__main__":
    unittest.main()
