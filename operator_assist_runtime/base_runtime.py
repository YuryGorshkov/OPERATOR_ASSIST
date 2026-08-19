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
from operator_assist_runtime.text_utils import (
    are_exact_duplicates as shared_are_exact_duplicates,
    normalize_name as shared_normalize_name,
    short_text as shared_short_text,
)


APP_TITLE = "OPERATOR_ASSIST Operator Assist"
APP_VERSION = "2026-07-09-chat1"
BASE_DIR = Path(__file__).resolve().parents[1]
SETTINGS_PATH = BASE_DIR / "operator_assist_settings.json"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
PROMPT_TEMPLATE_PATH = BASE_DIR / "chatgpt_prompt_template.txt"
BRIDGE_SCRIPT_PATH = BASE_DIR / "scripts" / "paste_to_chat_window.vbs"
TECHNICAL_TERMS_PATH = BASE_DIR / "technical_terms.json"
RUN_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
TARGET_SAMPLE_RATE = 16000
AUDIO_BLOCK_MS = 250
EXACT_DUPLICATE_WINDOW_SEC = 1.2
EXACT_DUPLICATE_MIN_CHARS = 12
CHATGPT_URL = "https://chatgpt.com/"
CHAT_CONTEXT_CHARS = 1400
CHAT_FULL_CHARS = 2200

MODEL_CANDIDATES = [
    BASE_DIR / "models" / "vosk-model-ru-0.42",
    BASE_DIR / "models" / "vosk-model-ru-0.22",
    BASE_DIR / "models" / "vosk-model-small-ru-0.22",
]


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

        LOGGER.info("UI initialized. devices=%s", len(self.devices))

        self._build_ui()
        self._apply_default_devices()
        self._poll_ui_queue()
        self.root.after(120, self._start_model_loading)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        self.root.configure(bg="#f3f6f9")

        wrapper = tk.Frame(self.root, bg="#f3f6f9")
        wrapper.pack(fill="both", expand=True, padx=18, pady=18)

        header = tk.Frame(wrapper, bg="#f3f6f9")
        header.pack(fill="x", pady=(0, 12))

        tk.Label(
            header,
            text="Operator Assist",
            font=("Segoe UI", 24, "bold"),
            bg="#f3f6f9",
            fg="#17324d",
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Одновременное распознавание вашего микрофона и речи собеседника через Стерео микшер",
            font=("Segoe UI", 11),
            bg="#f3f6f9",
            fg="#5f7184",
        ).pack(anchor="w", pady=(2, 0))

        controls = tk.Frame(wrapper, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        controls.pack(fill="x", pady=(0, 12))
        controls.configure(padx=16, pady=16)

        tk.Label(controls, text="Мой микрофон", bg="white", fg="#5f7184", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        tk.Label(controls, text="Собеседник / системный звук", bg="white", fg="#5f7184", font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w", padx=(16, 0))

        self.mic_combo = ttk.Combobox(controls, textvariable=self.mic_device_var, state="readonly", width=48)
        self.mic_combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.speaker_combo = ttk.Combobox(controls, textvariable=self.speaker_device_var, state="readonly", width=48)
        self.speaker_combo.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=(6, 0))

        buttons = tk.Frame(controls, bg="white")
        buttons.grid(row=1, column=2, padx=(16, 0), sticky="e")

        self.start_button = tk.Button(buttons, text="Старт", command=self.start_transcription, bg="#0f766e", fg="white", relief="flat", padx=16, pady=10, state="disabled")
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = tk.Button(buttons, text="Стоп", command=self.stop_transcription, bg="#e7eef5", fg="#17324d", relief="flat", padx=16, pady=10, state="disabled")
        self.stop_button.pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Обновить устройства", command=self.refresh_devices, bg="#e7eef5", fg="#17324d", relief="flat", padx=16, pady=10).pack(side="left")

        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)

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
        SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        LOGGER.info("Saved settings: %s", json.dumps(payload, ensure_ascii=False))

    def _apply_default_devices(self):
        labels = [self._device_label(device) for device in self.devices]
        self.mic_combo["values"] = labels
        self.speaker_combo["values"] = labels

        if not labels:
            LOGGER.warning("No input devices available")
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

    def _find_default_label(self, keywords):
        for device in self.devices:
            name = normalize_name(device["name"])
            if any(keyword in name for keyword in keywords):
                return self._device_label(device)
        return None

    def _start_model_loading(self):
        if self.model_loading or self.model is not None:
            return

        existing_models = find_existing_models()
        if not existing_models:
            LOGGER.error("No speech models found")
            self.status_var.set("Модель не найдена")
            self.hint_var.set("В папке models нет подходящей модели распознавания.")
            messagebox.showerror(APP_TITLE, "Не найдена модель распознавания в папке models.")
            return

        self.model_loading = True
        self.status_var.set("Загружаю модель")
        self.hint_var.set("Большая модель может загружаться долго, но окно уже работает. Ждите готовности кнопки Старт.")
        self.start_button.configure(state="disabled")
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

        try:
            mic_id = self._get_device_id(self.mic_device_var.get())
            speaker_id = self._get_device_id(self.speaker_device_var.get())
        except Exception:
            LOGGER.exception("Failed to parse selected devices")
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
            self.workers["me"] = TranscriptionWorker("me", self.model, mic_id, self.ui_queue)
            self.workers["speaker"] = TranscriptionWorker("speaker", self.model, speaker_id, self.ui_queue)
            self.workers["me"].start()
            self.workers["speaker"].start()
        except Exception as error:
            LOGGER.exception("Failed to start transcription workers")
            self.stop_transcription()
            messagebox.showerror(APP_TITLE, f"Не удалось запустить распознавание:\n{error}")
            return

        self.status_var.set("Идет одновременное распознавание")
        self.hint_var.set(f"Активная модель: {self._current_model_name()}. Блок ChatGPT работает отдельно и не мешает распознаванию.")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._save_settings()

    def stop_transcription(self):
        if self.workers:
            LOGGER.info("Stopping all workers")

        for worker in list(self.workers.values()):
            worker.stop()
        self.workers = {}
        self.recent_speaker_finals.clear()

        if self.model is not None and not self.model_loading:
            self.start_button.configure(state="normal")
        else:
            self.start_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")

    def refresh_devices(self):
        LOGGER.info("Refreshing device list")
        self.devices = self._load_input_devices()
        self._apply_default_devices()
        self.hint_var.set("Список аудиоустройств обновлен.")

    def _append_text(self, widget, text):
        widget.insert("end", text)
        widget.see("end")

    def _remember_speaker_final(self, text, event_time):
        cutoff = event_time - EXACT_DUPLICATE_WINDOW_SEC
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
                        self._remember_speaker_final(text, event_time)
                        self._append_text(self.speaker_text, text + " ")
                    else:
                        if not self._is_recent_exact_speaker_duplicate(text, event_time):
                            self._append_text(self.my_text, text + " ")
                elif kind == "partial":
                    _, label, text = message
                    if label == "me":
                        self.my_partial_var.set(text or "Пока пусто")
                    else:
                        self.speaker_partial_var.set(text or "Пока пусто")
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
                    self.status_var.set("Готово")
                    self.hint_var.set(f"Модель {self.active_model_dir.name} загружена за {duration:.1f} с. Можно нажимать Старт.")
                    if not self.workers:
                        self.start_button.configure(state="normal")
                    LOGGER.info("UI received loaded model: %s", self.active_model_dir)
                elif kind == "model_failed":
                    _, error_text = message
                    self.model_loading = False
                    self.status_var.set("Ошибка загрузки модели")
                    self.hint_var.set("Не удалось загрузить модель. Подробности в логах.")
                    self.start_button.configure(state="disabled")
                    LOGGER.error("All model loading attempts failed: %s", error_text)
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
