"""Recognition-engine adapters used by the desktop runtime."""

import ctypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys

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


@dataclass(frozen=True)
class PreciseEngineBundle:
    model: object
    model_name: str
    device: str
    compute_type: str
    download_root: Path


def precise_engine_available():
    return FASTER_WHISPER_AVAILABLE and np is not None


def precise_engine_status(models_dir):
    if not FASTER_WHISPER_AVAILABLE:
        return False, f"faster-whisper не установлен: {FASTER_WHISPER_IMPORT_ERROR}"
    if np is None:
        return False, "numpy недоступен для точного режима."

    download_root = Path(models_dir) / "whisper-cache"
    if download_root.exists():
        return True, f"Точный режим готов. Кэш Whisper: {download_root}"

    return True, "Точный режим доступен. При первом запуске модель Whisper может загружаться дольше."


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


def precise_engine_attempt_plan():
    device = preferred_precise_device()
    if device == "cuda":
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


def load_precise_engine_bundle(
    models_dir,
    *,
    logger,
    model_name=DEFAULT_PRECISE_MODEL_NAME,
    progress_callback=None,
):
    if not precise_engine_available():
        status_ok, status_text = precise_engine_status(models_dir)
        raise RuntimeError(status_text if not status_ok else "Точный режим недоступен.")

    download_root = Path(models_dir) / "whisper-cache"
    download_root.mkdir(parents=True, exist_ok=True)

    errors = []
    attempt_plan = precise_engine_attempt_plan()
    if any(device == "cuda" for device, _compute_type in attempt_plan):
        cuda_ready, cuda_details = prepare_cuda_runtime(logger=logger)
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
            "Loading precise speaker engine. model=%s device=%s compute_type=%s download_root=%s",
            model_name,
            device,
            compute_type,
            download_root,
        )
        try:
            model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                download_root=str(download_root),
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
        flush_after_seconds=3.2,
        min_segment_seconds=0.55,
    ):
        self._bundle = bundle
        self._text_postprocessor = text_postprocessor
        self._sample_rate = sample_rate
        self._buffer = bytearray()
        self._flush_after_bytes = int(sample_rate * 2 * flush_after_seconds)
        self._min_segment_bytes = int(sample_rate * 2 * min_segment_seconds)

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

        segments, _info = self._bundle.model.transcribe(
            audio,
            language="ru",
            task="transcribe",
            beam_size=5,
            best_of=5,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 350},
            word_timestamps=False,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        text = self._text_postprocessor(text.strip(), log_changes=True)
        if text:
            return [RecognitionUpdate("final", text)]
        return []
