"""Pause-aware streaming for the precise Whisper speaker channel."""

from dataclasses import dataclass
import logging
import math
import time

import numpy as np

from operator_assist_runtime.recognition_engines import (
    DEFAULT_NO_SPEECH_REJECT_THRESHOLD,
    RecognitionUpdate,
    filter_no_speech_segments,
    is_meaningful_final_text,
)


@dataclass(frozen=True)
class OwnedWord:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class PauseAwareWhisperConfig:
    sample_rate: int = 16000
    flush_seconds: float = 12.0
    min_chunk_seconds: float = 4.0
    pause_ms: int = 600
    short_pause_ms: int = 1000
    pause_min_window_seconds: float = 2.5
    overlap_seconds: float = 1.0
    boundary_guard_seconds: float = 0.6
    initial_flush_seconds: float = 4.0
    vad_silence_ms: int = 350
    no_speech_reject_threshold: float = DEFAULT_NO_SPEECH_REJECT_THRESHOLD
    beam_size: int = 8
    best_of: int = 5
    preview_enabled: bool = True
    preview_after_seconds: float = 2.5
    preview_beam_size: int = 1


def _word_key(value):
    return "".join(character for character in (value or "").casefold() if character.isalnum())


def select_owned_words(
    segments,
    *,
    window_start,
    owner_start,
    owner_end,
    previous=None,
    window_end=None,
    include_terminal=False,
    recover_uncommitted=False,
    deferred_words=(),
    deferred_out=None,
):
    """Select words owned by one time range so overlap is never emitted twice."""
    selected = []
    pending = False
    for segment in segments:
        words = getattr(segment, "words", None)
        if str(getattr(segment, "text", "") or "").strip() and not words:
            raise ValueError("Whisper returned text without word timestamps.")
        for word in words or ():
            start = float(word.start)
            end = float(word.end)
            if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start <= end:
                raise ValueError("Whisper returned invalid word timestamps.")
            if window_end is not None:
                if window_start + end > window_end + 0.02:
                    raise ValueError("Whisper word timestamp extends beyond available audio.")
                available = window_end - window_start
                start = min(start, available)
                end = min(end, available)

            current = OwnedWord(str(word.word), window_start + start, window_start + end)
            midpoint = (current.start + current.end) / 2
            terminal = include_terminal and current.start == current.end == owner_end
            if midpoint >= owner_end and not terminal:
                pending = True
                if deferred_out is not None:
                    deferred_out.append(current)
                continue

            key = _word_key(current.text)
            if midpoint < owner_start:
                overlaps_previous = previous and current.start < previous.end
                agreed = bool(
                    deferred_words
                    and not selected
                    and key
                    and key == _word_key(deferred_words[0].text)
                    and current.end > owner_start
                    and (deferred_words[0].start + deferred_words[0].end) / 2 >= owner_start
                    and min(current.end, deferred_words[0].end)
                    > max(current.start, deferred_words[0].start)
                )
                if not recover_uncommitted or overlaps_previous:
                    if not agreed:
                        continue

            if (
                previous
                and key
                and key == _word_key(previous.text)
                and min(previous.end, current.end) > max(previous.start, current.start)
            ):
                continue
            selected.append(current)

    return selected, pending


class SileroPauseDetector:
    """Inspect only past PCM and report whether it ends with a real pause."""

    def __init__(self, model=None):
        if model is None:
            from faster_whisper.vad import get_vad_model

            model = get_vad_model()
        self.model = model

    def inspect(self, pcm, buffer_start, owner_start):
        total_samples = len(pcm) // 2
        sample_count = min(total_samples, 32000)
        if not sample_count:
            return False, 0.0

        values = (
            np.frombuffer(pcm[-sample_count * 2 :], dtype=np.int16).astype(np.float32)
            / 32768.0
        )
        padded = np.pad(values, (0, (-sample_count) % 512))
        probabilities = np.asarray(self.model(padded)).reshape(-1)
        origin = buffer_start + total_samples - sample_count
        full_windows = sample_count // 512
        new_speech = any(
            probability >= 0.5
            and origin + min((index + 1) * 512, sample_count) > owner_start
            for index, probability in enumerate(probabilities)
        )
        quiet_samples = 0
        for probability in reversed(probabilities[:full_windows]):
            if probability >= 0.35:
                break
            quiet_samples += 512
        return bool(new_speech), quiet_samples / 16000.0


class PauseAwareWhisperEngine:
    """Decode around pauses and use timestamps to own overlapping boundary words."""

    def __init__(self, bundle, *, text_postprocessor, config=None, detector=None):
        self.bundle = bundle
        self.config = config or PauseAwareWhisperConfig()
        self.postprocessor = text_postprocessor
        self.detector = detector if detector is not None else SileroPauseDetector()
        self._logger = logging.getLogger("operator_assist")
        self._validate_config()
        self._logger.info(
            "Pause-aware Whisper configured. beam=%s best_of=%s pause_ms=%s",
            self.config.beam_size,
            self.config.best_of,
            self.config.pause_ms,
        )

        self.buffer = bytearray()
        self.buffer_start = 0
        self.owner_start = 0
        self.received = 0
        self.has_speech = False
        self.pending_words = False
        self.closed = False
        self.initial_result_seen = False
        self.last_word = None
        self.deferred_words = []
        self.peak_buffer_seconds = 0.0
        self.rejected_no_speech_segments = 0
        self.preview_emitted_for_owner = False
        self.preview_visible = False

    def _validate_config(self):
        config = self.config
        if config.sample_rate <= 0:
            raise ValueError("Whisper sample rate must be positive.")
        if not 0.2 <= config.min_chunk_seconds <= config.flush_seconds <= 24:
            raise ValueError("Invalid pause-aware chunk duration.")
        if not 0 <= config.overlap_seconds < config.min_chunk_seconds:
            raise ValueError("Invalid pause-aware overlap duration.")
        if not 0 <= config.boundary_guard_seconds <= 1.5:
            raise ValueError("Invalid pause-aware boundary guard.")
        if not 0 < config.pause_ms <= config.short_pause_ms:
            raise ValueError("Invalid pause-aware pause thresholds.")
        if not 0 <= config.pause_min_window_seconds <= config.flush_seconds:
            raise ValueError("Invalid minimum pause decode window.")
        if not config.min_chunk_seconds <= config.initial_flush_seconds <= config.flush_seconds:
            raise ValueError("Invalid initial pause-aware chunk duration.")
        search_values = (config.beam_size, config.best_of)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in search_values):
            raise ValueError("Invalid pause-aware decoder search size.")
        if not 1 <= config.beam_size <= 10 or not 1 <= config.best_of <= 10:
            raise ValueError("Invalid pause-aware decoder search size.")
        if not isinstance(config.preview_enabled, bool):
            raise ValueError("Invalid preview mode flag.")
        if not 0.5 <= config.preview_after_seconds <= config.initial_flush_seconds:
            raise ValueError("Invalid preview start duration.")
        if (
            isinstance(config.preview_beam_size, bool)
            or not isinstance(config.preview_beam_size, int)
            or not 1 <= config.preview_beam_size <= config.beam_size
        ):
            raise ValueError("Invalid preview decoder search size.")
        filter_no_speech_segments((), config.no_speech_reject_threshold)

    def consume_gap(self):
        raise RuntimeError("Pause-aware Whisper requires original PCM including silence.")

    def consume_chunk(self, pcm):
        if self.closed:
            raise RuntimeError("Cannot feed a finalized Whisper engine.")
        if len(pcm) % 2:
            raise ValueError("PCM16 chunk has an incomplete sample.")

        updates = []
        block_bytes = int(self.config.sample_rate * 0.25) * 2
        for offset in range(0, len(pcm), block_bytes):
            block = pcm[offset : offset + block_bytes]
            self.buffer.extend(block)
            self.received += len(block) // 2
            self.peak_buffer_seconds = max(
                self.peak_buffer_seconds,
                len(self.buffer) / float(self.config.sample_rate * 2),
            )
            speech, quiet = self.detector.inspect(
                bytes(self.buffer), self.buffer_start, self.owner_start
            )
            self.has_speech |= speech
            pending_duration = (
                self.received - self.owner_start
            ) / float(self.config.sample_rate)
            available_duration = (
                self.received - self.buffer_start
            ) / float(self.config.sample_rate)
            pause_ready = (
                quiet * 1000 >= self.config.pause_ms
                and (
                    pending_duration >= self.config.min_chunk_seconds
                    or quiet * 1000 >= self.config.short_pause_ms
                )
                and available_duration >= self.config.pause_min_window_seconds
            )
            duration_cap = (
                self.config.initial_flush_seconds
                if not self.initial_result_seen
                else self.config.flush_seconds
            )
            cap_ready = (
                pending_duration
                >= duration_cap + self.config.boundary_guard_seconds
            )
            if (self.has_speech or self.pending_words) and pause_ready:
                updates.extend(self._emit(self.received, "pause"))
            elif (self.has_speech or self.pending_words) and cap_ready:
                boundary = self.owner_start + round(
                    duration_cap * self.config.sample_rate
                )
                updates.extend(self._emit(boundary, "cap"))
            elif self._preview_ready(pending_duration, quiet):
                updates.extend(self._preview())
            elif not self.has_speech and not self.pending_words:
                self._trim(
                    max(
                        self.buffer_start,
                        self.received - self.config.sample_rate * 2,
                    )
                )
                self.owner_start = max(self.owner_start, self.buffer_start)
        return updates

    def _preview_ready(self, pending_duration, quiet):
        if (
            not self.config.preview_enabled
            or not self.has_speech
            or self.preview_emitted_for_owner
        ):
            return False
        if quiet * 1000 >= self.config.pause_ms:
            return False
        if pending_duration < self.config.preview_after_seconds:
            return False
        return True

    def _preview(self):
        sample_rate = self.config.sample_rate
        start = max(self.owner_start, self.buffer_start)
        audio_bytes = bytes(self.buffer[(start - self.buffer_start) * 2 :])
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        started_at = time.perf_counter()
        segments, _info = self.bundle.model.transcribe(
            audio,
            language="ru",
            task="transcribe",
            beam_size=self.config.preview_beam_size,
            best_of=self.config.preview_beam_size,
            condition_on_previous_text=False,
            initial_prompt=None,
            word_timestamps=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": self.config.vad_silence_ms},
        )
        segments, rejected = filter_no_speech_segments(
            list(segments), self.config.no_speech_reject_threshold
        )
        raw_text = " ".join(
            str(getattr(segment, "text", "") or "").strip()
            for segment in segments
            if str(getattr(segment, "text", "") or "").strip()
        )
        text = self.postprocessor(raw_text, log_changes=False) if raw_text else ""
        if text and not is_meaningful_final_text(text):
            text = ""
        self.preview_emitted_for_owner = True
        was_visible = self.preview_visible
        self.preview_visible = bool(text)
        elapsed = time.perf_counter() - started_at
        audio_seconds = len(audio) / float(sample_rate)
        self._logger.info(
            "Whisper preview processed. audio=%.2fs inference=%.2fs rtf=%.2f chars=%s rejected=%s",
            audio_seconds,
            elapsed,
            elapsed / audio_seconds if audio_seconds else 0.0,
            len(text),
            len(rejected),
        )
        if text or was_visible:
            return [RecognitionUpdate("partial", text)]
        return []

    def _trim(self, start):
        remove_samples = max(0, start - self.buffer_start)
        del self.buffer[: remove_samples * 2]
        self.buffer_start += remove_samples

    def _emit(self, boundary, reason):
        sample_rate = self.config.sample_rate
        if reason == "cap":
            decode_end = min(
                self.received,
                boundary + round(self.config.boundary_guard_seconds * sample_rate),
            )
        else:
            decode_end = self.received
        audio_bytes = bytes(self.buffer[: (decode_end - self.buffer_start) * 2])
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        started_at = time.perf_counter()
        segments, _info = self.bundle.model.transcribe(
            audio,
            language="ru",
            task="transcribe",
            beam_size=self.config.beam_size,
            best_of=self.config.best_of,
            condition_on_previous_text=False,
            initial_prompt=None,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": self.config.vad_silence_ms},
        )
        segments = list(segments)
        decoder_had_text = any(
            str(getattr(segment, "text", "") or "").strip() for segment in segments
        )
        segments, rejected = filter_no_speech_segments(
            segments, self.config.no_speech_reject_threshold
        )
        if rejected:
            self.rejected_no_speech_segments += len(rejected)
            self._logger.info(
                "Whisper no-speech guard rejected pause-aware segments. count=%s probabilities=%s total=%s",
                len(rejected),
                ",".join(f"{probability:.3f}" for _segment, probability in rejected),
                self.rejected_no_speech_segments,
            )

        deferred = []
        window_start_seconds = self.buffer_start / float(sample_rate)
        boundary_seconds = boundary / float(sample_rate)
        decode_end_seconds = decode_end / float(sample_rate)
        words, pending = select_owned_words(
            segments,
            window_start=window_start_seconds,
            owner_start=self.owner_start / float(sample_rate),
            owner_end=boundary_seconds,
            previous=self.last_word,
            window_end=decode_end_seconds,
            include_terminal=reason == "final",
            recover_uncommitted=True,
            deferred_words=self.deferred_words,
            deferred_out=deferred,
        )
        raw_text = " ".join("".join(word.text for word in words).split())
        text = self.postprocessor(raw_text, log_changes=True) if raw_text else ""
        if text and not is_meaningful_final_text(text):
            self._logger.info("Whisper short final fragment suppressed. chars=%s", len(text))
            text = ""

        next_start = max(
            self.buffer_start,
            boundary - round(self.config.overlap_seconds * sample_rate),
        )
        if reason == "pause":
            _, quiet = self.detector.inspect(audio_bytes, self.buffer_start, boundary)
            max_quiet = (decode_end - self.buffer_start) / float(sample_rate)
            if not math.isfinite(quiet) or not 0 <= quiet <= max_quiet:
                raise ValueError("Invalid measured pause duration.")
            last_word = words[-1] if words else self.last_word
            if (
                quiet * 1000 >= self.config.pause_ms
                and last_word
                and last_word.end <= boundary_seconds
            ):
                silence_start = boundary - math.floor(quiet * sample_rate)
                next_start = min(
                    boundary,
                    max(
                        next_start,
                        silence_start,
                        math.ceil(last_word.end * sample_rate),
                    ),
                )

        tail = bytes(self.buffer[(next_start - self.buffer_start) * 2 :])
        tail_has_speech, _quiet = self.detector.inspect(tail, next_start, boundary)
        elapsed = time.perf_counter() - started_at
        audio_seconds = len(audio) / float(sample_rate)
        self._logger.info(
            "Whisper pause-aware segment processed. reason=%s audio=%.2fs inference=%.2fs rtf=%.2f words=%s chars=%s",
            reason,
            audio_seconds,
            elapsed,
            elapsed / audio_seconds if audio_seconds else 0.0,
            len(words),
            len(text),
        )

        if words:
            self.last_word = words[-1]
        self.initial_result_seen |= decoder_had_text
        self.owner_start = boundary
        self.preview_emitted_for_owner = False
        self.deferred_words = deferred
        self.pending_words = pending and boundary < self.received
        self._trim(next_start)
        self.has_speech = tail_has_speech
        updates = []
        if self.preview_visible:
            updates.append(RecognitionUpdate("partial", ""))
            self.preview_visible = False
        if text:
            updates.append(RecognitionUpdate("final", text))
        return updates

    def finalize(self):
        if self.closed:
            return []
        if self.received > self.owner_start and (self.has_speech or self.pending_words):
            updates = self._emit(self.received, "final")
        else:
            updates = []
        self.closed = True
        self.buffer.clear()
        return updates
