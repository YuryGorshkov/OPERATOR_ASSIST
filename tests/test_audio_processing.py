import unittest

try:
    import numpy as np
    from operator_assist_runtime.audio_processing import (
        CrossChannelEchoConfig,
        CrossChannelEchoGate,
        SpeechAudioPreprocessor,
        adaptive_downmix,
    )
    AUDIO_PROCESSING_AVAILABLE = True
except ModuleNotFoundError:
    np = None
    CrossChannelEchoConfig = None
    CrossChannelEchoGate = None
    SpeechAudioPreprocessor = None
    adaptive_downmix = None
    AUDIO_PROCESSING_AVAILABLE = False


def _pcm_from_value(value, count=2048):
    return np.full(count, value, dtype=np.int16).tobytes()


def _pcm_tone(amplitude, count=2048, cycles=6):
    angles = np.linspace(0.0, np.pi * 2.0 * cycles, count, endpoint=False)
    samples = np.rint(np.sin(angles) * amplitude).astype(np.int16)
    return samples.tobytes()


def _pcm_signal(seed, amplitude=2400, count=4000):
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 1.0, count + 8)
    filtered = np.convolve(noise, np.array([0.15, 0.35, 0.35, 0.15]), mode="valid")[:count]
    envelope = 0.35 + 0.65 * np.sin(np.linspace(0.0, np.pi, count)) ** 2
    samples = filtered * envelope
    samples *= amplitude / max(float(np.max(np.abs(samples))), 1.0)
    return np.rint(samples).astype(np.int16).tobytes()


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

    def test_cross_channel_echo_gate_suppresses_repeated_reference(self):
        gate = CrossChannelEchoGate(
            CrossChannelEchoConfig(attack_chunks=2, min_correlation=0.72)
        )
        reference_1 = _pcm_signal(10)
        reference_2 = _pcm_signal(11)

        gate.observe_reference(reference_1, 10.0)
        first = gate.process_pcm16_at(reference_1, 10.02)
        gate.observe_reference(reference_2, 10.25)
        second = gate.process_pcm16_at(reference_2, 10.27)

        self.assertNotEqual(b"", first)
        self.assertEqual(bytes(len(reference_2)), second)
        self.assertEqual(1, gate.suppressed_chunks)

    def test_cross_channel_echo_gate_keeps_independent_microphone_speech(self):
        gate = CrossChannelEchoGate(CrossChannelEchoConfig(attack_chunks=1))
        reference = _pcm_signal(20)
        microphone = _pcm_signal(21)

        gate.observe_reference(reference, 20.0)
        result = gate.process_pcm16_at(microphone, 20.02)

        self.assertEqual(microphone, result)
        self.assertEqual(0, gate.suppressed_chunks)

    def test_cross_channel_echo_gate_keeps_double_talk(self):
        gate = CrossChannelEchoGate(CrossChannelEchoConfig(attack_chunks=1))
        reference = np.frombuffer(_pcm_signal(30), dtype=np.int16).astype(np.float32)
        operator = np.frombuffer(_pcm_signal(31), dtype=np.int16).astype(np.float32)
        microphone = np.clip((reference * 0.35) + operator, -32768, 32767).astype(np.int16).tobytes()

        gate.observe_reference(reference.astype(np.int16).tobytes(), 30.0)
        result = gate.process_pcm16_at(microphone, 30.02)

        self.assertEqual(microphone, result)
        self.assertEqual(0, gate.suppressed_chunks)

    def test_cross_channel_echo_gate_handles_delayed_filtered_leak(self):
        gate = CrossChannelEchoGate(CrossChannelEchoConfig(attack_chunks=1))
        reference = np.frombuffer(_pcm_signal(35), dtype=np.int16).astype(np.float32)
        leaked = np.convolve(reference, np.array([0.52, 0.26, 0.13, 0.06]), mode="same")
        leaked = np.concatenate((np.zeros(160, dtype=np.float32), leaked[:-160]))
        leaked = np.clip(leaked, -32768, 32767).astype(np.int16).tobytes()

        gate.observe_reference(reference.astype(np.int16).tobytes(), 35.0)
        result = gate.process_pcm16_at(leaked, 35.02)

        self.assertEqual(bytes(len(leaked)), result)
        self.assertGreater(gate.last_correlation, 0.9)

    def test_cross_channel_echo_gate_ignores_stale_reference(self):
        gate = CrossChannelEchoGate(CrossChannelEchoConfig(attack_chunks=1))
        reference = _pcm_signal(40)

        gate.observe_reference(reference, 40.0)
        result = gate.process_pcm16_at(reference, 41.0)

        self.assertEqual(reference, result)


if __name__ == "__main__":
    unittest.main()
