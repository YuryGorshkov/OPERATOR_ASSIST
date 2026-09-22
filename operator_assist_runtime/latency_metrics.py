"""Pure helpers for measuring recognition delivery latency."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RecognitionLatency:
    queue_seconds: float
    processing_seconds: float
    ui_dispatch_seconds: float
    trigger_to_ui_seconds: float
    speech_end_to_ui_seconds: float
    inference_seconds: float | None = None
    audio_tail_seconds: float = 0.0


def calculate_recognition_latency(
    *,
    captured_at,
    dequeued_at,
    recognized_at,
    displayed_at,
    inference_seconds=None,
    audio_tail_seconds=0.0,
):
    timestamps = tuple(
        float(value)
        for value in (captured_at, dequeued_at, recognized_at, displayed_at)
    )
    if not all(math.isfinite(value) for value in timestamps):
        raise ValueError("Recognition latency timestamps must be finite.")
    if any(later < earlier for earlier, later in zip(timestamps, timestamps[1:])):
        raise ValueError("Recognition latency timestamps must be monotonic.")

    tail = float(audio_tail_seconds or 0.0)
    if not math.isfinite(tail) or tail < 0:
        raise ValueError("Recognition audio tail must be a finite non-negative value.")

    inference = None
    if inference_seconds is not None:
        inference = float(inference_seconds)
        if not math.isfinite(inference) or inference < 0:
            raise ValueError("Recognition inference time must be finite and non-negative.")

    captured, dequeued, recognized, displayed = timestamps
    trigger_to_ui = displayed - captured
    return RecognitionLatency(
        queue_seconds=dequeued - captured,
        processing_seconds=recognized - dequeued,
        ui_dispatch_seconds=displayed - recognized,
        trigger_to_ui_seconds=trigger_to_ui,
        speech_end_to_ui_seconds=trigger_to_ui + tail,
        inference_seconds=inference,
        audio_tail_seconds=tail,
    )


def _nearest_rank(values, percentile):
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil((float(percentile) / 100.0) * len(ordered)))
    return ordered[rank - 1]


class RecognitionLatencyTracker:
    def __init__(self):
        self._samples = {}

    def clear(self):
        self._samples.clear()

    def record(self, label, kind, sample):
        key = (str(label), str(kind))
        values = self._samples.setdefault(key, [])
        values.append(sample)
        return self.summary(label, kind)

    def summary(self, label, kind):
        values = self._samples.get((str(label), str(kind)), [])
        if not values:
            return None
        end_to_ui = [sample.speech_end_to_ui_seconds for sample in values]
        return {
            "count": len(values),
            "mean_seconds": sum(end_to_ui) / len(end_to_ui),
            "p50_seconds": _nearest_rank(end_to_ui, 50),
            "p95_seconds": _nearest_rank(end_to_ui, 95),
            "max_seconds": max(end_to_ui),
        }
