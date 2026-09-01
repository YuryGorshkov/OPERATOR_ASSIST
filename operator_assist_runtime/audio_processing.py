"""Audio preprocessing helpers for speech-oriented channels."""

from dataclasses import dataclass
import math

import numpy as np


INT16_MAX = 32767.0
INT16_MIN = -32768.0


@dataclass(frozen=True)
class SpeechPreprocessorConfig:
    silence_gate_rms: int = 0
    hangover_chunks: int = 0
    target_rms: int = 0
    min_gain: float = 1.0
    max_gain: float = 1.0
    gain_smoothing: float = 0.0
    dc_block_alpha: float = 0.0
    stronger_channel_ratio: float = 1.75


def _int16_samples_to_float32(chunk):
    if not chunk:
        return np.empty(0, dtype=np.float32)

    return np.frombuffer(chunk, dtype=np.int16).astype(np.float32, copy=False)


def _float32_to_pcm16(samples):
    if samples.size == 0:
        return b""

    clipped = np.clip(np.rint(samples), INT16_MIN, INT16_MAX)
    return clipped.astype(np.int16).tobytes()


def adaptive_downmix(frames, *, stronger_channel_ratio=1.75):
    """Convert loopback frames to a mono float32 signal with voice-safe mixing."""

    samples = np.asarray(frames, dtype=np.float32)
    if samples.size == 0:
        return np.empty(0, dtype=np.float32)

    if samples.ndim == 1:
        return np.nan_to_num(samples, copy=False)

    if samples.shape[1] == 1:
        return np.nan_to_num(samples[:, 0], copy=False)

    cleaned = np.nan_to_num(samples, copy=False)
    channel_rms = np.sqrt(np.mean(cleaned * cleaned, axis=0))
    ranked = np.sort(channel_rms)
    strongest = float(ranked[-1]) if ranked.size else 0.0
    runner_up = float(ranked[-2]) if ranked.size > 1 else 0.0

    if strongest > 0.0 and (strongest / max(runner_up, 1e-6)) >= stronger_channel_ratio:
        strongest_idx = int(np.argmax(channel_rms))
        return cleaned[:, strongest_idx]

    return cleaned.mean(axis=1, dtype=np.float32)


def loopback_frames_to_pcm16(frames, *, stronger_channel_ratio=1.75):
    samples = adaptive_downmix(frames, stronger_channel_ratio=stronger_channel_ratio)
    if samples.size == 0:
        return b""

    samples = np.clip(samples, -1.0, 1.0)
    return _float32_to_pcm16(samples * INT16_MAX)


class SpeechAudioPreprocessor:
    """Stateful PCM16 preprocessor for noisy speech channels."""

    def __init__(self, config):
        self.config = config
        self.current_gain = 1.0
        self.speech_hold_remaining = 0
        self._previous_input = 0.0
        self._previous_output = 0.0

    @classmethod
    def speaker_default(cls):
        return cls(
            SpeechPreprocessorConfig(
                silence_gate_rms=45,
                hangover_chunks=2,
                target_rms=2200,
                min_gain=0.9,
                max_gain=3.2,
                gain_smoothing=0.18,
                dc_block_alpha=0.995,
            )
        )

    def _apply_dc_block(self, samples):
        alpha = self.config.dc_block_alpha
        if alpha <= 0.0 or samples.size == 0:
            return samples

        filtered = np.empty_like(samples, dtype=np.float32)
        prev_input = self._previous_input
        prev_output = self._previous_output

        for index, current in enumerate(samples):
            output = float(current) - prev_input + (alpha * prev_output)
            filtered[index] = output
            prev_input = float(current)
            prev_output = output

        self._previous_input = prev_input
        self._previous_output = prev_output
        return filtered

    def _rms(self, samples):
        if samples.size == 0:
            return 0.0
        return math.sqrt(float(np.mean(samples * samples)))

    def process_pcm16(self, chunk):
        samples = _int16_samples_to_float32(chunk)
        if samples.size == 0:
            return b""

        samples = self._apply_dc_block(samples)
        input_rms = self._rms(samples)

        if input_rms >= self.config.silence_gate_rms:
            self.speech_hold_remaining = self.config.hangover_chunks
        elif self.speech_hold_remaining > 0:
            self.speech_hold_remaining -= 1
        else:
            self.current_gain += (1.0 - self.current_gain) * 0.08
            return b""

        if input_rms > 0.0 and self.config.target_rms > 0:
            desired_gain = self.config.target_rms / input_rms
            desired_gain = min(self.config.max_gain, max(self.config.min_gain, desired_gain))
            smoothing = self.config.gain_smoothing
            self.current_gain += (desired_gain - self.current_gain) * smoothing

        if self.current_gain != 1.0:
            samples = samples * self.current_gain

        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        if peak > INT16_MAX:
            samples = samples * (INT16_MAX / peak)

        return _float32_to_pcm16(samples)
