"""Canonical base desktop runtime for OPERATOR_ASSIST."""

import audioop
from collections import deque
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import sounddevice as sd
from vosk import KaldiRecognizer, Model

from operator_assist_runtime.technical_terms import (
    TechnicalTermsManager,
    serialize_terms_payload,
)
from operator_assist_runtime.runtime_paths import application_root
from operator_assist_runtime.text_utils import (
    are_exact_duplicates as shared_are_exact_duplicates,
    are_similar_duplicates as shared_are_similar_duplicates,
    normalize_name as shared_normalize_name,
    short_text as shared_short_text,
)


APP_TITLE = "OPERATOR_ASSIST Operator Assist"
APP_VERSION = "2026-07-09-chat1"
BASE_DIR = application_root(__file__, levels_up=1)
SETTINGS_PATH = BASE_DIR / "operator_assist_settings.json"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
PROMPT_TEMPLATE_PATH = BASE_DIR / "chatgpt_prompt_template.txt"
BRIDGE_SCRIPT_PATH = BASE_DIR / "scripts" / "paste_to_chat_window.vbs"
TECHNICAL_TERMS_PATH = BASE_DIR / "technical_terms.json"
ASSETS_DIR = BASE_DIR / "assets"
APP_LOGO_PATH = ASSETS_DIR / "logo-enot.png"
APP_LOGO_SMALL_PATH = ASSETS_DIR / "logo-enot-72.png"
APP_LOGO_LARGE_PATH = ASSETS_DIR / "logo-enot-128.png"
APP_ICON_PATH = ASSETS_DIR / "operator_assist.ico"
RUN_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
TARGET_SAMPLE_RATE = 16000
AUDIO_BLOCK_MS = 250
EXACT_DUPLICATE_WINDOW_SEC = 1.2
EXACT_DUPLICATE_MIN_CHARS = 12
SIMILAR_DUPLICATE_WINDOW_SEC = 1.8
SIMILAR_DUPLICATE_MIN_CHARS = 16
SIMILAR_DUPLICATE_RATIO = 0.84
LEVEL_METER_RMS_CEILING = 5000
CHATGPT_URL = "https://chatgpt.com/"
CHAT_CONTEXT_CHARS = 1400
CHAT_FULL_CHARS = 2200

MODEL_CANDIDATES = [
    BASE_DIR / "models" / "vosk-model-ru-0.42",
    BASE_DIR / "models" / "vosk-model-ru-0.22",
    BASE_DIR / "models" / "vosk-model-small-ru-0.22",
]


def models_root():
    return BASE_DIR / "models"


def supported_model_names():
    return [candidate.name for candidate in MODEL_CANDIDATES]


def default_technical_terms_payload():
    return {'enabled': True, 'description': '????????????? ??????? ????-????????? ??? ??????????? ????????. ????? ? ??? ????????????? ????? ?????????, ???????? ? ??? ????? ?????????.', 'replacements': {'?? ??': 'IP', '????': 'Sass', '???': 'Bash', '?? ?? ??': 'CSS', '???? ???': 'FastAPI', '???????': 'Grafana', '??? ?????': 'Bitbucket', '????????': 'Tailwind', '???? ??? ???': 'GraphQL', '??????': 'Webpack', '??? ???': 'GitLab', '??? ?? ???': 'XML', '? ???': 'OAuth', '?? ?? ?? ??': 'SCSS', '???? ???? ? ??': 'JWT', '??? ???? ? ??': 'JWT', '?? ??? ???': 'SQL', '?? ?? ???': 'SSL', '?? ???': 'LDAP', '?? ????': 'C#', '? ?? ??': 'UDP', '?????': 'Apache', '????? ??????': 'JavaScript', '???????????': 'Elasticsearch', '???? ??????': 'TypeScript', '??????????': 'Kubernetes', '?? ???? ????': 'C++', '?????? ????': 'C++', '??? ??? ???': 'ASP.NET', '??? ??? ??': 'Node.js', '???? ??? ??': 'NestJS', '???? ?????': 'NestJS', '????? ??? ??': 'Next.js', '????? ?????': 'Next.js', '??? ???? ??': 'Vue.js', '?????? ???': 'Spring Boot', '?????????': 'Terraform', '???????? ??? ???': 'PostgreSQL', '?????????????': 'PostgreSQL', '??? ????????': 'MySQL', '??? ?? ??? ???': 'MySQL', '?? ??? ????': 'SQLite', '????? ??': 'MongoDB', '??????? ????': 'Elasticsearch', '?????? ?? ???': 'RabbitMQ', '????? ???????': 'Docker Compose', '?? ???? ???': 'Nginx', '??????? ??????': 'Windows Server', '????? ?????????': 'Active Directory', '??? ????': 'TeamCity', '????? ????': 'PowerShell', '??? ?? ?? ???': 'HTML'}}


def default_technical_terms_content():
    return serialize_terms_payload(default_technical_terms_payload())


def resolve_logs_dir():
    temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or "C:\\tmp")
    candidates = [
        BASE_DIR / "logs",
        temp_root / "OPERATOR_ASSIST_logs",
    ]

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            continue

    return temp_root


LOGS_DIR = resolve_logs_dir()
LOG_PATH = LOGS_DIR / f"operator_assist_{RUN_TIMESTAMP}.log"


def setup_logging():
    global LOGS_DIR, LOG_PATH

    logger = logging.getLogger("operator_assist")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(threadName)s %(message)s")
    handler = None

    candidate_paths = [LOG_PATH]
    temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or "C:\\tmp")
    fallback_dir = temp_root / "OPERATOR_ASSIST_logs"
    fallback_path = fallback_dir / f"operator_assist_{RUN_TIMESTAMP}.log"
    if fallback_path not in candidate_paths:
        candidate_paths.append(fallback_path)

    for candidate_path in candidate_paths:
        try:
            candidate_path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(candidate_path, encoding="utf-8")
            LOGS_DIR = candidate_path.parent
            LOG_PATH = candidate_path
            break
        except Exception:
            continue

    if handler is None:
        handler = logging.NullHandler()

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.propagate = False
    logger.info("Application boot. version=%s", APP_VERSION)
    logger.info("Base dir=%s", BASE_DIR)
    logger.info("Settings path=%s", SETTINGS_PATH)
    logger.info("Transcripts dir=%s", TRANSCRIPTS_DIR)
    logger.info("Logs dir=%s", LOGS_DIR)
    logger.info("Log file=%s", LOG_PATH)
    logger.info("Assets dir=%s", ASSETS_DIR)
    logger.info("Model candidates=%s", [str(path) for path in MODEL_CANDIDATES])
    logger.info("Technical terms path=%s", TECHNICAL_TERMS_PATH)
    return logger


LOGGER = setup_logging()


def install_exception_logging():
    def log_exception(prefix, exc_type, exc_value, exc_traceback):
        if exc_type and issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        LOGGER.error("%s\n%s", prefix, details)

    sys.excepthook = lambda exc_type, exc_value, exc_traceback: log_exception(
        "Unhandled exception in main thread",
        exc_type,
        exc_value,
        exc_traceback,
    )

    if hasattr(threading, "excepthook"):
        def thread_excepthook(args):
            thread_name = args.thread.name if args.thread else "unknown"
            log_exception(
                f"Unhandled exception in thread {thread_name}",
                args.exc_type,
                args.exc_value,
                args.exc_traceback,
            )

        threading.excepthook = thread_excepthook


install_exception_logging()


def ensure_text_file(path, content):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            LOGGER.info("Created helper file: %s", path)
    except Exception:
        LOGGER.exception("Failed to create helper file: %s", path)


def default_prompt_template():
    return (
        "Ты помощник оператора службы поддержки.\n"
        "Работай только с текстом клиента ниже.\n"
        "Не выдумывай факты, правила компании, сроки, тарифы и технические детали.\n"
        "Если данных не хватает, прямо напиши, что нужно уточнить у клиента.\n"
        "Ответ дай по-русски и кратко в формате:\n"
        "1. Суть обращения\n"
        "2. Что сказать клиенту сейчас\n"
        "3. Что уточнить у клиента\n"
        "4. Следующий шаг оператора\n\n"
        "Контекст предыдущих реплик клиента:\n"
        "{context}\n\n"
        "Новый фрагмент речи клиента:\n"
        "{latest}\n\n"
        "Если полезно, вот недавний полный фрагмент клиента:\n"
        "{full}\n"
    )


def bridge_script_content():
    return (
        'Set wsh = CreateObject("WScript.Shell")\n'
        'windowTitle = WScript.Arguments(0)\n'
        'pressEnter = LCase(WScript.Arguments(1))\n'
        'If wsh.AppActivate(windowTitle) Then\n'
        '  WScript.Sleep 350\n'
        '  wsh.SendKeys "^v"\n'
        '  WScript.Sleep 150\n'
        '  If pressEnter = "true" Then\n'
        '    wsh.SendKeys "{ENTER}"\n'
        '  End If\n'
        '  WScript.Quit 0\n'
        'Else\n'
        '  WScript.Quit 1\n'
        'End If\n'
    )


ensure_text_file(PROMPT_TEMPLATE_PATH, default_prompt_template())
ensure_text_file(BRIDGE_SCRIPT_PATH, bridge_script_content())


def load_prompt_template():
    try:
        return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    except Exception:
        LOGGER.exception("Failed to load prompt template, using default")
        return default_prompt_template()


def find_existing_models():
    return [candidate for candidate in MODEL_CANDIDATES if candidate.exists()]


def normalize_name(value):
    return shared_normalize_name(value)


def short_text(value, limit=220):
    return shared_short_text(value, limit=limit)


def default_models_help_content():
    supported = "\n".join(f"- {name}" for name in supported_model_names())
    return (
        "Папка моделей Vosk для OPERATOR_ASSIST\n\n"
        "Сюда нужно распаковать русскую модель распознавания.\n"
        "Поддерживаемые имена папок:\n"
        f"{supported}\n\n"
        "Что делать:\n"
        "1. Скачайте подходящую модель.\n"
        "2. Распакуйте ее целиком прямо в папку models.\n"
        "3. Вернитесь в приложение и нажмите Проверить снова.\n\n"
        "Важно:\n"
        "- не оставляйте модель внутри zip-архива;\n"
        "- не делайте лишнюю вложенную папку;\n"
        "- имя итоговой папки должно совпадать с одним из вариантов выше.\n"
    )


def build_startup_summary(
    *,
    model_loading,
    active_model_name,
    existing_model_names,
    model_error_text,
    mic_selected,
    speaker_selected,
    settings_exists,
    workers_active=False,
    settings_file_name="operator_assist_settings.json",
):
    existing_model_names = [name.strip() for name in existing_model_names if name and name.strip()]
    model_ready = bool(active_model_name)
    mic_ready = bool((mic_selected or "").strip())
    speaker_ready = bool((speaker_selected or "").strip())
    waiting_model = bool(model_loading and not model_ready)

    if model_ready:
        model_line = f"OK: модель {active_model_name} загружена."
    elif waiting_model and existing_model_names:
        model_line = f"Ждите: модель загружается ({', '.join(existing_model_names[:2])})."
    elif model_error_text:
        model_line = f"Ошибка: модель не открылась ({short_text(model_error_text, 110)})."
    else:
        model_line = "Нужно: положите в папку models одну из поддерживаемых русских моделей Vosk."

    if mic_ready:
        mic_line = f"OK: микрофон выбран ({short_text(mic_selected, 72)})."
    else:
        mic_line = "Нужно: выберите микрофон оператора."

    if speaker_ready:
        speaker_line = f"OK: источник собеседника выбран ({short_text(speaker_selected, 72)})."
    else:
        speaker_line = "Нужно: выберите источник собеседника или системного звука."

    if settings_exists:
        settings_line = f"OK: настройки сохраняются в {settings_file_name}."
    else:
        settings_line = f"Совет: файл {settings_file_name} появится после первого сохранения настроек."

    if workers_active:
        title = "Сеанс уже запущен"
        hint = "Стартовые проверки пройдены. Следите за уровнями сигнала и диагностикой аудио."
    elif model_error_text:
        title = "Ошибка загрузки модели"
        hint = "Проверьте содержимое папки models, затем нажмите Проверить снова. Подробности есть в логах."
    elif not existing_model_names and not model_ready:
        title = "Нужна модель распознавания"
        hint = "Откройте папку models и распакуйте туда русскую модель Vosk. После этого нажмите Проверить снова."
    elif waiting_model:
        title = "Загружаю модель"
        hint = "Большая модель может открываться заметно дольше. Кнопка Старт включится автоматически."
    elif not mic_ready or not speaker_ready:
        title = "Проверьте источники звука"
        hint = "Выберите оба канала. После этого можно сразу запускать распознавание."
    elif model_ready:
        title = "Готово к запуску"
        hint = "Можно нажимать Старт. Если дорожки будут пересекаться, посмотрите блок диагностики аудио."
    else:
        title = "Подготовка первого запуска"
        hint = "Проверяю модель, устройства и сохраненные настройки."

    return {
        "title": title,
        "hint": hint,
        "model_line": model_line,
        "mic_line": mic_line,
        "speaker_line": speaker_line,
        "settings_line": settings_line,
        "ready": model_ready and mic_ready and speaker_ready and not model_loading and not workers_active,
    }


_TECHNICAL_TERMS_MANAGER = TechnicalTermsManager(
    get_terms_path=lambda: TECHNICAL_TERMS_PATH,
    get_logger=lambda: LOGGER,
    normalize_name=normalize_name,
    short_text=short_text,
    default_payload_factory=default_technical_terms_payload,
)


def load_technical_terms(force=False):
    payload = _TECHNICAL_TERMS_MANAGER.load(force=force)
    replacements, pattern = _TECHNICAL_TERMS_MANAGER.resolve_active_terms(active_modes=())
    return payload.get("enabled", True), replacements, pattern


def get_available_technical_modes():
    return _TECHNICAL_TERMS_MANAGER.get_available_modes()


def set_active_technical_modes(modes):
    return _TECHNICAL_TERMS_MANAGER.set_active_modes(modes)


def get_active_technical_modes():
    return _TECHNICAL_TERMS_MANAGER.get_active_modes()


def resolve_active_technical_terms(active_modes=None):
    return _TECHNICAL_TERMS_MANAGER.resolve_active_terms(active_modes=active_modes)


def apply_technical_term_replacements(text, log_changes=False):
    return _TECHNICAL_TERMS_MANAGER.apply(text, log_changes=log_changes, active_modes=())


def are_exact_duplicates(left, right):
    return shared_are_exact_duplicates(left, right, min_chars=EXACT_DUPLICATE_MIN_CHARS)


def are_similar_duplicates(left, right):
    return shared_are_similar_duplicates(
        left,
        right,
        min_chars=SIMILAR_DUPLICATE_MIN_CHARS,
        ratio=SIMILAR_DUPLICATE_RATIO,
    )


def pcm16_level_percent(chunk, *, ceiling=LEVEL_METER_RMS_CEILING):
    if not chunk:
        return 0

    try:
        rms = audioop.rms(chunk, 2)
    except Exception:
        LOGGER.exception("Failed to compute PCM RMS level")
        return 0

    if rms <= 0:
        return 0

    bounded = min(int(rms), int(ceiling))
    return max(0, min(100, int(round((bounded / float(ceiling)) * 100))))


def format_channel_count(count):
    if not count:
        return ""
    count = int(count)
    return f"{count} кан." if count > 1 else "1 канал"


def find_chrome_exe():
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


class TranscriptionWorker:
    def __init__(self, label, model, device_id, ui_queue):
        self.label = label
        self.model = model
        self.device_id = device_id
        self.ui_queue = ui_queue
        self.audio_queue = queue.Queue(maxsize=32)
        self.thread = None
        self.stream = None
        self.stop_event = threading.Event()
        self.input_samplerate = TARGET_SAMPLE_RATE
        self.channels = 1
        self.rate_state = None
        self.device_name = ""
        self.drop_count = 0
        self.callback_warning_count = 0
        self.chunk_count = 0
        self.last_level_percent = 0

    def start(self):
        LOGGER.info("[%s] Starting worker for device_id=%s", self.label, self.device_id)

        device_info = sd.query_devices(self.device_id, "input")
        self.input_samplerate = int(device_info["default_samplerate"])
        self.channels = 1
        self.device_name = device_info["name"]
        blocksize = max(1024, int(self.input_samplerate * AUDIO_BLOCK_MS / 1000))

        LOGGER.info(
            "[%s] Device info name=%s sample_rate=%s requested_channels=%s max_input_channels=%s blocksize=%s target_rate=%s",
            self.label,
            self.device_name,
            self.input_samplerate,
            self.channels,
            int(device_info["max_input_channels"]),
            blocksize,
            TARGET_SAMPLE_RATE,
        )

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run_recognition,
            daemon=True,
            name=f"Recognizer-{self.label}",
        )
        self.thread.start()

        self.stream = sd.RawInputStream(
            samplerate=self.input_samplerate,
            blocksize=blocksize,
            device=self.device_id,
            dtype="int16",
            channels=self.channels,
            callback=self._audio_callback,
        )
        self.stream.start()

        self.ui_queue.put(("status", self.label, f"Слушаю: {self.device_name}"))

    def stop(self):
        LOGGER.info("[%s] Stopping worker", self.label)
        self.stop_event.set()

        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                LOGGER.exception("[%s] Failed to stop audio stream", self.label)
            self.stream = None

        if self.thread is not None:
            self.thread.join(timeout=1.5)
            if self.thread.is_alive():
                LOGGER.warning("[%s] Recognizer thread is still alive after timeout", self.label)
            self.thread = None

        LOGGER.info(
            "[%s] Worker stopped. chunks=%s drops=%s callback_warnings=%s",
            self.label,
            self.chunk_count,
            self.drop_count,
            self.callback_warning_count,
        )
        self.ui_queue.put(("status", self.label, "Остановлено"))

    def _emit_level(self, chunk):
        level_percent = pcm16_level_percent(chunk)
        self.last_level_percent = level_percent
        self.ui_queue.put(("level", self.label, level_percent))

    def _audio_callback(self, indata, frames, callback_time, status):
        if status:
            self.callback_warning_count += 1
            LOGGER.warning("[%s] Audio callback status=%s", self.label, status)
            self.ui_queue.put(("hint", f"{self.label}: {status}"))

        chunk = bytes(indata)

        if self.input_samplerate != TARGET_SAMPLE_RATE:
            chunk, self.rate_state = audioop.ratecv(
                chunk,
                2,
                1,
                self.input_samplerate,
                TARGET_SAMPLE_RATE,
                self.rate_state,
            )

        if not self.stop_event.is_set() and chunk:
            self.chunk_count += 1
            self._emit_level(chunk)
            try:
                self.audio_queue.put_nowait(chunk)
            except queue.Full:
                self.drop_count += 1

                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    pass

                try:
                    self.audio_queue.put_nowait(chunk)
                except queue.Full:
                    pass

                if self.drop_count <= 3 or self.drop_count % 10 == 0:
                    LOGGER.warning(
                        "[%s] Audio queue overflow. drops=%s queue_size=%s",
                        self.label,
                        self.drop_count,
                        self.audio_queue.qsize(),
                    )

    def _run_recognition(self):
        LOGGER.info("[%s] Recognizer thread started", self.label)

        try:
            recognizer = KaldiRecognizer(self.model, TARGET_SAMPLE_RATE)
            recognizer.SetWords(True)

            while not self.stop_event.is_set():
                try:
                    chunk = self.audio_queue.get(timeout=0.25)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(chunk):
                    result = json.loads(recognizer.Result())
                    text = apply_technical_term_replacements((result.get("text") or "").strip(), log_changes=True)
                    if text:
                        LOGGER.info("[%s] Final text: %s", self.label, short_text(text, 400))
                        self.ui_queue.put(("final", self.label, text, time.monotonic()))
                else:
                    partial = apply_technical_term_replacements(json.loads(recognizer.PartialResult()).get("partial", "").strip())
                    self.ui_queue.put(("partial", self.label, partial))

            final_result = json.loads(recognizer.FinalResult())
            final_text = apply_technical_term_replacements((final_result.get("text") or "").strip(), log_changes=True)
            if final_text:
                LOGGER.info("[%s] Final tail text: %s", self.label, short_text(final_text, 400))
                self.ui_queue.put(("final", self.label, final_text, time.monotonic()))
        except Exception:
            LOGGER.exception("[%s] Recognizer thread crashed", self.label)
            self.ui_queue.put(("hint", f"{self.label}: ошибка распознавания, детали в логе"))
        finally:
            LOGGER.info("[%s] Recognizer thread finished", self.label)


class OperatorAssistApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1400x980")
        self.root.minsize(1180, 780)
        self.root.report_callback_exception = self._report_callback_exception

        self.model = None
        self.model_loading = False
        self.active_model_dir = None
        self.model_error_text = ""
        self.model_load_interactive = False
        self._ensure_runtime_helper_files()
        self.ui_queue = queue.Queue()
        self.workers = {}
        self.devices = self._load_input_devices()
        self.settings = self._load_settings()
        self.recent_speaker_finals = deque()
        self.last_sent_speaker_chars = 0
        self.pending_prompt_snapshot_len = 0

        self.mic_device_var = tk.StringVar()
        self.speaker_device_var = tk.StringVar()
        self.chrome_window_var = tk.StringVar(value=self.settings.get("chrome_window_keyword", "ChatGPT"))
        self.auto_enter_var = tk.BooleanVar(value=bool(self.settings.get("chrome_auto_enter", False)))
        self.status_var = tk.StringVar(value="Подготовка окна")
        self.hint_var = tk.StringVar(value="Окно открыто. Подождите, модель загружается в фоне.")
        self.ai_hint_var = tk.StringVar(value="Мост к ChatGPT выключен до нажатия кнопок. На распознавание он не влияет.")
        self.my_partial_var = tk.StringVar(value="Пока пусто")
        self.speaker_partial_var = tk.StringVar(value="Пока пусто")
        self.setup_title_var = tk.StringVar(value="Подготовка первого запуска")
        self.setup_hint_var = tk.StringVar(value="Проверяю модель, устройства и сохраненные настройки.")
        self.setup_model_var = tk.StringVar(value="Ждите: проверяю наличие модели.")
        self.setup_mic_var = tk.StringVar(value="Ждите: проверяю микрофон.")
        self.setup_speaker_var = tk.StringVar(value="Ждите: проверяю источник собеседника.")
        self.setup_settings_var = tk.StringVar(value="Совет: настройки появятся после первого сохранения.")
        self.mic_source_var = tk.StringVar(value="Источник: не выбран")
        self.speaker_source_var = tk.StringVar(value="Источник: не выбран")
        self.mic_signal_var = tk.StringVar(value="Сигнал: тишина")
        self.speaker_signal_var = tk.StringVar(value="Сигнал: тишина")
        self.mic_level_var = tk.IntVar(value=0)
        self.speaker_level_var = tk.IntVar(value=0)
        self.route_diag_var = tk.StringVar(
            value="Диагностика: выберите источники и дождитесь загрузки модели."
        )
        self.channel_overlap_warning_active = False
        self.last_overlap_warning_at = 0.0
        self.recent_mic_finals = deque()
        self._brand_logo_image = None
        self._brand_icon_images = []

        LOGGER.info("UI initialized. devices=%s", len(self.devices))

        self._apply_window_branding()
        self._build_ui()
        self._apply_default_devices()
        self._poll_ui_queue()
        self._refresh_startup_readiness()
        self._update_start_button_state()
        self.root.after(120, lambda: self._start_model_loading(interactive=False))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        self.root.configure(bg="#f3f6f9")

        wrapper = tk.Frame(self.root, bg="#f3f6f9")
        wrapper.pack(fill="both", expand=True, padx=18, pady=18)

        self._build_branded_header(
            wrapper,
            subtitle_text="Одновременное распознавание вашего микрофона и речи собеседника через Стерео микшер",
        )
        self._build_startup_readiness(wrapper)

        controls = tk.Frame(wrapper, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        controls.pack(fill="x", pady=(0, 12))
        controls.configure(padx=16, pady=16)

        tk.Label(controls, text="Мой микрофон", bg="white", fg="#5f7184", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        tk.Label(controls, text="Собеседник / системный звук", bg="white", fg="#5f7184", font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w", padx=(16, 0))

        self.mic_combo = ttk.Combobox(controls, textvariable=self.mic_device_var, state="readonly", width=48)
        self.mic_combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.speaker_combo = ttk.Combobox(controls, textvariable=self.speaker_device_var, state="readonly", width=48)
        self.speaker_combo.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=(6, 0))
        self._bind_device_selection_diagnostics()

        buttons = tk.Frame(controls, bg="white")
        buttons.grid(row=1, column=2, padx=(16, 0), sticky="e")

        self.start_button = tk.Button(buttons, text="Старт", command=self.start_transcription, bg="#0f766e", fg="white", relief="flat", padx=16, pady=10, state="disabled")
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = tk.Button(buttons, text="Стоп", command=self.stop_transcription, bg="#e7eef5", fg="#17324d", relief="flat", padx=16, pady=10, state="disabled")
        self.stop_button.pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Обновить устройства", command=self.refresh_devices, bg="#e7eef5", fg="#17324d", relief="flat", padx=16, pady=10).pack(side="left")

        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)

        self._build_audio_diagnostics(wrapper)

        action_bar = tk.Frame(wrapper, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        action_bar.pack(fill="x", pady=(0, 12))
        action_bar.configure(padx=16, pady=12)

        tk.Label(action_bar, textvariable=self.status_var, bg="white", fg="#0f766e", font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Label(action_bar, textvariable=self.hint_var, bg="white", fg="#5f7184", font=("Segoe UI", 10)).pack(side="left", padx=(18, 0))

        actions_right = tk.Frame(action_bar, bg="white")
        actions_right.pack(side="right")
        tk.Button(actions_right, text="Копировать собеседника", command=self.copy_speaker_text, bg="#fff4df", fg="#5b4611", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions_right, text="Копировать всё", command=self.copy_all_text, bg="#eef6ff", fg="#17406d", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions_right, text="Сохранить TXT", command=self.save_transcript, bg="#e8f8f2", fg="#0b5d4f", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions_right, text="Открыть логи", command=self.open_logs_folder, bg="#f3efff", fg="#4b2d8d", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions_right, text="Очистить", command=self.clear_text, bg="#fdebec", fg="#8a2f39", relief="flat", padx=12, pady=8).pack(side="left")

        panel_grid = tk.Frame(wrapper, bg="#f3f6f9")
        panel_grid.pack(fill="both", expand=True)
        panel_grid.grid_columnconfigure(0, weight=1)
        panel_grid.grid_columnconfigure(1, weight=1)
        panel_grid.grid_rowconfigure(0, weight=1)

        self.my_text = self._build_panel(panel_grid, 0, "Я / оператор", self.my_partial_var)
        self.speaker_text = self._build_panel(panel_grid, 1, "Собеседник", self.speaker_partial_var)

        self._build_chat_bridge(wrapper)

    def _ensure_runtime_helper_files(self):
        ensure_text_file(PROMPT_TEMPLATE_PATH, default_prompt_template())
        ensure_text_file(BRIDGE_SCRIPT_PATH, bridge_script_content())
        ensure_text_file(TECHNICAL_TERMS_PATH, default_technical_terms_content())
        ensure_text_file(models_root() / "README.txt", default_models_help_content())

    def _build_startup_readiness(self, parent):
        card = tk.Frame(parent, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        card.pack(fill="x", pady=(0, 12))
        card.configure(padx=16, pady=14)
        card.grid_columnconfigure(0, weight=1)

        header = tk.Frame(card, bg="white")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        text_box = tk.Frame(header, bg="white")
        text_box.grid(row=0, column=0, sticky="w")

        tk.Label(
            text_box,
            textvariable=self.setup_title_var,
            bg="white",
            fg="#17324d",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            text_box,
            textvariable=self.setup_hint_var,
            bg="white",
            fg="#5f7184",
            font=("Segoe UI", 10),
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        buttons = tk.Frame(header, bg="white")
        buttons.grid(row=0, column=1, sticky="e", padx=(16, 0))
        tk.Button(
            buttons,
            text="Папка models",
            command=self.open_models_folder,
            bg="#eef6ff",
            fg="#17406d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons,
            text="Папка приложения",
            command=self.open_application_folder,
            bg="#f6f8fb",
            fg="#17324d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons,
            text="Проверить снова",
            command=self.refresh_startup_checks,
            bg="#e8f8f2",
            fg="#0b5d4f",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left")

        checklist = tk.Frame(card, bg="#f8fbfd", highlightbackground="#e3ebf3", highlightthickness=1)
        checklist.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        checklist.grid_columnconfigure(1, weight=1)
        checklist.configure(padx=12, pady=12)

        self._build_startup_row(checklist, 0, "Модель", self.setup_model_var)
        self._build_startup_row(checklist, 1, "Микрофон", self.setup_mic_var)
        self._build_startup_row(checklist, 2, "Собеседник", self.setup_speaker_var)
        self._build_startup_row(checklist, 3, "Настройки", self.setup_settings_var)

    def _build_startup_row(self, parent, row, title, value_var):
        tk.Label(
            parent,
            text=title,
            bg="#f8fbfd",
            fg="#17324d",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=(0 if row == 0 else 8, 0))
        tk.Label(
            parent,
            textvariable=value_var,
            bg="#f8fbfd",
            fg="#5f7184",
            font=("Segoe UI", 10),
            justify="left",
            wraplength=980,
        ).grid(row=row, column=1, sticky="w", pady=(0 if row == 0 else 8, 0))

    def _build_panel(self, parent, column, title, partial_var):
        panel = tk.Frame(parent, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        panel.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 8 if column == 0 else 0))
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        tk.Label(panel, text=title, bg="white", fg="#17324d", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))

        text_widget = ScrolledText(panel, wrap="word", font=("Segoe UI", 11), undo=True)
        text_widget.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))

        tk.Label(panel, textvariable=partial_var, bg="#f8fbfd", fg="#5f7184", anchor="w", justify="left", wraplength=580, padx=12, pady=10).grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        return text_widget

    def _build_chat_bridge(self, parent):
        bridge = tk.Frame(parent, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        bridge.pack(fill="both", pady=(12, 0))
        bridge.configure(padx=16, pady=16)
        bridge.grid_columnconfigure(0, weight=1)

        tk.Label(bridge, text="ChatGPT Bridge", bg="white", fg="#17324d", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(bridge, textvariable=self.ai_hint_var, bg="white", fg="#5f7184", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=(4, 12))

        controls = tk.Frame(bridge, bg="white")
        controls.grid(row=2, column=0, sticky="ew")
        controls.grid_columnconfigure(1, weight=1)

        tk.Label(controls, text="Заголовок окна Chrome", bg="white", fg="#5f7184", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        tk.Entry(controls, textvariable=self.chrome_window_var, width=24).grid(row=0, column=1, sticky="w", padx=(10, 10))
        tk.Checkbutton(controls, text="Нажимать Enter после вставки", variable=self.auto_enter_var, bg="white", activebackground="white").grid(row=0, column=2, sticky="w")

        buttons_top = tk.Frame(bridge, bg="white")
        buttons_top.grid(row=3, column=0, sticky="w", pady=(12, 8))
        tk.Button(buttons_top, text="Собрать новое", command=self.prepare_chat_prompt_delta, bg="#eef6ff", fg="#17406d", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(buttons_top, text="Собрать всё", command=self.prepare_chat_prompt_full, bg="#eef6ff", fg="#17406d", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(buttons_top, text="Копировать запрос", command=self.copy_chat_prompt, bg="#fff4df", fg="#5b4611", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(buttons_top, text="Отправить в Chrome", command=self.send_chat_prompt_to_chrome, bg="#e8f8f2", fg="#0b5d4f", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(buttons_top, text="Открыть ChatGPT", command=self.open_chatgpt_in_chrome, bg="#f3efff", fg="#4b2d8d", relief="flat", padx=12, pady=8).pack(side="left")

        buttons_bottom = tk.Frame(bridge, bg="white")
        buttons_bottom.grid(row=4, column=0, sticky="w", pady=(0, 10))
        tk.Button(buttons_bottom, text="Открыть шаблон", command=self.open_prompt_template, bg="#f6f8fb", fg="#17324d", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(buttons_bottom, text="Сбросить метку отправки", command=self.reset_chat_send_marker, bg="#fdebec", fg="#8a2f39", relief="flat", padx=12, pady=8).pack(side="left")

        self.ai_prompt_text = ScrolledText(bridge, wrap="word", font=("Consolas", 10), height=12, undo=True)
        self.ai_prompt_text.grid(row=5, column=0, sticky="nsew")

    def _load_brand_photo(self, path):
        if not path.exists():
            return None
        try:
            return tk.PhotoImage(file=str(path))
        except Exception:
            LOGGER.exception("Failed to load brand image: %s", path)
            return None

    def _apply_window_branding(self):
        icon_images = []
        for path in (APP_LOGO_SMALL_PATH, APP_LOGO_LARGE_PATH):
            image = self._load_brand_photo(path)
            if image is not None:
                icon_images.append(image)

        self._brand_icon_images = icon_images
        self._brand_logo_image = icon_images[0] if icon_images else self._load_brand_photo(APP_LOGO_PATH)

        if APP_ICON_PATH.exists():
            try:
                self.root.iconbitmap(default=str(APP_ICON_PATH))
            except Exception:
                LOGGER.exception("Failed to apply iconbitmap from %s", APP_ICON_PATH)

        if icon_images:
            try:
                self.root.iconphoto(True, *icon_images)
            except Exception:
                LOGGER.exception("Failed to apply iconphoto branding")

    def _build_branded_header(self, parent, *, subtitle_text):
        header = tk.Frame(parent, bg="#f3f6f9")
        header.pack(fill="x", pady=(0, 12))

        row = tk.Frame(header, bg="#f3f6f9")
        row.pack(fill="x")

        if self._brand_logo_image is not None:
            tk.Label(
                row,
                image=self._brand_logo_image,
                bg="#f3f6f9",
            ).pack(side="left", padx=(0, 14))

        text_block = tk.Frame(row, bg="#f3f6f9")
        text_block.pack(side="left", fill="x", expand=True)

        tk.Label(
            text_block,
            text="Operator Assist",
            font=("Segoe UI", 24, "bold"),
            bg="#f3f6f9",
            fg="#17324d",
        ).pack(anchor="w")

        tk.Label(
            text_block,
            text=subtitle_text,
            font=("Segoe UI", 11),
            bg="#f3f6f9",
            fg="#5f7184",
        ).pack(anchor="w", pady=(2, 0))

        return header

    def _refresh_startup_readiness(self):
        summary = build_startup_summary(
            model_loading=self.model_loading,
            active_model_name=self._current_model_name() if self.active_model_dir is not None else "",
            existing_model_names=[path.name for path in find_existing_models()],
            model_error_text=self.model_error_text,
            mic_selected=self.mic_device_var.get().strip(),
            speaker_selected=self.speaker_device_var.get().strip(),
            settings_exists=SETTINGS_PATH.exists(),
            workers_active=bool(self.workers),
            settings_file_name=SETTINGS_PATH.name,
        )
        self.setup_title_var.set(summary["title"])
        self.setup_hint_var.set(summary["hint"])
        self.setup_model_var.set(summary["model_line"])
        self.setup_mic_var.set(summary["mic_line"])
        self.setup_speaker_var.set(summary["speaker_line"])
        self.setup_settings_var.set(summary["settings_line"])

    def _can_start_transcription(self):
        return (
            not self.model_loading
            and self.model is not None
            and not self.workers
            and self._selected_mic_device() is not None
            and self._selected_speaker_source() is not None
        )

    def _update_start_button_state(self):
        if hasattr(self, "start_button"):
            self.start_button.configure(state="normal" if self._can_start_transcription() else "disabled")

    def _build_audio_diagnostics(self, parent):
        diagnostics = tk.Frame(
            parent,
            bg="white",
            highlightbackground="#d9e2ec",
            highlightthickness=1,
        )
        diagnostics.pack(fill="x", pady=(0, 12))
        diagnostics.configure(padx=16, pady=14)
        diagnostics.grid_columnconfigure(0, weight=1)
        diagnostics.grid_columnconfigure(1, weight=1)

        tk.Label(
            diagnostics,
            text="Диагностика аудио",
            bg="white",
            fg="#17324d",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            diagnostics,
            text="Ниже видно, какой источник выбран для каждого канала и есть ли по нему живой сигнал.",
            bg="white",
            fg="#5f7184",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        self._build_audio_channel_card(
            diagnostics,
            column=0,
            title="Микрофон / оператор",
            source_var=self.mic_source_var,
            signal_var=self.mic_signal_var,
            level_var=self.mic_level_var,
        )
        self._build_audio_channel_card(
            diagnostics,
            column=1,
            title="Собеседник / системный звук",
            source_var=self.speaker_source_var,
            signal_var=self.speaker_signal_var,
            level_var=self.speaker_level_var,
            padx=(12, 0),
        )

        tk.Label(
            diagnostics,
            textvariable=self.route_diag_var,
            bg="white",
            fg="#5f7184",
            font=("Segoe UI", 10),
            wraplength=1100,
            justify="left",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def _build_audio_channel_card(
        self,
        parent,
        *,
        column,
        title,
        source_var,
        signal_var,
        level_var,
        padx=(0, 0),
    ):
        card = tk.Frame(parent, bg="#f8fbfd", highlightbackground="#e3ebf3", highlightthickness=1)
        card.grid(row=2, column=column, sticky="ew", padx=padx)
        card.grid_columnconfigure(0, weight=1)
        card.configure(padx=12, pady=12)

        tk.Label(
            card,
            text=title,
            bg="#f8fbfd",
            fg="#17324d",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            card,
            textvariable=source_var,
            bg="#f8fbfd",
            fg="#5f7184",
            font=("Segoe UI", 9),
            wraplength=500,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 8))

        ttk.Progressbar(
            card,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=level_var,
        ).grid(row=2, column=0, sticky="ew")
        tk.Label(
            card,
            textvariable=signal_var,
            bg="#f8fbfd",
            fg="#5f7184",
            font=("Segoe UI", 9),
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))

    def _bind_device_selection_diagnostics(self):
        if hasattr(self, "mic_combo"):
            self.mic_combo.bind("<<ComboboxSelected>>", self._on_device_selection_changed)
        if hasattr(self, "speaker_combo"):
            self.speaker_combo.bind("<<ComboboxSelected>>", self._on_device_selection_changed)

    def _on_device_selection_changed(self, _event=None):
        self.channel_overlap_warning_active = False
        self._refresh_audio_diagnostics()

    def _selected_mic_source_info(self):
        if hasattr(self, "_selected_mic_device"):
            device = self._selected_mic_device()
            if device is not None:
                return {
                    "display": device.get("name") or self.mic_device_var.get() or "Не выбран",
                    "mode_label": "физический вход",
                    "channels": max(1, min(2, int(device.get("max_input_channels") or 1))),
                    "samplerate": int(device.get("default_samplerate") or 0) or None,
                    "hostapi_name": device.get("hostapi_name", ""),
                }

        return {
            "display": self.mic_device_var.get() or "Не выбран",
            "mode_label": "вход",
        }

    def _selected_speaker_source_info(self):
        if hasattr(self, "_selected_speaker_source"):
            source = self._selected_speaker_source()
            if source is not None:
                return {
                    "display": source.get("name") or source.get("label") or self.speaker_device_var.get() or "Не выбран",
                    "mode_label": source.get("mode_label", "вход"),
                    "channels": int(source.get("channels") or 0) or None,
                    "samplerate": int(source.get("default_samplerate") or 0) or None,
                    "hostapi_name": source.get("hostapi_name", ""),
                }

        return {
            "display": self.speaker_device_var.get() or "Не выбран",
            "mode_label": "вход",
        }

    def _format_source_summary(self, info):
        display = (info.get("display") or "Не выбран").strip()
        metadata = []

        mode_label = (info.get("mode_label") or "").strip()
        if mode_label:
            metadata.append(mode_label)

        channels_text = format_channel_count(info.get("channels"))
        if channels_text:
            metadata.append(channels_text)

        samplerate = info.get("samplerate")
        if samplerate:
            metadata.append(f"{int(round(int(samplerate) / 1000.0))} кГц")

        hostapi_name = (info.get("hostapi_name") or "").strip()
        if hostapi_name and hostapi_name not in metadata:
            metadata.append(hostapi_name)

        if metadata:
            return f"{display} | {', '.join(metadata)}"
        return display

    def _set_route_diag_message(self, message=None):
        if message is not None:
            self.route_diag_var.set(message)
            return

        mic_info = self._selected_mic_source_info()
        speaker_info = self._selected_speaker_source_info()

        if self.workers:
            self.route_diag_var.set(
                "Маршрут активен: "
                f"оператор -> {mic_info.get('mode_label', 'вход')}; "
                f"собеседник -> {speaker_info.get('mode_label', 'вход')}. "
                "Если одинаковые фразы попадают в обе колонки, проверьте выбор источников."
            )
            return

        self.route_diag_var.set(
            "Маршрут выбран: "
            f"оператор -> {mic_info.get('mode_label', 'вход')}; "
            f"собеседник -> {speaker_info.get('mode_label', 'вход')}. "
            "После старта следите за уровнями сигнала ниже."
        )

    def _refresh_audio_diagnostics(self):
        self.mic_source_var.set(self._format_source_summary(self._selected_mic_source_info()))
        self.speaker_source_var.set(self._format_source_summary(self._selected_speaker_source_info()))
        if not self.channel_overlap_warning_active:
            self._set_route_diag_message()
        self._refresh_startup_readiness()
        self._update_start_button_state()

    def _reset_audio_diagnostics(self):
        self.mic_level_var.set(0)
        self.speaker_level_var.set(0)
        self.mic_signal_var.set("Сигнал: тишина")
        self.speaker_signal_var.set("Сигнал: тишина")
        self.channel_overlap_warning_active = False
        self.last_overlap_warning_at = 0.0
        self._set_route_diag_message()
        self._refresh_startup_readiness()
        self._update_start_button_state()

    def _set_channel_signal(self, label, level_percent):
        if label == "me":
            level_var = self.mic_level_var
            signal_var = self.mic_signal_var
        else:
            level_var = self.speaker_level_var
            signal_var = self.speaker_signal_var

        level_var.set(level_percent)
        if level_percent >= 60:
            state_text = "сильный"
        elif level_percent >= 25:
            state_text = "есть"
        elif level_percent >= 8:
            state_text = "слабый"
        else:
            state_text = "тишина"
        signal_var.set(f"Сигнал: {state_text} ({level_percent}%)")

    def _remember_recent_final(self, bucket, text, event_time):
        cutoff = event_time - SIMILAR_DUPLICATE_WINDOW_SEC
        bucket.append((text, event_time))
        while bucket and bucket[0][1] < cutoff:
            bucket.popleft()

    def _find_recent_overlap(self, text, event_time, recent_items):
        for other_text, other_time in reversed(recent_items):
            if event_time - other_time > SIMILAR_DUPLICATE_WINDOW_SEC:
                break

            if are_exact_duplicates(text, other_text):
                return "exact", other_text
            if are_similar_duplicates(text, other_text):
                return "similar", other_text

        return None, None

    def _channel_name(self, label):
        return "микрофон" if label == "me" else "канал собеседника"

    def _register_channel_overlap(self, label, against_label, text, relation):
        now = time.monotonic()
        if relation == "similar" and now - self.last_overlap_warning_at < 1.5:
            return

        self.last_overlap_warning_at = now
        self.channel_overlap_warning_active = True
        relation_text = "одинаковую реплику" if relation == "exact" else "очень похожую реплику"
        self.route_diag_var.set(
            "Диагностика: похоже, каналы пересекаются. "
            f"{self._channel_name(label).capitalize()} и {self._channel_name(against_label)} поймали {relation_text}. "
            "Проверьте, что источник собеседника не дублирует микрофон."
        )
        LOGGER.warning(
            "Potential channel overlap detected. label=%s against=%s relation=%s text=%s",
            label,
            against_label,
            relation,
            short_text(text, 220),
        )

    def _load_input_devices(self):
        devices = []
        raw_devices = sd.query_devices()
        for idx, device in enumerate(raw_devices):
            if device["max_input_channels"] > 0:
                devices.append(
                    {
                        "id": idx,
                        "name": device["name"],
                        "max_input_channels": int(device["max_input_channels"]),
                        "default_samplerate": int(device["default_samplerate"]),
                    }
                )

        LOGGER.info("Detected input devices: %s", json.dumps(devices, ensure_ascii=False))
        return devices

    def _device_label(self, device):
        return f"{device['id']}: {device['name']}"

    def _find_device_by_label(self, label):
        for device in self.devices:
            if self._device_label(device) == label:
                return device
        return None

    def _selected_mic_device(self):
        return self._find_device_by_label(self.mic_device_var.get())

    def _selected_speaker_source(self):
        device = self._find_device_by_label(self.speaker_device_var.get())
        if device is None:
            return None
        return {
            "kind": "input",
            "mode_label": "вход",
            "label": self._device_label(device),
            "name": device["name"],
            "device_id": device["id"],
            "channels": max(1, min(2, int(device.get("max_input_channels") or 1))),
            "default_samplerate": int(device.get("default_samplerate") or 0) or None,
        }

    def _load_settings(self):
        if SETTINGS_PATH.exists():
            try:
                settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                LOGGER.info("Loaded settings: %s", json.dumps(settings, ensure_ascii=False))
                return settings
            except Exception:
                LOGGER.exception("Failed to load settings from %s", SETTINGS_PATH)
                return {}

        LOGGER.info("Settings file does not exist yet")
        return {}

    def _save_settings(self):
        payload = {
            "mic_device": self.mic_device_var.get(),
            "speaker_device": self.speaker_device_var.get(),
            "chrome_window_keyword": self.chrome_window_var.get().strip(),
            "chrome_auto_enter": bool(self.auto_enter_var.get()),
        }
        self.settings.update(payload)
        SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        LOGGER.info("Saved settings: %s", json.dumps(payload, ensure_ascii=False))
        self._refresh_startup_readiness()

    def _apply_default_devices(self):
        labels = [self._device_label(device) for device in self.devices]
        self.mic_combo["values"] = labels
        self.speaker_combo["values"] = labels

        if not labels:
            LOGGER.warning("No input devices available")
            self.mic_device_var.set("")
            self.speaker_device_var.set("")
            self._refresh_audio_diagnostics()
            return

        saved_mic = self.settings.get("mic_device")
        saved_speaker = self.settings.get("speaker_device")

        mic_default = saved_mic if saved_mic in labels else self._find_default_label(("микроф", "microphone", "mic input"))
        speaker_default = saved_speaker if saved_speaker in labels else self._find_default_label(("стерео микшер", "stereo mix", "stereo input"))

        self.mic_device_var.set(mic_default or labels[0])
        self.speaker_device_var.set(speaker_default or labels[0])

        LOGGER.info(
            "Default devices selected. mic=%s speaker=%s",
            self.mic_device_var.get(),
            self.speaker_device_var.get(),
        )
        self._refresh_audio_diagnostics()

    def _find_default_label(self, keywords):
        for device in self.devices:
            name = normalize_name(device["name"])
            if any(keyword in name for keyword in keywords):
                return self._device_label(device)
        return None

    def _start_model_loading(self, interactive=False):
        if self.model_loading or self.model is not None:
            return

        self.model_load_interactive = bool(interactive)
        existing_models = find_existing_models()
        if not existing_models:
            LOGGER.error("No speech models found")
            self.model_error_text = "В папке models нет подходящей модели распознавания."
            self.status_var.set("Модель не найдена")
            self.hint_var.set("В папке models нет подходящей модели распознавания.")
            self._refresh_startup_readiness()
            self._update_start_button_state()
            if interactive:
                messagebox.showerror(APP_TITLE, "Не найдена модель распознавания в папке models.")
            return

        self.model_loading = True
        self.model_error_text = ""
        self.status_var.set("Загружаю модель")
        self.hint_var.set("Большая модель может загружаться долго, но окно уже работает. Ждите готовности кнопки Старт.")
        self._refresh_startup_readiness()
        self._update_start_button_state()
        LOGGER.info("Scheduling background model loading. candidates=%s", [str(path) for path in existing_models])

        loader = threading.Thread(target=self._load_model_worker, daemon=True, name="ModelLoader")
        loader.start()

    def _load_model_worker(self):
        errors = []
        for model_dir in find_existing_models():
            try:
                started_at = time.perf_counter()
                LOGGER.info("Loading model in background from %s", model_dir)
                model = Model(str(model_dir))
                duration = time.perf_counter() - started_at
                LOGGER.info("Background model loaded in %.2f seconds from %s", duration, model_dir)
                self.ui_queue.put(("model_loaded", model, str(model_dir), duration))
                return
            except Exception as error:
                LOGGER.exception("Failed to load model from %s", model_dir)
                errors.append(f"{model_dir.name}: {error}")

        self.ui_queue.put(("model_failed", "\n".join(errors) if errors else "Не удалось загрузить модель"))

    def _current_model_name(self):
        if self.active_model_dir is not None:
            return self.active_model_dir.name
        return "не загружена"

    def _get_device_id(self, label):
        return int(label.split(":", 1)[0])

    def start_transcription(self):
        if self.model_loading:
            LOGGER.info("Start clicked while model is still loading")
            messagebox.showinfo(APP_TITLE, "Модель еще загружается. Дождитесь, когда кнопка Старт станет активной.")
            return

        if self.model is None:
            LOGGER.error("Start requested, but model is not loaded")
            messagebox.showerror(APP_TITLE, "Модель распознавания не загружена.")
            return

        mic_device = self._selected_mic_device()
        speaker_source = self._selected_speaker_source()
        if mic_device is None or speaker_source is None:
            LOGGER.error(
                "Selected devices are missing. mic=%s speaker=%s",
                self.mic_device_var.get(),
                self.speaker_device_var.get(),
            )
            messagebox.showerror(APP_TITLE, "Выберите оба устройства ввода.")
            return

        LOGGER.info(
            "Starting transcription. mic=%s speaker=%s model=%s",
            self.mic_device_var.get(),
            self.speaker_device_var.get(),
            self._current_model_name(),
        )

        self.stop_transcription()

        try:
            self.workers["me"] = TranscriptionWorker("me", self.model, mic_device["id"], self.ui_queue)
            self.workers["speaker"] = TranscriptionWorker("speaker", self.model, speaker_source["device_id"], self.ui_queue)
            self.workers["me"].start()
            self.workers["speaker"].start()
        except Exception as error:
            LOGGER.exception("Failed to start transcription workers")
            self.stop_transcription()
            messagebox.showerror(APP_TITLE, f"Не удалось запустить распознавание:\n{error}")
            return

        self.status_var.set("Идет одновременное распознавание")
        self.hint_var.set(f"Активная модель: {self._current_model_name()}. Блок ChatGPT работает отдельно и не мешает распознаванию.")
        self.channel_overlap_warning_active = False
        self.recent_mic_finals.clear()
        self.recent_speaker_finals.clear()
        self._refresh_audio_diagnostics()
        self._update_start_button_state()
        self.stop_button.configure(state="normal")
        self._save_settings()

    def stop_transcription(self):
        if self.workers:
            LOGGER.info("Stopping all workers")

        for worker in list(self.workers.values()):
            worker.stop()
        self.workers = {}
        self.recent_mic_finals.clear()
        self.recent_speaker_finals.clear()
        self._reset_audio_diagnostics()

        self._update_start_button_state()
        self.stop_button.configure(state="disabled")

    def refresh_devices(self):
        LOGGER.info("Refreshing device list")
        self.devices = self._load_input_devices()
        self._apply_default_devices()
        self.hint_var.set("Список аудиоустройств обновлен.")
        self.channel_overlap_warning_active = False
        self._refresh_audio_diagnostics()

    def refresh_startup_checks(self):
        LOGGER.info("Refreshing startup readiness checks")
        self.devices = self._load_input_devices()
        self._apply_default_devices()
        if self.model is None and not self.model_loading:
            self._start_model_loading(interactive=True)
        else:
            self._refresh_startup_readiness()
            self._update_start_button_state()

    def _append_text(self, widget, text):
        widget.insert("end", text)
        widget.see("end")

    def _remember_speaker_final(self, text, event_time):
        cutoff = event_time - SIMILAR_DUPLICATE_WINDOW_SEC
        self.recent_speaker_finals.append((text, event_time))

        while self.recent_speaker_finals and self.recent_speaker_finals[0][1] < cutoff:
            self.recent_speaker_finals.popleft()

    def _is_recent_exact_speaker_duplicate(self, text, event_time):
        for speaker_text, speaker_time in reversed(self.recent_speaker_finals):
            if event_time - speaker_time > EXACT_DUPLICATE_WINDOW_SEC:
                break

            if are_exact_duplicates(text, speaker_text):
                LOGGER.info(
                    "Suppressing exact duplicate in mic pane. me=%s speaker=%s",
                    short_text(text, 160),
                    short_text(speaker_text, 160),
                )
                return True

        return False

    def _poll_ui_queue(self):
        try:
            while True:
                message = self.ui_queue.get_nowait()
                kind = message[0]

                if kind == "final":
                    _, label, text, event_time = message
                    if label == "speaker":
                        relation, _matched_text = self._find_recent_overlap(
                            text, event_time, self.recent_mic_finals
                        )
                        if relation:
                            self._register_channel_overlap(label, "me", text, relation)
                        self._remember_speaker_final(text, event_time)
                        self._append_text(self.speaker_text, text + " ")
                    else:
                        relation, matched_text = self._find_recent_overlap(
                            text, event_time, self.recent_speaker_finals
                        )
                        if relation == "exact":
                            self._register_channel_overlap(label, "speaker", text, relation)
                            LOGGER.info(
                                "Suppressing exact duplicate in mic pane. me=%s speaker=%s",
                                short_text(text, 160),
                                short_text(matched_text, 160),
                            )
                        else:
                            if relation == "similar":
                                self._register_channel_overlap(label, "speaker", text, relation)
                            self._remember_recent_final(self.recent_mic_finals, text, event_time)
                            self._append_text(self.my_text, text + " ")
                elif kind == "partial":
                    _, label, text = message
                    if label == "me":
                        self.my_partial_var.set(text or "Пока пусто")
                    else:
                        self.speaker_partial_var.set(text or "Пока пусто")
                elif kind == "level":
                    _, label, level_percent = message
                    self._set_channel_signal(label, level_percent)
                elif kind == "status":
                    _, label, text = message
                    if label == "me":
                        self.status_var.set(f"Микрофон: {text}")
                    else:
                        self.hint_var.set(f"Собеседник: {text}")
                elif kind == "hint":
                    _, text = message
                    self.hint_var.set(text)
                elif kind == "model_loaded":
                    _, model, model_dir_text, duration = message
                    self.model = model
                    self.active_model_dir = Path(model_dir_text)
                    self.model_loading = False
                    self.model_error_text = ""
                    self.model_load_interactive = False
                    self.status_var.set("Готово")
                    self.hint_var.set(f"Модель {self.active_model_dir.name} загружена за {duration:.1f} с. Можно нажимать Старт.")
                    self._refresh_startup_readiness()
                    self._update_start_button_state()
                    LOGGER.info("UI received loaded model: %s", self.active_model_dir)
                elif kind == "model_failed":
                    _, error_text = message
                    self.model_loading = False
                    self.model_error_text = error_text
                    self.status_var.set("Ошибка загрузки модели")
                    self.hint_var.set("Не удалось загрузить модель. Подробности в логах.")
                    interactive = self.model_load_interactive
                    self.model_load_interactive = False
                    self._refresh_startup_readiness()
                    self._update_start_button_state()
                    LOGGER.error("All model loading attempts failed: %s", error_text)
                    if interactive:
                        messagebox.showerror(APP_TITLE, f"Не удалось загрузить модель:\n{error_text}")
        except queue.Empty:
            pass

        self.root.after(120, self._poll_ui_queue)

    def copy_speaker_text(self):
        text = self.speaker_text.get("1.0", "end").strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.hint_var.set("Текст собеседника скопирован.")
        LOGGER.info("Copied speaker text. chars=%s", len(text))

    def copy_all_text(self):
        me_text = self.my_text.get("1.0", "end").strip()
        speaker_text = self.speaker_text.get("1.0", "end").strip()
        combined = (
            "Я / оператор:\n"
            f"{me_text}\n\n"
            "Собеседник:\n"
            f"{speaker_text}\n"
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(combined)
        self.root.update()
        self.hint_var.set("Обе ленты скопированы.")
        LOGGER.info("Copied both texts. me_chars=%s speaker_chars=%s", len(me_text), len(speaker_text))

    def save_transcript(self):
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_path = TRANSCRIPTS_DIR / f"transcript_{timestamp}.txt"

        me_text = self.my_text.get("1.0", "end").strip()
        speaker_text = self.speaker_text.get("1.0", "end").strip()

        content = (
            f"{APP_TITLE}\n"
            f"Создано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"Модель: {self._current_model_name()}\n"
            f"Частота распознавания: {TARGET_SAMPLE_RATE} Hz\n"
            f"Лог: {LOG_PATH.name}\n\n"
            "Я / оператор:\n"
            f"{me_text}\n\n"
            "Собеседник:\n"
            f"{speaker_text}\n"
        )
        file_path.write_text(content, encoding="utf-8")
        self.hint_var.set(f"Сохранено: {file_path.name}")
        LOGGER.info("Transcript saved to %s", file_path)

    def open_logs_folder(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(LOGS_DIR))
        self.hint_var.set(f"Открыта папка логов: {LOGS_DIR}")
        LOGGER.info("Opened logs folder: %s", LOGS_DIR)

    def open_models_folder(self):
        self._ensure_runtime_helper_files()
        model_dir = models_root()
        model_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(model_dir))
        self.hint_var.set("Открыта папка models. Скопируйте туда русскую модель Vosk и нажмите Проверить снова.")
        LOGGER.info("Opened models folder: %s", model_dir)

    def open_application_folder(self):
        os.startfile(str(BASE_DIR))
        self.hint_var.set(f"Открыта папка приложения: {BASE_DIR}")
        LOGGER.info("Opened application folder: %s", BASE_DIR)

    def clear_text(self):
        if not messagebox.askyesno(APP_TITLE, "Очистить обе текстовые панели?"):
            LOGGER.info("Clear text canceled by user")
            return

        self.my_text.delete("1.0", "end")
        self.speaker_text.delete("1.0", "end")
        self.my_partial_var.set("Пока пусто")
        self.speaker_partial_var.set("Пока пусто")
        self.ai_prompt_text.delete("1.0", "end")
        self.last_sent_speaker_chars = 0
        self.pending_prompt_snapshot_len = 0
        self.hint_var.set("Панели очищены.")
        self.ai_hint_var.set("История отправки в ChatGPT сброшена.")
        LOGGER.info("Text panels cleared")

    def _render_prompt(self, prompt_text, snapshot_len):
        self.ai_prompt_text.delete("1.0", "end")
        self.ai_prompt_text.insert("1.0", prompt_text)
        self.pending_prompt_snapshot_len = snapshot_len

    def _speaker_text(self):
        return self.speaker_text.get("1.0", "end").strip()

    def _build_chat_prompt(self, mode):
        speaker_text = self._speaker_text()
        if not speaker_text:
            raise ValueError("В окне собеседника пока нет текста.")

        full_tail = speaker_text[-CHAT_FULL_CHARS:]
        current_len = len(speaker_text)

        if mode == "full":
            context_text = speaker_text[-CHAT_CONTEXT_CHARS:]
            latest_text = speaker_text[-CHAT_CONTEXT_CHARS:]
        else:
            if self.last_sent_speaker_chars < 0 or self.last_sent_speaker_chars > current_len:
                self.last_sent_speaker_chars = 0

            latest_text = speaker_text[self.last_sent_speaker_chars:].strip()
            if not latest_text:
                raise ValueError("Новых реплик после последней отправки пока нет.")

            context_text = speaker_text[:self.last_sent_speaker_chars].strip()
            context_text = context_text[-CHAT_CONTEXT_CHARS:]

        template = load_prompt_template()
        try:
            prompt_text = template.format(
                context=context_text or "(пока пусто)",
                latest=latest_text or "(пока пусто)",
                full=full_tail or "(пока пусто)",
            )
        except Exception:
            LOGGER.exception("Prompt template format failed, using fallback template")
            prompt_text = default_prompt_template().format(
                context=context_text or "(пока пусто)",
                latest=latest_text or "(пока пусто)",
                full=full_tail or "(пока пусто)",
            )

        return prompt_text, current_len

    def prepare_chat_prompt_delta(self):
        try:
            prompt_text, snapshot_len = self._build_chat_prompt("delta")
        except ValueError as error:
            messagebox.showinfo(APP_TITLE, str(error))
            return

        self._render_prompt(prompt_text, snapshot_len)
        self.ai_hint_var.set("Собран запрос только по новым репликам клиента.")
        LOGGER.info("Prepared delta ChatGPT prompt. chars=%s snapshot_len=%s", len(prompt_text), snapshot_len)

    def prepare_chat_prompt_full(self):
        try:
            prompt_text, snapshot_len = self._build_chat_prompt("full")
        except ValueError as error:
            messagebox.showinfo(APP_TITLE, str(error))
            return

        self._render_prompt(prompt_text, snapshot_len)
        self.ai_hint_var.set("Собран запрос по полному недавнему контексту клиента.")
        LOGGER.info("Prepared full ChatGPT prompt. chars=%s snapshot_len=%s", len(prompt_text), snapshot_len)

    def _current_prompt_text(self):
        return self.ai_prompt_text.get("1.0", "end").strip()

    def _ensure_prompt_for_sending(self):
        prompt_text = self._current_prompt_text()
        if prompt_text:
            return prompt_text

        prompt_text, snapshot_len = self._build_chat_prompt("delta")
        self._render_prompt(prompt_text, snapshot_len)
        return prompt_text

    def _mark_prompt_sent(self):
        if self.pending_prompt_snapshot_len > self.last_sent_speaker_chars:
            self.last_sent_speaker_chars = self.pending_prompt_snapshot_len
            LOGGER.info("Updated last_sent_speaker_chars=%s", self.last_sent_speaker_chars)

    def copy_chat_prompt(self):
        try:
            prompt_text = self._ensure_prompt_for_sending()
        except ValueError as error:
            messagebox.showinfo(APP_TITLE, str(error))
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(prompt_text)
        self.root.update()
        self._mark_prompt_sent()
        self.ai_hint_var.set("Запрос скопирован в буфер обмена. Если нужно переотправить, можно нажать Сбросить метку отправки.")
        LOGGER.info("Copied ChatGPT prompt to clipboard. chars=%s", len(prompt_text))
        self._save_settings()

    def open_prompt_template(self):
        os.startfile(str(PROMPT_TEMPLATE_PATH))
        self.ai_hint_var.set(f"Открыт шаблон: {PROMPT_TEMPLATE_PATH.name}")
        LOGGER.info("Opened prompt template: %s", PROMPT_TEMPLATE_PATH)

    def reset_chat_send_marker(self):
        self.last_sent_speaker_chars = 0
        self.pending_prompt_snapshot_len = 0
        self.ai_hint_var.set("Метка отправки сброшена. Теперь можно снова собрать весь контекст.")
        LOGGER.info("Reset ChatGPT send marker")

    def open_chatgpt_in_chrome(self):
        chrome_exe = find_chrome_exe()

        try:
            if chrome_exe is not None:
                subprocess.Popen([str(chrome_exe), "--new-tab", CHATGPT_URL])
                self.ai_hint_var.set("Открываю ChatGPT в Chrome.")
                LOGGER.info("Opened ChatGPT in Chrome: %s", chrome_exe)
            else:
                os.startfile(CHATGPT_URL)
                self.ai_hint_var.set("Chrome не найден явно, открываю ChatGPT через браузер по умолчанию.")
                LOGGER.warning("Chrome executable not found, used default browser")
        except Exception:
            LOGGER.exception("Failed to open ChatGPT in browser")
            messagebox.showerror(APP_TITLE, "Не удалось открыть ChatGPT в браузере.")

    def _paste_prompt_to_chat_window(self, prompt_text):
        self.root.clipboard_clear()
        self.root.clipboard_append(prompt_text)
        self.root.update()

        window_keyword = (self.chrome_window_var.get() or "").strip() or "ChatGPT"
        press_enter = "true" if self.auto_enter_var.get() else "false"

        command = [
            "cscript.exe",
            "//nologo",
            str(BRIDGE_SCRIPT_PATH),
            window_keyword,
            press_enter,
        ]
        LOGGER.info("Running bridge script for window keyword=%s auto_enter=%s", window_keyword, press_enter)
        result = subprocess.run(command, capture_output=True, text=True, timeout=12)
        return result.returncode == 0

    def send_chat_prompt_to_chrome(self):
        try:
            prompt_text = self._ensure_prompt_for_sending()
        except ValueError as error:
            messagebox.showinfo(APP_TITLE, str(error))
            return

        try:
            success = self._paste_prompt_to_chat_window(prompt_text)
        except Exception:
            LOGGER.exception("Failed to execute Chrome bridge")
            success = False

        if success:
            self._mark_prompt_sent()
            if self.auto_enter_var.get():
                self.ai_hint_var.set("Запрос вставлен в Chrome и отправлен.")
            else:
                self.ai_hint_var.set("Запрос вставлен в Chrome. При необходимости нажми Enter вручную.")
            LOGGER.info("Prompt sent to Chrome successfully. chars=%s", len(prompt_text))
            self._save_settings()
            return

        self.ai_hint_var.set("Окно ChatGPT не найдено. Запрос уже в буфере обмена, можно вставить вручную.")
        LOGGER.warning("Chrome bridge failed, prompt left in clipboard")
        messagebox.showinfo(
            APP_TITLE,
            "Не удалось активировать окно ChatGPT по текущему заголовку.\n\n"
            "Запрос уже скопирован в буфер.\n"
            "Что можно сделать:\n"
            "1. Откройте нужную вкладку ChatGPT в Chrome\n"
            "2. Кликните в поле ввода один раз\n"
            "3. Нажмите Отправить в Chrome еще раз\n"
            "Или просто вставьте текст вручную.",
        )

    def _report_callback_exception(self, exc_type, exc_value, exc_traceback):
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        LOGGER.error("Tk callback exception\n%s", details)
        messagebox.showerror(APP_TITLE, "Произошла ошибка. Подробности записаны в лог.")

    def on_close(self):
        LOGGER.info("Application closing")
        self.stop_transcription()
        self.root.destroy()


def main():
    LOGGER.info("Entering main()")
    root = tk.Tk()
    OperatorAssistApp(root)
    LOGGER.info("GUI mainloop starting")
    root.mainloop()
    LOGGER.info("GUI loop finished")


if __name__ == "__main__":
    main()
