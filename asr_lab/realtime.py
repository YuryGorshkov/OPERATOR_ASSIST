"""Real-time paced replay through the production recognition pipeline."""

from dataclasses import asdict
from datetime import datetime, timezone
import importlib.metadata
import json
import logging
import math
from pathlib import Path
import platform
import queue
import threading
import time

from operator_assist_runtime.latency_metrics import calculate_recognition_latency

from .benchmark import load_local_bundle, make_postprocessor, write_json
from .corpus import corpus_summary, file_sha256, read_pcm
from .engine import make_engine
from .error_analysis import collect_error_candidates
from .metrics import aggregate, score_text


LOGGER = logging.getLogger("asr_lab.realtime")
_END_OF_STREAM = object()


def _nearest_rank(values, percentile):
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil((float(percentile) / 100.0) * len(ordered)))
    return ordered[rank - 1]


def _latency_summary(values):
    if not values:
        return {
            "count": 0,
            "mean_seconds": None,
            "p50_seconds": None,
            "p95_seconds": None,
            "max_seconds": None,
        }
    return {
        "count": len(values),
        "mean_seconds": sum(values) / len(values),
        "p50_seconds": _nearest_rank(values, 50),
        "p95_seconds": _nearest_rank(values, 95),
        "max_seconds": max(values),
    }


def replay_sample_realtime(
    bundle,
    profile,
    sample,
    *,
    postprocessor,
    chunk_ms=250,
    ui_poll_ms=120,
    trailing_silence_seconds=1.25,
    queue_capacity=64,
    pace=True,
):
    """Feed one sample at wall-clock speed while recognition runs independently."""
    if not 10 <= chunk_ms <= 1000:
        raise ValueError("chunk-ms must be between 10 and 1000.")
    if not 10 <= ui_poll_ms <= 1000:
        raise ValueError("ui-poll-ms must be between 10 and 1000.")
    if not 0 <= trailing_silence_seconds <= 10:
        raise ValueError("trailing silence must be between 0 and 10 seconds.")
    if queue_capacity < 2:
        raise ValueError("queue capacity must be at least 2.")

    pcm = read_pcm(sample)
    silence_bytes = int(round(16000 * trailing_silence_seconds)) * 2
    stream_pcm = pcm + (b"\0" * silence_bytes)
    block_bytes = int(16000 * chunk_ms / 1000) * 2
    engine, observed = make_engine(
        bundle,
        profile,
        text_postprocessor=postprocessor,
    )
    audio_queue = queue.Queue(maxsize=queue_capacity)
    ui_queue = queue.Queue()
    counters = {"drops": 0, "max_queue_depth": 0}
    errors = []
    stream_started_at = time.perf_counter()
    last_captured_at = stream_started_at

    def publish(updates, *, captured_at, dequeued_at, recognized_at, tail=False):
        for update in updates:
            ui_queue.put({
                "kind": update.kind,
                "text": update.text,
                "captured_at": captured_at,
                "dequeued_at": dequeued_at,
                "recognized_at": recognized_at,
                "inference_seconds": update.inference_seconds,
                "audio_tail_seconds": update.audio_tail_seconds,
                "trigger_reason": update.trigger_reason,
                "queue_depth": audio_queue.qsize(),
                "tail": tail,
            })

    def produce():
        nonlocal last_captured_at
        try:
            for offset in range(0, len(stream_pcm), block_bytes):
                chunk = stream_pcm[offset:offset + block_bytes]
                input_end_seconds = (offset + len(chunk)) / 32000.0
                if pace:
                    remaining = stream_started_at + input_end_seconds - time.perf_counter()
                    if remaining > 0:
                        time.sleep(remaining)
                captured_at = time.perf_counter()
                last_captured_at = captured_at
                item = (chunk, captured_at, input_end_seconds)
                try:
                    audio_queue.put_nowait(item)
                except queue.Full:
                    counters["drops"] += 1
                    try:
                        audio_queue.get_nowait()
                    except queue.Empty:
                        pass
                    audio_queue.put_nowait(item)
                counters["max_queue_depth"] = max(
                    counters["max_queue_depth"], audio_queue.qsize()
                )
        except Exception as error:
            errors.append(error)
        finally:
            audio_queue.put(_END_OF_STREAM)

    def recognize():
        try:
            while True:
                item = audio_queue.get()
                if item is _END_OF_STREAM:
                    break
                chunk, captured_at, input_end_seconds = item
                observed.input_end_seconds = input_end_seconds
                dequeued_at = time.perf_counter()
                updates = engine.consume_chunk(chunk)
                recognized_at = time.perf_counter()
                publish(
                    updates,
                    captured_at=captured_at,
                    dequeued_at=dequeued_at,
                    recognized_at=recognized_at,
                )

            dequeued_at = time.perf_counter()
            updates = engine.finalize()
            recognized_at = time.perf_counter()
            publish(
                updates,
                captured_at=last_captured_at,
                dequeued_at=dequeued_at,
                recognized_at=recognized_at,
                tail=True,
            )
        except Exception as error:
            errors.append(error)

    producer = threading.Thread(target=produce, name="asr-realtime-producer")
    recognizer = threading.Thread(target=recognize, name="asr-realtime-recognizer")
    producer.start()
    recognizer.start()

    events = []
    first_preview_at = None
    final_displayed_at = None
    poll_seconds = ui_poll_ms / 1000.0 if pace else 0.001
    while producer.is_alive() or recognizer.is_alive() or not ui_queue.empty():
        time.sleep(poll_seconds)
        displayed_at = time.perf_counter()
        while True:
            try:
                event = ui_queue.get_nowait()
            except queue.Empty:
                break
            latency = calculate_recognition_latency(
                captured_at=event["captured_at"],
                dequeued_at=event["dequeued_at"],
                recognized_at=event["recognized_at"],
                displayed_at=displayed_at,
                inference_seconds=event["inference_seconds"],
                audio_tail_seconds=event["audio_tail_seconds"],
            )
            event["latency"] = asdict(latency)
            event["displayed_offset_seconds"] = displayed_at - stream_started_at
            events.append(event)
            if event["kind"] == "partial" and event["text"] and first_preview_at is None:
                first_preview_at = displayed_at
            if event["kind"] == "final" and event["text"]:
                final_displayed_at = displayed_at

    producer.join()
    recognizer.join()
    if errors:
        raise errors[0]

    finals = [event["text"] for event in events if event["kind"] == "final" and event["text"]]
    hypothesis = " ".join(finals)
    source_end_at = stream_started_at + len(pcm) / 32000.0
    completed_at = time.perf_counter()
    return {
        "id": sample.id,
        "speaker_id": sample.speaker_id,
        "profile": profile.name,
        "paced": bool(pace),
        "reference": sample.text,
        "hypothesis": hypothesis,
        "scores": score_text(sample.text, hypothesis),
        "audio_seconds": len(pcm) / 32000.0,
        "stream_seconds": len(stream_pcm) / 32000.0,
        "wall_seconds": completed_at - stream_started_at,
        "first_preview_seconds": (
            first_preview_at - stream_started_at if first_preview_at is not None else None
        ),
        "reference_end_to_last_final_seconds": (
            final_displayed_at - source_end_at if final_displayed_at is not None else None
        ),
        "queue_drops": counters["drops"],
        "max_queue_depth": counters["max_queue_depth"],
        "preview_updates": sum(
            event["kind"] == "partial" and bool(event["text"]) for event in events
        ),
        "final_updates": len(finals),
        "events": events,
        "trace": observed.calls,
    }


def summarize_realtime_results(results):
    good = [result for result in results if "error" not in result]
    final_latencies = [
        event["latency"]["speech_end_to_ui_seconds"]
        for result in good
        for event in result["events"]
        if event["kind"] == "final" and event["text"]
    ]
    completion_latencies = [
        result["reference_end_to_last_final_seconds"]
        for result in good
        if result["reference_end_to_last_final_seconds"] is not None
    ]

    speakers = []
    for speaker_id in dict.fromkeys(result["speaker_id"] for result in good):
        group = [result for result in good if result["speaker_id"] == speaker_id]
        speakers.append({
            "speaker_id": speaker_id,
            "samples": len(group),
            "wer": aggregate([result["scores"] for result in group], "wer"),
            "cer": aggregate([result["scores"] for result in group], "cer"),
            "queue_drops": sum(result["queue_drops"] for result in group),
        })

    return {
        "samples": len(results),
        "failed_samples": len(results) - len(good),
        "wer": aggregate([result["scores"] for result in good], "wer"),
        "cer": aggregate([result["scores"] for result in good], "cer"),
        "queue_drops": sum(result["queue_drops"] for result in good),
        "max_queue_depth": max((result["max_queue_depth"] for result in good), default=0),
        "final_event_latency": _latency_summary(final_latencies),
        "sample_completion_latency": _latency_summary(completion_latencies),
        "speakers": speakers,
        "error_candidates": collect_error_candidates(good),
    }


def evaluate_realtime(
    samples,
    *,
    manifest_path,
    profile,
    model_dir,
    device,
    terms_path,
    it_mode,
    output_dir,
    split="dev",
    allow_test=False,
    chunk_ms=250,
    ui_poll_ms=120,
    trailing_silence_seconds=1.25,
):
    if split == "test" and not allow_test:
        raise ValueError("Closed test set requires --allow-test. Tune profiles on dev, not test.")
    selected = [sample for sample in samples if sample.split == split]
    if not selected:
        raise ValueError(f"No samples in {split} split.")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    metadata = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": file_sha256(manifest_path),
        "model_dir": str(Path(model_dir).resolve()),
        "requested_device": device,
        "profile": asdict(profile),
        "split": split,
        "chunk_ms": chunk_ms,
        "ui_poll_ms": ui_poll_ms,
        "trailing_silence_seconds": trailing_silence_seconds,
        "cold_start_sample": selected[0].id,
        "terms_sha256": file_sha256(terms_path),
        "it_mode": bool(it_mode),
        "corpus": corpus_summary(samples),
        "python": platform.python_version(),
        "dependencies": {
            package: importlib.metadata.version(package)
            for package in ("faster-whisper", "ctranslate2", "numpy")
        },
        "status": "initializing",
    }
    write_json(output_dir / "run.json", metadata)
    results = []
    log_handler = logging.FileHandler(output_dir / "realtime.log", mode="x", encoding="utf-8")
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(log_handler)
    try:
        bundle, load_seconds, errors = load_local_bundle(model_dir, device)
        metadata.update({
            "actual_device": bundle.device,
            "compute_type": bundle.compute_type,
            "model_load_seconds": load_seconds,
            "fallback_errors": errors,
            "model_sha256": file_sha256(Path(model_dir) / "model.bin"),
        })
        write_json(output_dir / "run.json", metadata)
        postprocessor = make_postprocessor(terms_path, it_mode)
        with (output_dir / "samples.jsonl").open("x", encoding="utf-8") as stream:
            for sample in selected:
                LOGGER.info("Real-time replay: %s / %s", sample.id, sample.speaker_id)
                try:
                    result = replay_sample_realtime(
                        bundle,
                        profile,
                        sample,
                        postprocessor=postprocessor,
                        chunk_ms=chunk_ms,
                        ui_poll_ms=ui_poll_ms,
                        trailing_silence_seconds=trailing_silence_seconds,
                    )
                except Exception as error:
                    LOGGER.exception("Real-time sample failed")
                    result = {
                        "id": sample.id,
                        "speaker_id": sample.speaker_id,
                        "profile": profile.name,
                        "error": str(error) or type(error).__name__,
                        "error_type": type(error).__name__,
                    }
                results.append(result)
                stream.write(json.dumps(result, ensure_ascii=False) + "\n")
                stream.flush()
        summary = summarize_realtime_results(results)
        write_json(output_dir / "summary.json", summary)
        write_json(output_dir / "error-candidates.json", {
            "schema_version": 1,
            "warning": "Review candidates manually before adding any replacement to the application.",
            "candidates": summary["error_candidates"],
        })
        metadata["status"] = "failed_samples" if summary["failed_samples"] else "complete"
        return metadata["status"] == "complete"
    except Exception as error:
        metadata.update({"status": "failed", "error": str(error)})
        raise
    finally:
        write_json(output_dir / "run.json", metadata)
        LOGGER.removeHandler(log_handler)
        log_handler.close()
