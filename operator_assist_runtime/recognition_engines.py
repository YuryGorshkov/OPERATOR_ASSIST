"""Recognition-engine adapters used by the desktop runtime."""

import ctypes
from dataclasses import dataclass
import json
import logging
import math
import os
from pathlib import Path
import sys
import time

try:
    import numpy as np
except Exception:
    np = None

try:
    import ctranslate2
except Exception:
    ctranslate2 = None

try:
    from faster_whisper import WhisperModel

    FASTER_WHISPER_AVAILABLE = True
    FASTER_WHISPER_IMPORT_ERROR = ""
except Exception as error:
    WhisperModel = None
    FASTER_WHISPER_AVAILABLE = False
    FASTER_WHISPER_IMPORT_ERROR = str(error)

from vosk import KaldiRecognizer


DEFAULT_PRECISE_MODEL_NAME = "large-v3"
PRECISE_MODEL_REPOSITORIES = {
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}
DEFAULT_NO_SPEECH_REJECT_THRESHOLD = 0.8
MIN_FINAL_ALNUM_CHARS = 2
_KNOWN_SUBTITLE_CREDIT_MARKERS = ("dimatorzok", "диматоржок")
PRECISE_DEVICE_GPU = "gpu"
PRECISE_DEVICE_CPU = "cpu"
_CUDA_DLL_DIRECTORY_HANDLES = []


def _candidate_cublas_bin_dirs():
    candidates = []

    try:
        import nvidia.cublas

        candidates.extend(Path(path) / "bin" for path in nvidia.cublas.__path__)
    except Exception:
        pass

    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.extend(
            (
                bundle_root / "nvidia" / "cublas" / "bin",
                bundle_root / "_internal" / "nvidia" / "cublas" / "bin",
            )
        )

    unique_candidates = []
    seen = set()
    for candidate in candidates:
        resolved = str(candidate.resolve())
        if resolved.lower() not in seen:
            unique_candidates.append(Path(resolved))
            seen.add(resolved.lower())
    return unique_candidates


def prepare_cuda_runtime(*, logger=None):
    """Preload cuBLAS so CTranslate2 can resolve it in frozen Windows builds."""
    if os.name != "nt":
        return True, "CUDA runtime uses the platform loader."

    required_dlls = ("cublasLt64_12.dll", "cublas64_12.dll")
    errors = []

    for candidate in _candidate_cublas_bin_dirs():
        if not all((candidate / dll_name).is_file() for dll_name in required_dlls):
            continue

        try:
            candidate_text = str(candidate)
            if candidate_text.lower() not in os.environ.get("PATH", "").lower():
                os.environ["PATH"] = candidate_text + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                _CUDA_DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(candidate_text))
            for dll_name in required_dlls:
                ctypes.WinDLL(str(candidate / dll_name))
            if logger is not None:
                logger.info("CUDA cuBLAS runtime ready. bin_dir=%s", candidate)
            return True, f"cuBLAS загружен из {candidate}"
        except OSError as error:
            errors.append(f"{candidate}: {error}")

    try:
        for dll_name in required_dlls:
            ctypes.WinDLL(dll_name)
        if logger is not None:
            logger.info("CUDA cuBLAS runtime ready via the Windows DLL search path")
        return True, "cuBLAS загружен из системного пути."
    except OSError as error:
        errors.append(f"system path: {error}")

    details = "; ".join(errors) if errors else "файлы cuBLAS не найдены"
    if logger is not None:
        logger.warning("CUDA cuBLAS runtime unavailable. details=%s", details)
    return False, details


@dataclass(frozen=True)
class RecognitionUpdate:
    kind: str
    text: str
    inference_seconds: float | None = None
    audio_tail_seconds: float = 0.0
    trigger_reason: str = ""


@dataclass(frozen=True)
class PreciseEngineBundle:
    model: object
    model_name: str
    device: str
    compute_type: str
    download_root: Path


def precise_engine_available():
    return FASTER_WHISPER_AVAILABLE and np is not None


def precise_engine_status(models_dir, model_name=DEFAULT_PRECISE_MODEL_NAME):
    if not FASTER_WHISPER_AVAILABLE:
        return False, f"faster-whisper не установлен: {FASTER_WHISPER_IMPORT_ERROR}"
    if np is None:
        return False, "numpy недоступен для точного режима."

    download_root = Path(models_dir) / "whisper-cache"
    if cached_precise_model_path(download_root, model_name) is not None:
        return True, f"Модель Whisper {model_name} найдена в локальном кэше."

    return True, (
        f"Модель Whisper {model_name} будет подготовлена при первом запуске; "
        "это может занять заметное время."
    )


def cached_precise_model_path(download_root, model_name):
    """Return a complete local snapshot without invoking the hub cache resolver."""
    repository = PRECISE_MODEL_REPOSITORIES.get(model_name)
    if repository is None:
        return None

    repository_dir = Path(download_root) / f"models--{repository.replace('/', '--')}"
    snapshot_root = repository_dir / "snapshots"
    if not snapshot_root.is_dir():
        return None

    candidates = []
    main_ref = repository_dir / "refs" / "main"
    try:
        revision = main_ref.read_text(encoding="utf-8").strip()
    except OSError:
        revision = ""
    if revision:
        candidates.append(snapshot_root / revision)

    try:
        candidates.extend(
            sorted(
                (path for path in snapshot_root.iterdir() if path.is_dir()),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        )
    except OSError:
        return None

    required_files = ("model.bin", "config.json", "tokenizer.json")
    seen = set()
    for candidate in candidates:
        candidate_key = str(candidate).lower()
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        if all((candidate / file_name).is_file() for file_name in required_files):
            return candidate
    return None


def preferred_precise_device():
    if ctranslate2 is not None:
        try:
            if int(ctranslate2.get_cuda_device_count()) > 0:
                return "cuda"
        except Exception:
            pass
    return "cpu"


def supported_precise_compute_types(device):
    if ctranslate2 is None:
        return set()
    try:
        return set(ctranslate2.get_supported_compute_types(device))
    except Exception:
        return set()


def precise_engine_attempt_plan(device_preference=None):
    if device_preference not in (None, PRECISE_DEVICE_GPU, PRECISE_DEVICE_CPU):
        raise ValueError(f"Неизвестный вычислитель Whisper: {device_preference}")

    use_cuda = (
        device_preference != PRECISE_DEVICE_CPU
        and preferred_precise_device() == "cuda"
    )
    if use_cuda:
        cuda_supported = supported_precise_compute_types("cuda")
        cuda_order = ("float16", "int8_float16", "int8", "int8_float32", "float32")
        cuda_attempts = [
            ("cuda", compute_type)
            for compute_type in cuda_order
            if not cuda_supported or compute_type in cuda_supported
        ]
    else:
        cuda_attempts = []

    cpu_supported = supported_precise_compute_types("cpu")
    cpu_order = ("int8", "float32")
    cpu_attempts = [
        ("cpu", compute_type)
        for compute_type in cpu_order
        if not cpu_supported or compute_type in cpu_supported
    ]
    return cuda_attempts + cpu_attempts


def filter_no_speech_segments(segments, threshold):
    """Partition decoder segments without relying on recognized phrases."""
    segments = list(segments)
    if threshold is None:
        return segments, []
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(threshold)
        or not 0.0 < threshold <= 1.0
    ):
        raise ValueError("Порог отсутствия речи должен быть числом больше 0 и не больше 1.")

    accepted = []
    rejected = []
    for segment in segments:
        probability = getattr(segment, "no_speech_prob", None)
        try:
            probability = float(probability)
        except (TypeError, ValueError):
            accepted.append(segment)
            continue
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            accepted.append(segment)
            continue
        if probability >= threshold:
            rejected.append((segment, probability))
        else:
            accepted.append(segment)
    return accepted, rejected


def filter_known_metadata_hallucinations(segments):
    """Reject only reproduced Whisper subtitle-credit hallucinations."""
    segments = list(segments)

    def is_known_credit(text):
        key = "".join(character for character in text.casefold() if character.isalnum())
        return key.startswith("субтитры") and any(
            marker in key for marker in _KNOWN_SUBTITLE_CREDIT_MARKERS
        )

    accepted = []
    rejected = []
    for segment in segments:
        text = str(getattr(segment, "text", "") or "")
        if is_known_credit(text):
            rejected.append(segment)
        else:
            accepted.append(segment)
    if rejected:
        return accepted, rejected

    combined_text = " ".join(
        str(getattr(segment, "text", "") or "") for segment in segments
    )
    if is_known_credit(combined_text):
        return [], segments
    return accepted, rejected


def is_meaningful_final_text(text, *, min_alnum_chars=MIN_FINAL_ALNUM_CHARS):
    """Reject isolated decoder debris while preserving short replies such as 'да'."""
    return sum(character.isalnum() for character in (text or "")) >= min_alnum_chars


def load_precise_engine_bundle(
    models_dir,
    *,
    logger,
    model_name=DEFAULT_PRECISE_MODEL_NAME,
    device_preference=None,
    progress_callback=None,
):
    if not precise_engine_available():
        status_ok, status_text = precise_engine_status(models_dir)
        raise RuntimeError(status_text if not status_ok else "Точный режим недоступен.")

    download_root = Path(models_dir) / "whisper-cache"
    download_root.mkdir(parents=True, exist_ok=True)
    cached_model_path = cached_precise_model_path(download_root, model_name)
    model_source = str(cached_model_path) if cached_model_path is not None else model_name

    errors = []
    load_started_at = time.perf_counter()
    attempt_plan = precise_engine_attempt_plan(device_preference)
    if any(device == "cuda" for device, _compute_type in attempt_plan):
        cuda_started_at = time.perf_counter()
        cuda_ready, cuda_details = prepare_cuda_runtime(logger=logger)
        logger.info(
            "Precise engine CUDA preparation finished in %.2f seconds. ready=%s",
            time.perf_counter() - cuda_started_at,
            cuda_ready,
        )
        if not cuda_ready:
            errors.append(f"cuda/runtime: {cuda_details}")
            attempt_plan = [
                attempt for attempt in attempt_plan if attempt[0] != "cuda"
            ]
    for attempt_index, (device, compute_type) in enumerate(attempt_plan, start=1):
        if progress_callback is not None:
            progress_callback(
                model_name,
                device,
                compute_type,
                attempt_index,
                len(attempt_plan),
            )
        logger.info(
            "Loading precise speaker engine. model=%s source=%s device=%s compute_type=%s download_root=%s",
            model_name,
            model_source,
            device,
            compute_type,
            download_root,
        )
        try:
            attempt_started_at = time.perf_counter()
            model = WhisperModel(
                model_source,
                device=device,
                compute_type=compute_type,
                download_root=str(download_root),
                local_files_only=cached_model_path is not None,
            )
            logger.info(
                "Precise engine model opened in %.2f seconds (total %.2f). local_snapshot=%s",
                time.perf_counter() - attempt_started_at,
                time.perf_counter() - load_started_at,
                cached_model_path is not None,
            )
            return PreciseEngineBundle(
                model=model,
                model_name=model_name,
                device=device,
                compute_type=compute_type,
                download_root=download_root,
            )
        except Exception as error:
            errors.append(f"{device}/{compute_type}: {error}")
            logger.warning(
                "Precise speaker engine init failed. device=%s compute_type=%s error=%s",
                device,
                compute_type,
                error,
            )

    raise RuntimeError(
        "Не удалось загрузить точный режим Whisper. "
        f"Проверенные варианты: {'; '.join(errors)}"
    )


class VoskRecognitionEngine:
    """Small adapter around KaldiRecognizer to isolate engine-specific logic."""

    def __init__(self, model, sample_rate, *, text_postprocessor):
        self._recognizer = KaldiRecognizer(model, sample_rate)
        self._recognizer.SetWords(True)
        self._text_postprocessor = text_postprocessor

    def consume_chunk(self, chunk):
        if self._recognizer.AcceptWaveform(chunk):
            result = json.loads(self._recognizer.Result())
            text = self._text_postprocessor((result.get("text") or "").strip(), log_changes=True)
            if text:
                return [RecognitionUpdate("final", text)]
            return []

        partial = self._text_postprocessor(
            json.loads(self._recognizer.PartialResult()).get("partial", "").strip()
        )
        return [RecognitionUpdate("partial", partial)]

    def consume_gap(self):
        return []

    def finalize(self):
        result = json.loads(self._recognizer.FinalResult())
        text = self._text_postprocessor((result.get("text") or "").strip(), log_changes=True)
        if text:
            return [RecognitionUpdate("final", text)]
        return []


class FasterWhisperBufferedEngine:
    """Buffered high-accuracy engine for the speaker channel."""

    def __init__(
        self,
        bundle,
        *,
        text_postprocessor,
        sample_rate=16000,
        flush_after_seconds=6.0,
        min_segment_seconds=0.7,
        context_chars=320,
        no_speech_reject_threshold=DEFAULT_NO_SPEECH_REJECT_THRESHOLD,
    ):
        self._bundle = bundle
        self._text_postprocessor = text_postprocessor
        self._sample_rate = sample_rate
        self._buffer = bytearray()
        self._flush_after_bytes = int(sample_rate * 2 * flush_after_seconds)
        self._min_segment_bytes = int(sample_rate * 2 * min_segment_seconds)
        self._context_chars = max(0, int(context_chars))
        filter_no_speech_segments((), no_speech_reject_threshold)
        self._no_speech_reject_threshold = no_speech_reject_threshold
        self._rejected_no_speech_segments = 0
        self._rejected_known_hallucinations = 0
        self._previous_text = ""
        self._logger = logging.getLogger("operator_assist")

    @property
    def rejected_no_speech_segments(self):
        return self._rejected_no_speech_segments

    @property
    def rejected_known_hallucinations(self):
        return self._rejected_known_hallucinations

    def consume_chunk(self, chunk):
        if chunk:
            self._buffer.extend(chunk)
        if len(self._buffer) >= self._flush_after_bytes:
            return self._flush_buffer()
        return []

    def consume_gap(self):
        if len(self._buffer) >= self._min_segment_bytes:
            return self._flush_buffer()
        if self._buffer:
            self._buffer.clear()
        return []

    def finalize(self):
        return self._flush_buffer(force=True)

    def _flush_buffer(self, force=False):
        if not self._buffer:
            return []

        if len(self._buffer) < self._min_segment_bytes and not force:
            return []

        audio = (
            np.frombuffer(bytes(self._buffer), dtype=np.int16).astype(np.float32)
            / 32768.0
        )
        self._buffer.clear()
        audio_seconds = len(audio) / float(self._sample_rate)
        started_at = time.perf_counter()

        segments, _info = self._bundle.model.transcribe(
            audio,
            language="ru",
            task="transcribe",
            beam_size=5,
            best_of=5,
            condition_on_previous_text=True,
            initial_prompt=self._previous_text or None,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 350},
            word_timestamps=False,
        )
        segments, rejected_segments = filter_no_speech_segments(
            segments,
            self._no_speech_reject_threshold,
        )
        if rejected_segments:
            self._rejected_no_speech_segments += len(rejected_segments)
            self._logger.info(
                "Whisper no-speech guard rejected segments. count=%s probabilities=%s total=%s",
                len(rejected_segments),
                ",".join(f"{probability:.3f}" for _segment, probability in rejected_segments),
                self._rejected_no_speech_segments,
            )
        segments, rejected_hallucinations = filter_known_metadata_hallucinations(
            segments
        )
        if rejected_hallucinations:
            self._rejected_known_hallucinations += len(rejected_hallucinations)
            self._logger.info(
                "Whisper known metadata hallucination suppressed. count=%s total=%s",
                len(rejected_hallucinations),
                self._rejected_known_hallucinations,
            )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        text = self._text_postprocessor(text.strip(), log_changes=True)
        if text and not is_meaningful_final_text(text):
            self._logger.info("Whisper short final fragment suppressed. chars=%s", len(text))
            text = ""
        elapsed = time.perf_counter() - started_at
        real_time_factor = elapsed / audio_seconds if audio_seconds else 0.0
        self._logger.info(
            "Whisper segment processed. audio=%.2fs inference=%.2fs rtf=%.2f chars=%s",
            audio_seconds,
            elapsed,
            real_time_factor,
            len(text),
        )
        if text:
            self._previous_text = text[-self._context_chars :] if self._context_chars else ""
            return [
                RecognitionUpdate(
                    "final",
                    text,
                    inference_seconds=elapsed,
                    trigger_reason="buffer",
                )
            ]
        return []
