import importlib
import importlib.util
import logging
import sys
from datetime import datetime
from pathlib import Path

from operator_assist_runtime.runtime_paths import application_root, bundle_root, is_frozen

WRAPPER_VERSION = "2026-07-09-chat5"
CURRENT_DIR = application_root(__file__)
BUNDLE_DIR = bundle_root(__file__)
BASE_SCRIPT_CANDIDATES = [
    BUNDLE_DIR / "operator_assist_chat_bridge_v3_base.py",
]
VENDOR_CANDIDATES = [
    BUNDLE_DIR / "vendor",
    CURRENT_DIR / "vendor",
]

for vendor_dir in VENDOR_CANDIDATES:
    if vendor_dir.exists():
        vendor_text = str(vendor_dir)
        if vendor_text not in sys.path:
            sys.path.insert(0, vendor_text)

try:
    import numpy as _np
    import soundcard as _soundcard

    LOOPBACK_AVAILABLE = True
    LOOPBACK_IMPORT_ERROR = ""
except Exception as error:
    _np = None
    _soundcard = None
    LOOPBACK_AVAILABLE = False
    LOOPBACK_IMPORT_ERROR = str(error)


def load_base_module():
    if is_frozen():
        return (
            importlib.import_module("operator_assist_chat_bridge_v3_base"),
            BUNDLE_DIR / "operator_assist_chat_bridge_v3_base.py",
        )

    for candidate in BASE_SCRIPT_CANDIDATES:
        if not candidate.exists():
            continue

        spec = importlib.util.spec_from_file_location("operator_assist_chat3_base_module", candidate)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, candidate

    raise FileNotFoundError("Base Chat Bridge v3 script was not found.")


_base_mod, _base_path = load_base_module()


def rebind_environment():
    runtime = _base_mod._base
    runtime.BASE_DIR = CURRENT_DIR
    runtime.SETTINGS_PATH = CURRENT_DIR / "operator_assist_settings.json"
    runtime.TRANSCRIPTS_DIR = CURRENT_DIR / "transcripts"
    runtime.PROMPT_TEMPLATE_PATH = CURRENT_DIR / "chatgpt_prompt_template.txt"
    runtime.BRIDGE_SCRIPT_PATH = CURRENT_DIR / "scripts" / "paste_to_chat_window.vbs"
    runtime.TECHNICAL_TERMS_PATH = CURRENT_DIR / "technical_terms.json"
    runtime.ASSETS_DIR = CURRENT_DIR / "assets"
    runtime.APP_LOGO_PATH = runtime.ASSETS_DIR / "logo-enot.png"
    runtime.APP_LOGO_SMALL_PATH = runtime.ASSETS_DIR / "logo-enot-72.png"
    runtime.APP_LOGO_LARGE_PATH = runtime.ASSETS_DIR / "logo-enot-128.png"
    runtime.APP_ICON_PATH = runtime.ASSETS_DIR / "operator_assist.ico"
    runtime.MODEL_CANDIDATES = [
        CURRENT_DIR / "models" / "vosk-model-ru-0.42",
        CURRENT_DIR / "models" / "vosk-model-ru-0.22",
        CURRENT_DIR / "models" / "vosk-model-small-ru-0.22",
    ]
    runtime.RUN_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    runtime.LOGS_DIR = runtime.resolve_logs_dir()
    runtime.LOG_PATH = runtime.LOGS_DIR / f"operator_assist_{runtime.RUN_TIMESTAMP}.log"

    logger = runtime.LOGGER
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(threadName)s %(message)s")
    handler = None
    temp_root = Path(runtime.os.environ.get("TEMP") or runtime.os.environ.get("TMP") or "C:\\tmp")
    fallback_dir = temp_root / "OPERATOR_ASSIST_logs"
    fallback_path = fallback_dir / f"operator_assist_{runtime.RUN_TIMESTAMP}.log"

    for candidate_path in (runtime.LOG_PATH, fallback_path):
        try:
            candidate_path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(candidate_path, encoding="utf-8")
            runtime.LOGS_DIR = candidate_path.parent
            runtime.LOG_PATH = candidate_path
            break
        except Exception:
            continue

    if handler is None:
        handler = logging.NullHandler()

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    runtime.ensure_text_file(runtime.BRIDGE_SCRIPT_PATH, runtime.bridge_script_content())
    runtime.ensure_text_file(runtime.TECHNICAL_TERMS_PATH, runtime.default_technical_terms_content())
    logger.info(
        "Wrapper rebound environment. wrapper_version=%s base_source=%s model_candidates=%s technical_terms_path=%s loopback_available=%s loopback_error=%s",
        WRAPPER_VERSION,
        _base_path,
        [str(path) for path in runtime.MODEL_CANDIDATES],
        runtime.TECHNICAL_TERMS_PATH,
        LOOPBACK_AVAILABLE,
        LOOPBACK_IMPORT_ERROR,
    )


rebind_environment()


class LoopbackTranscriptionWorker(_base_mod._base.TranscriptionWorker):
    def __init__(self, label, model, source, ui_queue):
        super().__init__(label, model, -1, ui_queue)
        self.source = source
        self.capture_thread = None
        self.device_name = source["name"]
        self.channels = max(1, int(source.get("channels") or 2))
        self.input_samplerate = int(source.get("default_samplerate") or 48000)

    def start(self):
        runtime = _base_mod._base
        runtime.LOGGER.info("[%s] Starting WASAPI loopback worker. source=%s", self.label, self.source)

        self.stop_event.clear()
        self.thread = runtime.threading.Thread(
            target=self._run_recognition,
            daemon=True,
            name=f"Recognizer-{self.label}",
        )
        self.thread.start()

        self.capture_thread = runtime.threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name=f"Loopback-{self.label}",
        )
        self.capture_thread.start()

        self.ui_queue.put(("status", self.label, f"Слушаю: {self.device_name}"))

    def stop(self):
        runtime = _base_mod._base
        runtime.LOGGER.info("[%s] Stopping WASAPI loopback worker", self.label)
        self.stop_event.set()

        if self.capture_thread is not None:
            self.capture_thread.join(timeout=2.0)
            if self.capture_thread.is_alive():
                runtime.LOGGER.warning("[%s] Loopback capture thread is still alive after timeout", self.label)
            self.capture_thread = None

        if self.thread is not None:
            self.thread.join(timeout=1.5)
            if self.thread.is_alive():
                runtime.LOGGER.warning("[%s] Recognizer thread is still alive after timeout", self.label)
            self.thread = None

        runtime.LOGGER.info(
            "[%s] WASAPI loopback worker stopped. chunks=%s drops=%s callback_warnings=%s",
            self.label,
            self.chunk_count,
            self.drop_count,
            self.callback_warning_count,
        )
        self.ui_queue.put(("status", self.label, "Остановлено"))

    def _resolve_microphone(self):
        for microphone in _soundcard.all_microphones(include_loopback=True):
            if getattr(microphone, "id", None) == self.source["id"] and getattr(microphone, "isloopback", False):
                return microphone

        raise RuntimeError(f"Loopback source not found: {self.source['name']}")

    def _candidate_sample_rates(self):
        values = []
        for samplerate in (
            self.source.get("default_samplerate"),
            48000,
            44100,
        ):
            if samplerate:
                samplerate = int(samplerate)
                if samplerate not in values:
                    values.append(samplerate)
        return values or [48000]

    def _enqueue_chunk(self, chunk):
        runtime = _base_mod._base

        if self.input_samplerate != runtime.TARGET_SAMPLE_RATE:
            chunk, self.rate_state = runtime.audioop.ratecv(
                chunk,
                2,
                1,
                self.input_samplerate,
                runtime.TARGET_SAMPLE_RATE,
                self.rate_state,
            )

        if not self.stop_event.is_set() and chunk:
            self.chunk_count += 1
            self._emit_level(chunk)
            try:
                self.audio_queue.put_nowait(chunk)
            except runtime.queue.Full:
                self.drop_count += 1

                try:
                    self.audio_queue.get_nowait()
                except runtime.queue.Empty:
                    pass

                try:
                    self.audio_queue.put_nowait(chunk)
                except runtime.queue.Full:
                    pass

                if self.drop_count <= 3 or self.drop_count % 10 == 0:
                    runtime.LOGGER.warning(
                        "[%s] Audio queue overflow. drops=%s queue_size=%s",
                        self.label,
                        self.drop_count,
                        self.audio_queue.qsize(),
                    )

    def _frames_to_pcm(self, frames):
        if frames is None:
            return b""

        samples = _np.asarray(frames, dtype=_np.float32)
        if samples.size == 0:
            return b""

        if samples.ndim == 2:
            if samples.shape[1] > 1:
                samples = samples.mean(axis=1, dtype=_np.float32)
            else:
                samples = samples[:, 0]

        samples = _np.nan_to_num(samples, copy=False)
        samples = _np.clip(samples, -1.0, 1.0)
        return (samples * 32767.0).astype(_np.int16).tobytes()

    def _capture_loop(self):
        runtime = _base_mod._base
        errors = []

        for samplerate in self._candidate_sample_rates():
            try:
                microphone = self._resolve_microphone()
                blocksize = max(1024, int(samplerate * runtime.AUDIO_BLOCK_MS / 1000))
                self.input_samplerate = samplerate
                self.rate_state = None

                runtime.LOGGER.info(
                    "[%s] Opening loopback recorder. name=%s samplerate=%s channels=%s blocksize=%s",
                    self.label,
                    self.device_name,
                    samplerate,
                    self.channels,
                    blocksize,
                )

                with microphone.recorder(samplerate=samplerate, channels=self.channels) as recorder:
                    while not self.stop_event.is_set():
                        frames = recorder.record(numframes=blocksize)
                        chunk = self._frames_to_pcm(frames)
                        if chunk:
                            self._enqueue_chunk(chunk)
                return
            except Exception as error:
                errors.append(f"{samplerate} Hz: {error}")
                runtime.LOGGER.exception("[%s] Loopback capture failed at %s Hz", self.label, samplerate)

        if not self.stop_event.is_set():
            message = "; ".join(errors) if errors else "Не удалось открыть WASAPI loopback."
            runtime.LOGGER.error("[%s] Loopback capture could not start: %s", self.label, message)
            self.ui_queue.put(("hint", f"{self.label}: {message}"))


class OperatorAssistApp(_base_mod.OperatorAssistApp):
    SPEAKER_FALLBACK_KEYWORDS = (
        "стерео",
        "stereo",
        "mix",
        "loopback",
        "what u hear",
        "what you hear",
        "monitor",
        "output",
        "cable",
        "virtual",
    )

    def __init__(self, root):
        self.mic_devices = []
        self.speaker_sources = []
        self.default_loopback_label = None
        super().__init__(root)

    def _build_ui(self):
        runtime = _base_mod._base

        self.root.geometry("1360x860")
        self.root.minsize(1080, 700)
        self.root.configure(bg="#f3f6f9")

        shell = runtime.tk.Frame(self.root, bg="#f3f6f9")
        shell.pack(fill="both", expand=True)

        canvas = runtime.tk.Canvas(shell, bg="#f3f6f9", highlightthickness=0)
        scrollbar = runtime.ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        wrapper = runtime.tk.Frame(canvas, bg="#f3f6f9")
        canvas_window = canvas.create_window((0, 0), window=wrapper, anchor="nw")

        def sync_scrollregion(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_width(event):
            canvas.itemconfigure(canvas_window, width=event.width)

        def on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")
                return "break"
            return None

        wrapper.bind("<Configure>", sync_scrollregion)
        canvas.bind("<Configure>", fit_width)
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        self._main_canvas = canvas
        self._main_scrollbar = scrollbar

        outer = runtime.tk.Frame(wrapper, bg="#f3f6f9")
        outer.pack(fill="both", expand=True, padx=18, pady=18)

        self._build_branded_header(
            outer,
            subtitle_text="Одновременное распознавание вашего микрофона и системного звука через WASAPI loopback или запасной вход",
        )
        self._build_startup_readiness(outer)

        controls = runtime.tk.Frame(outer, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        controls.pack(fill="x", pady=(0, 12))
        controls.configure(padx=16, pady=16)

        runtime.tk.Label(controls, text="Мой микрофон", bg="white", fg="#5f7184", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        runtime.tk.Label(controls, text="Собеседник / системный звук", bg="white", fg="#5f7184", font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w", padx=(16, 0))

        self.mic_combo = runtime.ttk.Combobox(controls, textvariable=self.mic_device_var, state="readonly", width=48)
        self.mic_combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.speaker_combo = runtime.ttk.Combobox(controls, textvariable=self.speaker_device_var, state="readonly", width=48)
        self.speaker_combo.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=(6, 0))
        self._bind_device_selection_diagnostics()

        buttons = runtime.tk.Frame(controls, bg="white")
        buttons.grid(row=1, column=2, padx=(16, 0), sticky="e")

        self.start_button = runtime.tk.Button(buttons, text="Старт", command=self.start_transcription, bg="#0f766e", fg="white", relief="flat", padx=16, pady=10, state="disabled")
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = runtime.tk.Button(buttons, text="Стоп", command=self.stop_transcription, bg="#e7eef5", fg="#17324d", relief="flat", padx=16, pady=10, state="disabled")
        self.stop_button.pack(side="left", padx=(0, 8))
        runtime.tk.Button(buttons, text="Обновить устройства", command=self.refresh_devices, bg="#e7eef5", fg="#17324d", relief="flat", padx=16, pady=10).pack(side="left")

        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)

        self._build_audio_diagnostics(outer)

        action_bar = runtime.tk.Frame(outer, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        action_bar.pack(fill="x", pady=(0, 12))
        action_bar.configure(padx=16, pady=12)

        runtime.tk.Label(action_bar, textvariable=self.status_var, bg="white", fg="#0f766e", font=("Segoe UI", 11, "bold")).pack(side="left")
        runtime.tk.Label(action_bar, textvariable=self.hint_var, bg="white", fg="#5f7184", font=("Segoe UI", 10)).pack(side="left", padx=(18, 0))

        actions_right = runtime.tk.Frame(action_bar, bg="white")
        actions_right.pack(side="right")
        runtime.tk.Button(actions_right, text="Копировать собеседника", command=self.copy_speaker_text, bg="#fff4df", fg="#5b4611", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        runtime.tk.Button(actions_right, text="Копировать всё", command=self.copy_all_text, bg="#eef6ff", fg="#17406d", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        runtime.tk.Button(actions_right, text="Сохранить TXT", command=self.save_transcript, bg="#e8f8f2", fg="#0b5d4f", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        runtime.tk.Button(actions_right, text="Открыть логи", command=self.open_logs_folder, bg="#f3efff", fg="#4b2d8d", relief="flat", padx=12, pady=8).pack(side="left", padx=(0, 8))
        runtime.tk.Button(actions_right, text="Очистить", command=self.clear_text, bg="#fdebec", fg="#8a2f39", relief="flat", padx=12, pady=8).pack(side="left")

        panel_grid = runtime.tk.Frame(outer, bg="#f3f6f9")
        panel_grid.pack(fill="both", expand=True)
        panel_grid.grid_columnconfigure(0, weight=1)
        panel_grid.grid_columnconfigure(1, weight=1)
        panel_grid.grid_rowconfigure(0, weight=1)

        self.my_text = self._build_panel(panel_grid, 0, "Я / оператор", self.my_partial_var)
        self.speaker_text = self._build_panel(panel_grid, 1, "Собеседник", self.speaker_partial_var)

        self._build_chat_bridge(outer)
        if hasattr(self, "ai_prompt_text"):
            self.ai_prompt_text.configure(height=8)

        self.root.after(50, sync_scrollregion)

    def _load_input_devices(self):
        runtime = _base_mod._base
        raw_devices = runtime.sd.query_devices()
        hostapis = runtime.sd.query_hostapis()
        hostapi_names = {idx: api["name"] for idx, api in enumerate(hostapis)}
        mic_devices = []
        wasapi_output_rates = {}

        for idx, device in enumerate(raw_devices):
            hostapi_name = hostapi_names.get(device["hostapi"], str(device["hostapi"]))
            if device["max_output_channels"] > 0 and "wasapi" in hostapi_name.casefold():
                key = runtime.normalize_name(device["name"])
                wasapi_output_rates.setdefault(key, []).append(int(device["default_samplerate"]))

            if device["max_input_channels"] > 0:
                mic_devices.append(
                    {
                        "id": idx,
                        "name": device["name"],
                        "hostapi_name": hostapi_name,
                        "max_input_channels": int(device["max_input_channels"]),
                        "default_samplerate": int(device["default_samplerate"]),
                    }
                )

        self.mic_devices = mic_devices
        self.speaker_sources = self._build_speaker_sources(mic_devices, wasapi_output_rates)

        runtime.LOGGER.info("Detected mic devices: %s", runtime.json.dumps(mic_devices, ensure_ascii=False))
        runtime.LOGGER.info("Detected speaker sources: %s", runtime.json.dumps(self.speaker_sources, ensure_ascii=False))
        return mic_devices

    def _make_loopback_label(self, name, source_id, seen_labels):
        label = f"WASAPI loopback: {name}"
        if label in seen_labels:
            label = f"{label} [{str(source_id)[-8:]}]"
        seen_labels.add(label)
        return label

    def _build_speaker_sources(self, mic_devices, wasapi_output_rates):
        runtime = _base_mod._base
        sources = []
        seen_labels = set()
        self.default_loopback_label = None

        if LOOPBACK_AVAILABLE:
            default_speaker_id = None
            try:
                default_speaker = _soundcard.default_speaker()
                default_speaker_id = getattr(default_speaker, "id", None)
            except Exception:
                runtime.LOGGER.exception("Failed to query default WASAPI speaker")

            try:
                for microphone in _soundcard.all_microphones(include_loopback=True):
                    if not getattr(microphone, "isloopback", False):
                        continue

                    name_key = runtime.normalize_name(microphone.name)
                    rate_options = wasapi_output_rates.get(name_key) or [48000]
                    label = self._make_loopback_label(microphone.name, microphone.id, seen_labels)
                    source = {
                        "kind": "loopback",
                        "mode_label": "WASAPI loopback",
                        "label": label,
                        "name": microphone.name,
                        "id": microphone.id,
                        "channels": int(getattr(microphone, "channels", 2) or 2),
                        "default_samplerate": int(rate_options[0]),
                    }
                    sources.append(source)

                    if default_speaker_id and microphone.id == default_speaker_id and self.default_loopback_label is None:
                        self.default_loopback_label = label
            except Exception:
                runtime.LOGGER.exception("Failed to enumerate WASAPI loopback microphones")
        else:
            runtime.LOGGER.warning("WASAPI loopback dependency unavailable: %s", LOOPBACK_IMPORT_ERROR)

        fallback_sources = []
        for device in mic_devices:
            label = self._device_label(device)
            normalized_name = runtime.normalize_name(device["name"])
            if any(keyword in normalized_name for keyword in self.SPEAKER_FALLBACK_KEYWORDS):
                fallback_sources.append(
                    {
                        "kind": "input",
                        "mode_label": "запасной вход",
                        "label": label,
                        "name": device["name"],
                        "device_id": device["id"],
                        "channels": max(1, min(2, int(device["max_input_channels"]))),
                        "default_samplerate": int(device["default_samplerate"]),
                        "hostapi_name": device["hostapi_name"],
                    }
                )

        if not sources and not fallback_sources:
            for device in mic_devices:
                fallback_sources.append(
                    {
                        "kind": "input",
                        "mode_label": "обычный вход",
                        "label": self._device_label(device),
                        "name": device["name"],
                        "device_id": device["id"],
                        "channels": max(1, min(2, int(device["max_input_channels"]))),
                        "default_samplerate": int(device["default_samplerate"]),
                        "hostapi_name": device["hostapi_name"],
                    }
                )

        sources.extend(fallback_sources)
        return sources

    def _apply_default_devices(self):
        runtime = _base_mod._base
        mic_labels = [self._device_label(device) for device in self.mic_devices]
        speaker_labels = [source["label"] for source in self.speaker_sources]

        self.mic_combo["values"] = mic_labels
        self.speaker_combo["values"] = speaker_labels

        if not mic_labels:
            runtime.LOGGER.warning("No microphone devices available")
            self.mic_device_var.set("")
            self.speaker_device_var.set("")
            self._refresh_audio_diagnostics()
            return

        saved_mic = self.settings.get("mic_device")
        saved_speaker = self.settings.get("speaker_device")

        mic_default = saved_mic if saved_mic in mic_labels else self._find_mic_label(("микроф", "microphone", "mic input"))

        if not speaker_labels:
            runtime.LOGGER.warning("No speaker capture sources available")
            self.mic_device_var.set(mic_default or mic_labels[0])
            self.speaker_device_var.set("")
            self._refresh_audio_diagnostics()
            return

        speaker_default = saved_speaker if saved_speaker in speaker_labels else self._find_speaker_label()

        self.mic_device_var.set(mic_default or mic_labels[0])
        self.speaker_device_var.set(speaker_default or speaker_labels[0])

        runtime.LOGGER.info(
            "Default devices selected. mic=%s speaker=%s",
            self.mic_device_var.get(),
            self.speaker_device_var.get(),
        )
        self._refresh_audio_diagnostics()

    def _find_mic_label(self, keywords):
        runtime = _base_mod._base
        for device in self.mic_devices:
            name = runtime.normalize_name(device["name"])
            if any(keyword in name for keyword in keywords):
                return self._device_label(device)
        return None

    def _find_speaker_label(self):
        runtime = _base_mod._base
        if self.default_loopback_label:
            return self.default_loopback_label

        for source in self.speaker_sources:
            label = runtime.normalize_name(source["label"])
            if "wasapi loopback" in label or "стерео" in label or "stereo mix" in label:
                return source["label"]

        return self.speaker_sources[0]["label"] if self.speaker_sources else None

    def _selected_mic_device(self):
        selected = self.mic_device_var.get()
        for device in self.mic_devices:
            if self._device_label(device) == selected:
                return device
        return None

    def _selected_speaker_source(self):
        selected = self.speaker_device_var.get()
        for source in self.speaker_sources:
            if source["label"] == selected:
                return source
        return None

    def start_transcription(self):
        runtime = _base_mod._base

        if self.model_loading:
            runtime.LOGGER.info("Start clicked while model is still loading")
            runtime.messagebox.showinfo(runtime.APP_TITLE, "Модель еще загружается. Дождитесь, когда кнопка Старт станет активной.")
            return

        if self.model is None:
            runtime.LOGGER.error("Start requested, but model is not loaded")
            runtime.messagebox.showerror(runtime.APP_TITLE, "Модель распознавания не загружена.")
            return

        mic_device = self._selected_mic_device()
        speaker_source = self._selected_speaker_source()
        if mic_device is None or speaker_source is None:
            runtime.LOGGER.error("Selected devices are missing. mic=%s speaker=%s", self.mic_device_var.get(), self.speaker_device_var.get())
            runtime.messagebox.showerror(runtime.APP_TITLE, "Выберите микрофон и источник звука собеседника.")
            return

        runtime.LOGGER.info(
            "Starting transcription. mic=%s speaker=%s model=%s",
            self.mic_device_var.get(),
            self.speaker_device_var.get(),
            self._current_model_name(),
        )

        self.stop_transcription()

        try:
            self.workers["me"] = runtime.TranscriptionWorker("me", self.model, mic_device["id"], self.ui_queue)

            if speaker_source["kind"] == "loopback":
                self.workers["speaker"] = LoopbackTranscriptionWorker("speaker", self.model, speaker_source, self.ui_queue)
            else:
                self.workers["speaker"] = runtime.TranscriptionWorker("speaker", self.model, speaker_source["device_id"], self.ui_queue)

            self.workers["me"].start()
            self.workers["speaker"].start()
        except Exception as error:
            runtime.LOGGER.exception("Failed to start transcription workers")
            self.stop_transcription()
            runtime.messagebox.showerror(runtime.APP_TITLE, f"Не удалось запустить распознавание:\n{error}")
            return

        self.status_var.set("Идет одновременное распознавание")
        self.hint_var.set(
            f"Активная модель: {self._current_model_name()}. Собеседник захватывается через {speaker_source['mode_label']}."
        )
        self.channel_overlap_warning_active = False
        self.recent_mic_finals.clear()
        self.recent_speaker_finals.clear()
        self._refresh_audio_diagnostics()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._save_settings()

    def refresh_devices(self):
        runtime = _base_mod._base
        runtime.LOGGER.info("Refreshing device list")
        self.devices = self._load_input_devices()
        self._apply_default_devices()
        self.channel_overlap_warning_active = False
        self._refresh_audio_diagnostics()

        if any(source["kind"] == "loopback" for source in self.speaker_sources):
            self.hint_var.set("Список устройств обновлен. Для собеседника доступен WASAPI loopback.")
        elif LOOPBACK_AVAILABLE:
            self.hint_var.set("Список устройств обновлен. Loopback не найден, используйте запасной вход.")
        else:
            self.hint_var.set("Список устройств обновлен. Модуль loopback не загрузился, используйте обычный вход.")


def main():
    _base_mod._base.LOGGER.info("Entering wrapper main()")
    root = _base_mod._base.tk.Tk()
    OperatorAssistApp(root)
    _base_mod._base.LOGGER.info("Wrapper GUI mainloop starting")
    root.mainloop()
    _base_mod._base.LOGGER.info("Wrapper GUI loop finished")


if __name__ == "__main__":
    main()
