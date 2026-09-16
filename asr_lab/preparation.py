"""Explicit file conversion and verified-pair export, without recording devices."""

import json
from pathlib import Path
import wave

from .corpus import corpus_summary, file_sha256, read_pcm


def convert_audio(source, output, *, permission_confirmed=False):
    if not permission_confirmed:
        raise ValueError("Confirm permission to use this recording with --permission-confirmed.")
    import av

    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file() or source == output:
        raise ValueError("Choose an existing source and a different output file.")
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            with wave.open(stream, "wb") as target, av.open(str(source)) as container:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(16000)
                resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
                frames_written = 0
                for frame in container.decode(audio=0):
                    for converted in resampler.resample(frame):
                        target.writeframesraw(converted.to_ndarray().tobytes())
                        frames_written += converted.samples
                for converted in resampler.resample(None):
                    target.writeframesraw(converted.to_ndarray().tobytes())
                    frames_written += converted.samples
                if not frames_written:
                    raise ValueError("Source has no decoded audio.")
        return {"output": str(output), "seconds": frames_written / 16000.0,
                "source_sha256": file_sha256(source), "output_sha256": file_sha256(output)}
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def export_training_pairs(samples, output):
    if any(sample.duration > 30.0 for sample in samples):
        raise ValueError("Training examples must be at most 30 seconds; align and split the long samples first.")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    audio_dir = output / "audio"
    audio_dir.mkdir()
    streams = {}
    status = {"status": "preparing", "completed_samples": 0, "training_started": False}
    status_path = output / "export.json"
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    try:
        for split in ("train", "dev", "test"):
            streams[split] = (output / f"{split}.jsonl").open("x", encoding="utf-8")
        for index, sample in enumerate(samples):
            name = f"{index:06d}.wav"
            clip = audio_dir / name
            with wave.open(str(clip), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(read_pcm(sample))
            row = {"audio": f"audio/{name}", "text": sample.text, "id": sample.id,
                   "book_id": sample.book_id, "speaker_id": sample.speaker_id,
                   "passage_id": sample.passage_id, "license": sample.license,
                   "source_audio_sha256": sample.audio_sha256,
                   "clip_sha256": file_sha256(clip), "source_start": sample.start,
                   "source_end": sample.end}
            streams[sample.split].write(json.dumps(row, ensure_ascii=False) + "\n")
            status["completed_samples"] += 1
        (output / "corpus.json").write_text(json.dumps(corpus_summary(samples), ensure_ascii=False, indent=2), encoding="utf-8")
        status["status"] = "complete"
    except BaseException as error:
        status.update({"status": "failed", "error": str(error) or type(error).__name__})
        raise
    finally:
        for stream in streams.values():
            stream.close()
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output": str(output), "samples": len(samples), "training_started": False}
