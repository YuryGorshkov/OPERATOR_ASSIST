"""Offline replay through the actual speaker preprocessor and buffering engine."""

from dataclasses import asdict
from datetime import datetime, timezone
import importlib.metadata
import json
import logging
from pathlib import Path
import platform
import time

import numpy as np

from operator_assist_runtime import recognition_engines as runtime
from operator_assist_runtime.audio_processing import SpeechAudioPreprocessor
from operator_assist_runtime.technical_terms import TechnicalTermsManager
from .corpus import corpus_summary, file_sha256, read_pcm
from .engine import make_engine
from .metrics import aggregate, score_terms, score_text


LOGGER = logging.getLogger("asr_lab")


def load_local_bundle(model_dir, device):
    model_dir = Path(model_dir).resolve()
    if not model_dir.is_dir() or not all((model_dir / file).is_file() for file in ("model.bin", "config.json", "tokenizer.json")):
        raise ValueError("A complete local CTranslate2 Whisper model is required; automatic downloads are disabled.")
    if not runtime.precise_engine_available():
        raise RuntimeError("Installed faster-whisper runtime is unavailable.")
    attempts = runtime.precise_engine_attempt_plan(device)
    if any(target == "cuda" for target, _ in attempts):
        ready, details = runtime.prepare_cuda_runtime(logger=LOGGER)
        if not ready:
            LOGGER.warning("CUDA unavailable: %s", details)
            attempts = [attempt for attempt in attempts if attempt[0] != "cuda"]
    errors, started = [], time.perf_counter()
    for target, compute in attempts:
        LOGGER.info("Loading local model: %s / %s", target, compute)
        try:
            model = runtime.WhisperModel(str(model_dir), device=target, compute_type=compute,
                                         local_files_only=True)
            bundle = runtime.PreciseEngineBundle(model, model_dir.name, target, compute, model_dir)
            return bundle, time.perf_counter() - started, errors
        except Exception as error:
            errors.append(f"{target}/{compute}: {error}")
            LOGGER.warning("Model attempt failed: %s", errors[-1])
    raise RuntimeError("Unable to load local model: " + "; ".join(errors))


def make_postprocessor(terms_path, it_mode):
    manager = TechnicalTermsManager(get_terms_path=lambda: Path(terms_path),
                                   get_logger=lambda: None,
                                   normalize_name=lambda text: " ".join(text.casefold().split()),
                                   short_text=lambda text, *_: text,
                                   default_payload_factory=lambda: {"enabled": False})
    if it_mode:
        if "it_mode" not in manager.get_available_modes():
            raise ValueError("Terms file has no it_mode dictionary.")
        manager.set_active_modes(("it_mode",))
    return manager.apply


def replay_sample(bundle, profile, sample, *, postprocessor, hotwords="", chunk_ms=250):
    pcm = read_pcm(sample)
    engine, observed = make_engine(bundle, profile, text_postprocessor=postprocessor, hotwords=hotwords)
    preprocessor = SpeechAudioPreprocessor.speaker_default() if profile.preprocessing else None
    block_bytes = int(16000 * chunk_ms / 1000) * 2
    outputs, first_result, first_preview = [], None, None
    preview_updates, preprocessing_seconds, gated_seconds = 0, 0.0, 0.0
    gap_queued = False
    started = time.perf_counter()
    for offset in range(0, len(pcm), block_bytes):
        original = pcm[offset:offset + block_bytes]
        observed.input_end_seconds = (offset + len(original)) / 32000.0
        prep_started = time.perf_counter()
        chunk = preprocessor.process_pcm16(original) if preprocessor else original
        preprocessing_seconds += time.perf_counter() - prep_started
        if not chunk:
            gated_seconds += len(original) / 32000.0
            updates = engine.consume_gap() if not gap_queued else []
            gap_queued = True
        else:
            gap_queued = False
            updates = engine.consume_chunk(chunk)
        for update in updates:
            if update.kind == "final":
                outputs.append(update.text)
                if first_result is None:
                    first_result = observed.input_end_seconds
            elif update.kind == "partial" and update.text:
                preview_updates += 1
                if first_preview is None:
                    first_preview = observed.input_end_seconds
    for update in engine.finalize():
        if update.kind == "final":
            outputs.append(update.text)
            if first_result is None:
                first_result = len(pcm) / 32000.0
    elapsed = time.perf_counter() - started
    text = " ".join(outputs)
    raw_calls = observed.calls
    if profile.engine_kind == "pause":
        raw_calls = [
            call for call in raw_calls
            if call.get("options", {}).get("word_timestamps")
        ]
    raw_text = " ".join(call.get("raw_text", "") for call in raw_calls).strip()
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    duration = len(pcm) / 32000.0
    return {
        "id": sample.id, "profile": profile.name, "reference": sample.text,
        "hypothesis": text, "raw_hypothesis": raw_text,
        "scores": score_text(sample.text, text), "raw_scores": score_text(sample.text, raw_text),
        "critical_terms": score_terms(sample.text, text, sample.critical_terms),
        "audio_seconds": duration, "engine_wall_seconds": elapsed,
        "inference_seconds": sum(call["seconds"] for call in observed.calls),
        "preprocessing_seconds": preprocessing_seconds, "gated_audio_seconds": gated_seconds,
        "real_time_factor": elapsed / duration,
        "first_result_buffer_seconds": first_result,
        "first_preview_buffer_seconds": first_preview,
        "preview_updates": preview_updates,
        "input_peak": float(np.max(np.abs(samples))),
        "input_rms": float(np.sqrt(np.mean(samples * samples))),
        "clipped_samples": int(np.sum(np.abs(samples) >= 32767)),
        "trace": observed.calls,
    }


def summarize_results(results):
    summaries = []
    for name in dict.fromkeys(result["profile"] for result in results):
        group = [result for result in results if result["profile"] == name]
        good = [result for result in group if "error" not in result]
        audio_seconds = sum(result["audio_seconds"] for result in good)
        wall_seconds = sum(result["engine_wall_seconds"] for result in good)
        preview_delays = [
            result["first_preview_buffer_seconds"] for result in good
            if result.get("first_preview_buffer_seconds") is not None
        ]
        summaries.append({
            "profile": name, "samples": len(group), "failed_samples": len(group) - len(good),
            "wer": aggregate([result["scores"] for result in good], "wer"),
            "cer": aggregate([result["scores"] for result in good], "cer"),
            "raw_wer": aggregate([result["raw_scores"] for result in good], "wer"),
            "audio_seconds": audio_seconds, "engine_wall_seconds": wall_seconds,
            "real_time_factor": wall_seconds / audio_seconds if audio_seconds else None,
            "preview_updates": sum(result.get("preview_updates", 0) for result in good),
            "mean_first_preview_buffer_seconds": (
                sum(preview_delays) / len(preview_delays) if preview_delays else None
            ),
            "silence_insertions": sum(result["scores"]["wer"]["insertions"] for result in good
                                      if not result["scores"]["wer"]["reference"]),
            "critical_terms_expected": sum(term["expected"] for result in good for term in result["critical_terms"]),
            "critical_terms_recognized": sum(term["recognized"] for result in good for term in result["critical_terms"]),
            "critical_terms_extra": sum(term["extra"] for result in good for term in result["critical_terms"]),
        })
    return summaries


def evaluate(samples, *, manifest_path, profiles, model_dir, device, terms_path, it_mode,
             hotwords, output_dir, split="dev", allow_test=False, chunk_ms=250):
    if split == "test" and not allow_test:
        raise ValueError("Closed test set requires --allow-test. Tune profiles on dev, not test.")
    selected = [sample for sample in samples if sample.split == split]
    if not selected:
        raise ValueError(f"No samples in {split} split.")
    if any(profile.use_hotwords for profile in profiles) and not hotwords.strip():
        raise ValueError("term_hints requires --hotwords-file; reference transcripts are never used as hints.")
    if not 10 <= chunk_ms <= 1000:
        raise ValueError("chunk-ms must be between 10 and 1000.")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    metadata = {
        "schema_version": 1, "manifest_sha256": file_sha256(manifest_path),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model_dir": str(Path(model_dir).resolve()), "requested_device": device,
        "profiles": [asdict(profile) for profile in profiles], "split": split,
        "chunk_ms": chunk_ms, "it_mode": it_mode, "hotwords": hotwords,
        "terms_sha256": file_sha256(terms_path), "corpus": corpus_summary(samples),
        "python": platform.python_version(),
        "dependencies": {package: importlib.metadata.version(package) for package in
                         ("faster-whisper", "ctranslate2", "numpy")},
        "samples": [{"id": sample.id, "audio_sha256": sample.audio_sha256,
                     "start": sample.start, "end": sample.end, "book_id": sample.book_id,
                     "speaker_id": sample.speaker_id, "passage_id": sample.passage_id,
                     "license": sample.license} for sample in selected],
        "warning": "Offline replay: RTF and buffer delay do not measure live UI startup, queue drops or p95 latency.",
        "status": "initializing",
    }
    source_root = Path(__file__).resolve().parent
    metadata["source_sha256"] = {path.name: file_sha256(path) for path in source_root.glob("*.py")}
    metadata["desktop_engine_sha256"] = file_sha256(runtime.__file__)
    run_path = output_dir / "run.json"
    write_json(run_path, metadata)
    results = []
    log_handler = logging.FileHandler(output_dir / "benchmark.log", mode="x", encoding="utf-8")
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(log_handler)
    try:
        bundle, load_seconds, errors = load_local_bundle(model_dir, device)
        metadata.update({"actual_device": bundle.device, "compute_type": bundle.compute_type,
                         "model_load_seconds": load_seconds, "fallback_errors": errors,
                         "model_sha256": file_sha256(Path(model_dir) / "model.bin")})
        write_json(run_path, metadata)
        # Separate cold inference from profile comparisons without using any reference text.
        started = time.perf_counter()
        segments, _ = bundle.model.transcribe(np.zeros(16000, dtype=np.float32), language="ru", vad_filter=False)
        list(segments)
        metadata["warmup_seconds"] = time.perf_counter() - started
        postprocessor = make_postprocessor(terms_path, it_mode)
        with (output_dir / "samples.jsonl").open("x", encoding="utf-8") as stream:
            for sample in selected:
                for profile in profiles:
                    LOGGER.info("%s / %s", sample.id, profile.name)
                    try:
                        result = replay_sample(bundle, profile, sample, postprocessor=postprocessor,
                                               hotwords=hotwords, chunk_ms=chunk_ms)
                    except Exception as error:
                        LOGGER.exception("Sample failed")
                        result = {"id": sample.id, "profile": profile.name,
                                  "error": str(error) or type(error).__name__, "error_type": type(error).__name__}
                    results.append(result)
                    stream.write(json.dumps(result, ensure_ascii=False) + "\n")
                    stream.flush()
        metadata["status"] = "failed_samples" if any("error" in result for result in results) else "complete"
        write_json(output_dir / "summary.json", summarize_results(results))
        return metadata["status"] == "complete"
    except Exception as error:
        metadata.update({"status": "failed", "error": str(error)})
        raise
    finally:
        write_json(run_path, metadata)
        LOGGER.removeHandler(log_handler)
        log_handler.close()


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
