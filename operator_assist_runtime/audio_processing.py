"""Audio preprocessing helpers for speech-oriented channels."""

from collections import deque
from dataclasses import dataclass
import math
import threading

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


@dataclass(frozen=True)
class CrossChannelEchoConfig:
    sample_rate: int = 16000
    reference_history_seconds: float = 1.0
    max_reference_offset_seconds: float = 0.4
    max_lag_seconds: float = 0.12
    analysis_downsample: int = 4
    min_reference_rms: float = 120.0
    min_microphone_rms: float = 60.0
    min_correlation: float = 0.78
    max_residual_ratio: float = 0.65
    coherence_frame_samples: int = 512
    coherence_hop_samples: int = 256
    min_coherence_frames: int = 6
    min_coherence: float = 0.32
    attack_chunks: int = 2


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


class CrossChannelEchoGate:
    """Replace echo-only microphone blocks with same-length PCM silence."""

    def __init__(self, config=None):
        self.config = config or CrossChannelEchoConfig()
        self._references = deque()
        self._reference_lock = threading.Lock()
        self._echo_streak = 0
        self.matched_chunks = 0
        self.waveform_matched_chunks = 0
        self.coherence_matched_chunks = 0
        self.suppressed_chunks = 0
        self.last_correlation = 0.0
        self.last_residual_ratio = 1.0
        self.last_coherence = 0.0
        self.peak_correlation = 0.0
        self.peak_coherence = 0.0
        self.last_reference_offset_seconds = None

    @staticmethod
    def _rms(samples):
        if samples.size == 0:
            return 0.0
        return math.sqrt(float(np.mean(samples * samples)))

    def observe_reference(self, chunk, captured_at):
        if not chunk:
            return

        timestamp = float(captured_at)
        reference = bytes(chunk)
        cutoff = timestamp - self.config.reference_history_seconds
        with self._reference_lock:
            self._references.append((timestamp, reference))
            while self._references and self._references[0][0] < cutoff:
                self._references.popleft()

    def _candidate_references(self, captured_at):
        cutoff = captured_at - self.config.reference_history_seconds
        with self._reference_lock:
            while self._references and self._references[0][0] < cutoff:
                self._references.popleft()
            return [
                (timestamp, chunk)
                for timestamp, chunk in self._references
                if abs(captured_at - timestamp) <= self.config.max_reference_offset_seconds
            ]

    def _prepare_analysis_samples(self, chunk):
        samples = _int16_samples_to_float32(chunk)
        step = max(1, int(self.config.analysis_downsample))
        samples = samples[::step]
        if samples.size < 4:
            return np.empty(0, dtype=np.float32)

        samples = samples - float(np.mean(samples))
        return np.diff(samples)

    @staticmethod
    def _aligned_samples(left, right, lag):
        if lag >= 0:
            overlap = min(left.size - lag, right.size)
            return left[lag:lag + overlap], right[:overlap]

        offset = -lag
        overlap = min(left.size, right.size - offset)
        return left[:overlap], right[offset:offset + overlap]

    def _score_candidate(self, microphone, reference):
        if microphone.size < 16 or reference.size < 16:
            return 0.0, 1.0

        correlation = np.correlate(microphone, reference, mode="full")
        lags = np.arange(-reference.size + 1, microphone.size)
        downsampled_rate = self.config.sample_rate / max(1, self.config.analysis_downsample)
        max_lag = max(1, int(round(self.config.max_lag_seconds * downsampled_rate)))
        valid = np.abs(lags) <= max_lag
        if not np.any(valid):
            return 0.0, 1.0

        valid_indexes = np.flatnonzero(valid)
        best_index = int(valid_indexes[np.argmax(np.abs(correlation[valid]))])
        left, right = self._aligned_samples(microphone, reference, int(lags[best_index]))
        if left.size < min(microphone.size, reference.size) * 0.5:
            return 0.0, 1.0

        left_energy = float(np.dot(left, left))
        right_energy = float(np.dot(right, right))
        if left_energy <= 0.0 or right_energy <= 0.0:
            return 0.0, 1.0

        dot = float(np.dot(left, right))
        normalized_correlation = abs(dot) / math.sqrt(left_energy * right_energy)
        projection_gain = dot / right_energy
        residual = left - (projection_gain * right)
        residual_ratio = math.sqrt(float(np.dot(residual, residual)) / left_energy)
        return normalized_correlation, residual_ratio

    def _coherence_frames(self, samples):
        frame_size = max(64, int(self.config.coherence_frame_samples))
        hop_size = max(1, int(self.config.coherence_hop_samples))
        if samples.size < frame_size:
            return np.empty((0, 0), dtype=np.complex64)

        samples = samples.astype(np.float32, copy=False)
        samples = samples - float(np.mean(samples))
        window = np.hanning(frame_size).astype(np.float32)
        frames = np.stack(
            [
                samples[offset : offset + frame_size] * window
                for offset in range(0, samples.size - frame_size + 1, hop_size)
            ]
        )
        spectra = np.fft.rfft(frames, axis=1)
        low_bin = max(1, int(math.ceil(80.0 * frame_size / self.config.sample_rate)))
        high_bin = min(
            spectra.shape[1],
            int(math.floor(7000.0 * frame_size / self.config.sample_rate)) + 1,
        )
        return spectra[:, low_bin:high_bin].astype(np.complex64, copy=False)

    def _coherence_score(self, microphone_raw, reference_raw):
        microphone = self._coherence_frames(microphone_raw)
        reference = self._coherence_frames(reference_raw)
        minimum_frames = max(2, int(self.config.min_coherence_frames))
        if microphone.shape[0] < minimum_frames or reference.shape[0] < minimum_frames:
            return 0.0

        hop_seconds = self.config.coherence_hop_samples / float(self.config.sample_rate)
        max_lag_frames = max(1, int(round(self.config.max_lag_seconds / hop_seconds)))
        best_score = 0.0
        for lag in range(-max_lag_frames, max_lag_frames + 1):
            if lag >= 0:
                overlap = min(microphone.shape[0] - lag, reference.shape[0])
                left = microphone[lag : lag + overlap]
                right = reference[:overlap]
            else:
                offset = -lag
                overlap = min(microphone.shape[0], reference.shape[0] - offset)
                left = microphone[:overlap]
                right = reference[offset : offset + overlap]
            if left.shape[0] < minimum_frames:
                continue

            cross_power = np.mean(left * np.conjugate(right), axis=0)
            microphone_power = np.mean(np.abs(left) ** 2, axis=0)
            reference_power = np.mean(np.abs(right) ** 2, axis=0)
            denominator = microphone_power * reference_power
            coherence = (np.abs(cross_power) ** 2) / np.maximum(denominator, 1e-9)
            active = reference_power > float(np.max(reference_power)) * 1e-4
            if np.count_nonzero(active) < 8:
                continue

            weights = np.sqrt(reference_power[active])
            score = float(np.average(np.clip(coherence[active], 0.0, 1.0), weights=weights))
            best_score = max(best_score, score)
        return best_score

    def process_pcm16_at(self, chunk, captured_at):
        microphone_raw = _int16_samples_to_float32(chunk)
        if self._rms(microphone_raw) < self.config.min_microphone_rms:
            self._echo_streak = 0
            return chunk

        microphone = self._prepare_analysis_samples(chunk)
        best = (0.0, 1.0, 0.0, None)
        for reference_time, reference_chunk in self._candidate_references(float(captured_at)):
            reference_raw = _int16_samples_to_float32(reference_chunk)
            if self._rms(reference_raw) < self.config.min_reference_rms:
                continue
            reference = self._prepare_analysis_samples(reference_chunk)
            correlation, residual_ratio = self._score_candidate(microphone, reference)
            coherence = self._coherence_score(microphone_raw, reference_raw)
            if correlation > best[0] or coherence > best[2]:
                reference_offset = abs(float(captured_at) - reference_time)
                best_correlation = max(best[0], correlation)
                best_residual = residual_ratio if correlation >= best[0] else best[1]
                best_coherence = max(best[2], coherence)
                best = (
                    best_correlation,
                    best_residual,
                    best_coherence,
                    reference_offset,
                )

        correlation, residual_ratio, coherence, reference_offset = best
        self.last_correlation = correlation
        self.last_residual_ratio = residual_ratio
        self.last_coherence = coherence
        self.peak_correlation = max(self.peak_correlation, correlation)
        self.peak_coherence = max(self.peak_coherence, coherence)
        self.last_reference_offset_seconds = reference_offset
        waveform_match = (
            correlation >= self.config.min_correlation
            and residual_ratio <= self.config.max_residual_ratio
        )
        coherence_match = coherence >= self.config.min_coherence
        echo_only = waveform_match or coherence_match
        if not echo_only:
            self._echo_streak = 0
            return chunk

        self.matched_chunks += 1
        if waveform_match:
            self.waveform_matched_chunks += 1
        if coherence_match:
            self.coherence_matched_chunks += 1
        self._echo_streak += 1
        if self._echo_streak < max(1, self.config.attack_chunks):
            return chunk

        self.suppressed_chunks += 1
        # Pause-aware Whisper owns silence detection and requires a continuous
        # PCM timeline, so echo is muted rather than converted to a gap marker.
        return bytes(len(chunk))

    def stats(self):
        return {
            "matched_chunks": self.matched_chunks,
            "waveform_matched_chunks": self.waveform_matched_chunks,
            "coherence_matched_chunks": self.coherence_matched_chunks,
            "suppressed_chunks": self.suppressed_chunks,
            "last_correlation": self.last_correlation,
            "last_residual_ratio": self.last_residual_ratio,
            "last_coherence": self.last_coherence,
            "peak_correlation": self.peak_correlation,
            "peak_coherence": self.peak_coherence,
            "last_reference_offset_seconds": self.last_reference_offset_seconds,
        }


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
