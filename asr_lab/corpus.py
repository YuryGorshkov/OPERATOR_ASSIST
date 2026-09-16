"""Read-only validation of paired WAV audio and human-verified transcripts."""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import wave


@dataclass(frozen=True)
class Sample:
    id: str
    audio: Path
    text: str
    start: float
    end: float
    split: str
    book_id: str
    speaker_id: str
    passage_id: str
    critical_terms: tuple
    license: str
    audio_sha256: str

    @property
    def duration(self):
        return self.end - self.start


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wav_info(path):
    try:
        with wave.open(str(path), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, 16000, "NONE"):
                raise ValueError("Expected mono PCM16 WAV at 16000 Hz; convert the audio first.")
            return audio.getnframes() / 16000.0
    except (wave.Error, EOFError) as error:
        raise ValueError(f"Invalid WAV file: {path}") from error


def _required_string(row, key):
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string.")
    return value.strip()


def load_manifest(path, *, max_sample_seconds=120.0):
    path = Path(path).resolve()
    samples, ids, audio_cache, group_splits, clip_splits = [], set(), {}, {}, {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("Each line must be a JSON object.")
            sample_id = _required_string(row, "id")
            if sample_id in ids:
                raise ValueError(f"Duplicate sample id: {sample_id}")
            if row.get("verified") is not True:
                raise ValueError("Transcript must be human-verified: verified=true.")
            split = _required_string(row, "split")
            if split not in ("train", "dev", "test"):
                raise ValueError("split must be train, dev or test.")
            audio_path = (path.parent / _required_string(row, "audio")).resolve()
            if not audio_path.is_file():
                raise ValueError(f"Missing audio: {audio_path}")
            if audio_path not in audio_cache:
                audio_cache[audio_path] = (wav_info(audio_path), file_sha256(audio_path))
            duration, audio_hash = audio_cache[audio_path]
            start, end = float(row.get("start", 0)), float(row.get("end", duration))
            if not all(math.isfinite(value) for value in (start, end)) or not 0 <= start < end <= duration:
                raise ValueError("Invalid audio interval.")
            if end - start > max_sample_seconds:
                raise ValueError(f"Sample exceeds {max_sample_seconds:g} seconds; split at phrase boundaries.")
            has_text, has_file = "text" in row, "text_file" in row
            if has_text == has_file:
                raise ValueError("Specify exactly one of text or text_file.")
            text = row["text"] if has_text else (path.parent / _required_string(row, "text_file")).read_text(encoding="utf-8-sig")
            if not isinstance(text, str):
                raise ValueError("Transcript must be a string; empty text is valid for silence.")
            book = _required_string(row, "book_id")
            speaker = _required_string(row, "speaker_id")
            passage = _required_string(row, "passage_id")
            license_text = _required_string(row, "license")
            terms = row.get("critical_terms", [])
            if not isinstance(terms, list) or any(not isinstance(term, str) or not term.strip() for term in terms):
                raise ValueError("critical_terms must be a list of non-empty strings.")
            group = (book, passage)
            if group in group_splits and group_splits[group] != split:
                raise ValueError("Same book passage appears in different splits (including alternate voices).")
            for previous_start, previous_end, previous_split in clip_splits.get(audio_hash, []):
                if previous_split != split and max(start, previous_start) < min(end, previous_end):
                    raise ValueError("Overlapping audio appears in different splits.")
            group_splits[group] = split
            clip_splits.setdefault(audio_hash, []).append((start, end, split))
            ids.add(sample_id)
            samples.append(Sample(sample_id, audio_path, text.strip(), start, end, split, book,
                                  speaker, passage, tuple(terms), license_text, audio_hash))
        except (ValueError, TypeError, OSError) as error:
            raise ValueError(f"{path.name}:{line_number}: {error}") from error
    if not samples:
        raise ValueError("Manifest has no samples.")
    return samples


def corpus_summary(samples):
    splits = {}
    for split in ("train", "dev", "test"):
        selected = [sample for sample in samples if sample.split == split]
        splits[split] = {"samples": len(selected), "seconds": sum(sample.duration for sample in selected),
                         "books": sorted({sample.book_id for sample in selected}),
                         "speakers": sorted({sample.speaker_id for sample in selected})}
    warnings = []
    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        for field in ("books", "speakers"):
            shared = sorted(set(splits[left][field]) & set(splits[right][field]))
            if shared:
                warnings.append(f"Shared {field} between {left}/{right}: {', '.join(shared)}; this is not a fully unseen-{field} test.")
    return {"splits": splits, "warnings": warnings}


def read_pcm(sample):
    with wave.open(str(sample.audio), "rb") as audio:
        first = int(round(sample.start * 16000))
        last = int(round(sample.end * 16000))
        audio.setpos(first)
        chunk = audio.readframes(last - first)
    if len(chunk) != (last - first) * 2:
        raise ValueError(f"Audio changed or interval is truncated: {sample.id}")
    return chunk
