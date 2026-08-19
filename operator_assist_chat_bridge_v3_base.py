import importlib.util
import logging
from datetime import datetime
from pathlib import Path


WRAPPER_VERSION = "2026-07-09-chat3"
CURRENT_DIR = Path(__file__).resolve().parent
BASE_SCRIPT_CANDIDATES = [
    CURRENT_DIR / "operator_assist_runtime" / "base_runtime.py",
    CURRENT_DIR / "backups" / "operator_assist_chat_bridge_base.py",
    CURRENT_DIR / "operator_assist_chat_bridge.py",
]


def load_base_module():
    for candidate in BASE_SCRIPT_CANDIDATES:
        if not candidate.exists():
            continue

        spec = importlib.util.spec_from_file_location("operator_assist_base_module", candidate)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, candidate

    raise FileNotFoundError("Base Operator Assist script for Chat Bridge was not found.")


_base, _base_path = load_base_module()


def rebind_base_environment():
    _base.BASE_DIR = CURRENT_DIR
    _base.SETTINGS_PATH = CURRENT_DIR / "operator_assist_settings.json"
    _base.TRANSCRIPTS_DIR = CURRENT_DIR / "transcripts"
    _base.PROMPT_TEMPLATE_PATH = CURRENT_DIR / "chatgpt_prompt_template.txt"
    _base.BRIDGE_SCRIPT_PATH = CURRENT_DIR / "scripts" / "paste_to_chat_window.vbs"
    _base.TECHNICAL_TERMS_PATH = CURRENT_DIR / "technical_terms.json"
    _base.MODEL_CANDIDATES = [
        CURRENT_DIR / "models" / "vosk-model-ru-0.42",
        CURRENT_DIR / "models" / "vosk-model-ru-0.22",
        CURRENT_DIR / "models" / "vosk-model-small-ru-0.22",
    ]
    _base.RUN_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _base.LOGS_DIR = _base.resolve_logs_dir()
    _base.LOG_PATH = _base.LOGS_DIR / f"operator_assist_{_base.RUN_TIMESTAMP}.log"

    logger = _base.LOGGER
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(threadName)s %(message)s")
    handler = None
    temp_root = Path(_base.os.environ.get("TEMP") or _base.os.environ.get("TMP") or "C:\\tmp")
    fallback_dir = temp_root / "OPERATOR_ASSIST_logs"
    fallback_path = fallback_dir / f"operator_assist_{_base.RUN_TIMESTAMP}.log"

    for candidate_path in (_base.LOG_PATH, fallback_path):
        try:
            candidate_path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(candidate_path, encoding="utf-8")
            _base.LOGS_DIR = candidate_path.parent
            _base.LOG_PATH = candidate_path
            break
        except Exception:
            continue

    if handler is None:
        handler = logging.NullHandler()

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    _base.ensure_text_file(_base.BRIDGE_SCRIPT_PATH, _base.bridge_script_content())
    _base.ensure_text_file(_base.TECHNICAL_TERMS_PATH, _base.default_technical_terms_content())
    logger.info(
        "Wrapper rebound base environment. wrapper_version=%s base_source=%s model_candidates=%s technical_terms_path=%s",
        WRAPPER_VERSION,
        _base_path,
        [str(path) for path in _base.MODEL_CANDIDATES],
        _base.TECHNICAL_TERMS_PATH,
    )


rebind_base_environment()


class OperatorAssistApp(_base.OperatorAssistApp):
    def __init__(self, root):
        super().__init__(root)
        self.ai_hint_var.set(
            "Для надежности основной режим такой: впиши свои условия, нажми Собрать всё, затем Копировать запрос и вставь его в свой ChatGPT."
        )

    def _build_chat_bridge(self, parent):
        bridge = _base.tk.Frame(parent, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        bridge.pack(fill="both", pady=(12, 0))
        bridge.configure(padx=16, pady=16)
        bridge.grid_columnconfigure(0, weight=1)

        _base.tk.Label(
            bridge,
            text="ChatGPT Bridge",
            bg="white",
            fg="#17324d",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")
        _base.tk.Label(
            bridge,
            textvariable=self.ai_hint_var,
            bg="white",
            fg="#5f7184",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        controls = _base.tk.Frame(bridge, bg="white")
        controls.grid(row=2, column=0, sticky="ew")
        controls.grid_columnconfigure(1, weight=1)

        _base.tk.Label(
            controls,
            text="Заголовок окна Chrome",
            bg="white",
            fg="#5f7184",
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, sticky="w")
        _base.tk.Entry(controls, textvariable=self.chrome_window_var, width=24).grid(row=0, column=1, sticky="w", padx=(10, 10))
        _base.tk.Checkbutton(
            controls,
            text="Нажимать Enter после вставки",
            variable=self.auto_enter_var,
            bg="white",
            activebackground="white",
        ).grid(row=0, column=2, sticky="w")

        operator_box = _base.tk.Frame(bridge, bg="white")
        operator_box.grid(row=3, column=0, sticky="nsew", pady=(12, 10))
        operator_box.grid_columnconfigure(0, weight=1)

        _base.tk.Label(
            operator_box,
            text="Условия подсказок",
            bg="white",
            fg="#17324d",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")
        _base.tk.Label(
            operator_box,
            text="Сюда оператор сам пишет условия и роль для ИИ. Этот текст будет поставлен перед текстом собеседника при копировании запроса.",
            bg="white",
            fg="#5f7184",
            font=("Segoe UI", 10),
            wraplength=1080,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 8))

        self.operator_prompt_text = _base.ScrolledText(operator_box, wrap="word", font=("Segoe UI", 10), height=5, undo=True)
        self.operator_prompt_text.grid(row=2, column=0, sticky="ew")
        initial_prompt = self.settings.get("operator_prompt", "")
        if initial_prompt:
            self.operator_prompt_text.insert("1.0", initial_prompt)

        buttons_top = _base.tk.Frame(bridge, bg="white")
        buttons_top.grid(row=4, column=0, sticky="w", pady=(10, 8))
        _base.tk.Button(
            buttons_top,
            text="Собрать всё",
            command=self.prepare_chat_prompt_full,
            bg="#eef6ff",
            fg="#17406d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        _base.tk.Button(
            buttons_top,
            text="Собрать новое",
            command=self.prepare_chat_prompt_delta,
            bg="#eef6ff",
            fg="#17406d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        _base.tk.Button(
            buttons_top,
            text="Копировать запрос",
            command=self.copy_chat_prompt,
            bg="#fff4df",
            fg="#5b4611",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        _base.tk.Button(
            buttons_top,
            text="Отправить в Chrome",
            command=self.send_chat_prompt_to_chrome,
            bg="#e8f8f2",
            fg="#0b5d4f",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        _base.tk.Button(
            buttons_top,
            text="Открыть ChatGPT",
            command=self.open_chatgpt_in_chrome,
            bg="#f3efff",
            fg="#4b2d8d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left")

        buttons_bottom = _base.tk.Frame(bridge, bg="white")
        buttons_bottom.grid(row=5, column=0, sticky="w", pady=(0, 10))
        _base.tk.Button(
            buttons_bottom,
            text="Очистить условия",
            command=self.clear_operator_prompt,
            bg="#f6f8fb",
            fg="#17324d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        _base.tk.Button(
            buttons_bottom,
            text="Сбросить метку отправки",
            command=self.reset_chat_send_marker,
            bg="#fdebec",
            fg="#8a2f39",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left")

        self.ai_prompt_text = _base.ScrolledText(bridge, wrap="word", font=("Consolas", 10), height=12, undo=True)
        self.ai_prompt_text.grid(row=6, column=0, sticky="nsew")

    def _operator_prompt_value(self):
        if not hasattr(self, "operator_prompt_text"):
            return ""
        return self.operator_prompt_text.get("1.0", "end").strip()

    def _save_settings(self):
        payload = {
            "mic_device": self.mic_device_var.get(),
            "speaker_device": self.speaker_device_var.get(),
            "chrome_window_keyword": self.chrome_window_var.get().strip(),
            "chrome_auto_enter": bool(self.auto_enter_var.get()),
            "operator_prompt": self._operator_prompt_value(),
        }
        _base.SETTINGS_PATH.write_text(_base.json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _base.LOGGER.info("Saved settings: %s", _base.json.dumps(payload, ensure_ascii=False))

    def clear_operator_prompt(self):
        self.operator_prompt_text.delete("1.0", "end")
        self.ai_hint_var.set("Условия подсказок очищены.")
        self._save_settings()
        _base.LOGGER.info("Operator prompt cleared")

    def _build_chat_prompt(self, mode):
        speaker_text = self._speaker_text()
        if not speaker_text:
            raise ValueError("В окне собеседника пока нет текста.")

        current_len = len(speaker_text)
        if mode == "delta":
            if self.last_sent_speaker_chars < 0 or self.last_sent_speaker_chars > current_len:
                self.last_sent_speaker_chars = 0

            speaker_fragment = speaker_text[self.last_sent_speaker_chars:].strip()
            if not speaker_fragment:
                raise ValueError("Новых реплик после последней отправки пока нет.")
        else:
            speaker_fragment = speaker_text

        operator_prompt = self._operator_prompt_value()
        prompt_parts = []
        if operator_prompt:
            prompt_parts.append(operator_prompt)
        prompt_parts.append(speaker_fragment)

        prompt_text = "\n\n".join(part for part in prompt_parts if part).strip()
        return prompt_text, current_len

    def prepare_chat_prompt_delta(self):
        try:
            prompt_text, snapshot_len = self._build_chat_prompt("delta")
        except ValueError as error:
            _base.messagebox.showinfo(_base.APP_TITLE, str(error))
            return

        self._render_prompt(prompt_text, snapshot_len)
        self.ai_hint_var.set("Собран запрос по новым репликам: сначала ваши условия, затем новые фразы собеседника.")
        self._save_settings()
        _base.LOGGER.info("Prepared delta ChatGPT prompt. chars=%s snapshot_len=%s", len(prompt_text), snapshot_len)

    def prepare_chat_prompt_full(self):
        try:
            prompt_text, snapshot_len = self._build_chat_prompt("full")
        except ValueError as error:
            _base.messagebox.showinfo(_base.APP_TITLE, str(error))
            return

        self._render_prompt(prompt_text, snapshot_len)
        self.ai_hint_var.set("Собран полный запрос: сначала ваши условия, затем текущий текст собеседника.")
        self._save_settings()
        _base.LOGGER.info("Prepared full ChatGPT prompt. chars=%s snapshot_len=%s", len(prompt_text), snapshot_len)

    def _ensure_prompt_for_sending(self):
        prompt_text = self._current_prompt_text()
        if prompt_text:
            return prompt_text

        prompt_text, snapshot_len = self._build_chat_prompt("full")
        self._render_prompt(prompt_text, snapshot_len)
        return prompt_text

    def copy_chat_prompt(self):
        try:
            prompt_text = self._ensure_prompt_for_sending()
        except ValueError as error:
            _base.messagebox.showinfo(_base.APP_TITLE, str(error))
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(prompt_text)
        self.root.update()
        self._mark_prompt_sent()
        self._save_settings()
        self.ai_hint_var.set("Запрос скопирован: сначала идут ваши условия, затем текст собеседника. Для надежности вставляйте его в ChatGPT вручную.")
        _base.LOGGER.info("Copied ChatGPT prompt to clipboard. chars=%s", len(prompt_text))

    def clear_text(self):
        if not _base.messagebox.askyesno(_base.APP_TITLE, "Очистить обе текстовые панели?"):
            _base.LOGGER.info("Clear text canceled by user")
            return

        self.my_text.delete("1.0", "end")
        self.speaker_text.delete("1.0", "end")
        self.my_partial_var.set("Пока пусто")
        self.speaker_partial_var.set("Пока пусто")
        self.ai_prompt_text.delete("1.0", "end")
        self.last_sent_speaker_chars = 0
        self.pending_prompt_snapshot_len = 0
        self.hint_var.set("Панели очищены.")
        self.ai_hint_var.set("История отправки в ChatGPT сброшена. Условия подсказок оставлены без изменений.")
        _base.LOGGER.info("Text panels cleared, operator prompt preserved")

    def on_close(self):
        self._save_settings()
        super().on_close()


def main():
    _base.LOGGER.info("Entering wrapper main()")
    root = _base.tk.Tk()
    OperatorAssistApp(root)
    _base.LOGGER.info("Wrapper GUI mainloop starting")
    root.mainloop()
    _base.LOGGER.info("Wrapper GUI loop finished")


if __name__ == "__main__":
    main()
