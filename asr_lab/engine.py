"""Lab-only adapters; the baseline uses the unchanged desktop engine."""

from dataclasses import replace
import time

import numpy as np

from operator_assist_runtime.recognition_engines import (
    FasterWhisperBufferedEngine, RecognitionUpdate,
)


class ObservedModel:
    def __init__(self, model):
        self.model = model
        self.calls = []
        self.input_end_seconds = 0.0

    def transcribe(self, audio, **options):
        started = time.perf_counter()
        event = {"audio_seconds": len(audio) / 16000.0,
                 "input_end_seconds": self.input_end_seconds, "options": options}
        try:
            segments, info = self.model.transcribe(audio, **options)
            segments = list(segments)
            event.update({"seconds": time.perf_counter() - started,
                          "raw_text": " ".join(segment.text.strip() for segment in segments if segment.text.strip()),
                          "segments": [{key: getattr(segment, key, None) for key in
                                        ("start", "end", "avg_logprob", "no_speech_prob", "compression_ratio")}
                                       for segment in segments]})
            self.calls.append(event)
            return iter(segments), info
        except Exception as error:
            event.update({"seconds": time.perf_counter() - started, "error": str(error)})
            self.calls.append(event)
            raise


class ExperimentalWhisperEngine(FasterWhisperBufferedEngine):
    def __init__(self, bundle, *, profile, text_postprocessor, hotwords=""):
        super().__init__(bundle, text_postprocessor=text_postprocessor,
                         flush_after_seconds=profile.flush_seconds,
                         min_segment_seconds=profile.min_segment_seconds)
        self.profile = profile
        self.hotwords = hotwords.strip()
        if profile.use_hotwords and not self.hotwords:
            raise ValueError("term_hints requires a separate, topic-specific hotwords file.")

    def _flush_buffer(self, force=False):
        if not self._buffer or (len(self._buffer) < self._min_segment_bytes and not force):
            return []
        audio = np.frombuffer(bytes(self._buffer), dtype=np.int16).astype(np.float32) / 32768.0
        self._buffer.clear()
        options = dict(language="ru", task="transcribe", beam_size=self.profile.beam_size,
                       best_of=5, condition_on_previous_text=self.profile.context_source != "none",
                       initial_prompt=self._previous_text or None, vad_filter=True,
                       vad_parameters={"min_silence_duration_ms": self.profile.vad_silence_ms},
                       word_timestamps=False)
        if self.profile.use_hotwords:
            options["hotwords"] = self.hotwords
        segments, _info = self._bundle.model.transcribe(audio, **options)
        raw_text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        text = self._text_postprocessor(raw_text, log_changes=True)
        if not text:
            return []
        context = raw_text if self.profile.context_source == "raw" else text
        self._previous_text = context[-self._context_chars:] if self.profile.context_source != "none" else ""
        return [RecognitionUpdate("final", text)]


def make_engine(bundle, profile, *, text_postprocessor, hotwords=""):
    observed = ObservedModel(bundle.model)
    observed_bundle = replace(bundle, model=observed)
    if profile.name == "baseline":
        engine = FasterWhisperBufferedEngine(observed_bundle, text_postprocessor=text_postprocessor)
    else:
        engine = ExperimentalWhisperEngine(observed_bundle, profile=profile,
                                           text_postprocessor=text_postprocessor, hotwords=hotwords)
    return engine, observed
