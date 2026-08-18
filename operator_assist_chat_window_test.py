# -*- coding: utf-8 -*-
import asyncio
import importlib.util
import json
import subprocess
import time
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

try:
    import websockets

    WEBSOCKETS_AVAILABLE = True
    WEBSOCKETS_IMPORT_ERROR = ""
except Exception as error:
    websockets = None
    WEBSOCKETS_AVAILABLE = False
    WEBSOCKETS_IMPORT_ERROR = str(error)


WRAPPER_VERSION = "2026-07-14-chrome-bridge-test"
CURRENT_DIR = Path(__file__).resolve().parent
BASE_SCRIPT_CANDIDATES = [
    CURRENT_DIR / "operator_assist.py",
    Path("D:/OPERATOR_ASSIST/operator_assist.py"),
]
CHROME_BRIDGE_PORT = 9333
CHROME_BRIDGE_BASE_URL = f"http://127.0.0.1:{CHROME_BRIDGE_PORT}"
CHROME_BRIDGE_PROFILE_DIR = CURRENT_DIR / "chrome_bridge_profile"
CHATGPT_HOST_MARKERS = ("chatgpt.com", "chat.openai.com")


def load_base_module():
    for candidate in BASE_SCRIPT_CANDIDATES:
        if not candidate.exists():
            continue

        spec = importlib.util.spec_from_file_location("operator_assist_main_module", candidate)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, candidate

    raise FileNotFoundError("Main Operator Assist script was not found.")


_base_mod, _base_path = load_base_module()
_runtime = _base_mod._runtime
_runtime.LOGGER.info(
    "Loaded Chrome bridge test wrapper. base_source=%s wrapper_version=%s websockets_available=%s websockets_error=%s",
    _base_path,
    WRAPPER_VERSION,
    WEBSOCKETS_AVAILABLE,
    WEBSOCKETS_IMPORT_ERROR,
)


class OperatorAssistChromeBridgeTestApp(_base_mod.OperatorAssistApp):
    def __init__(self, root):
        super().__init__(root)
        self.ai_hint_var.set(
            "Тестовый режим Chrome Bridge: запускается отдельное окно Chrome, которым приложение управляет напрямую. "
            "Основная версия не затрагивается."
        )

    def _build_chat_bridge(self, parent):
        tk = _runtime.tk

        bridge = tk.Frame(parent, bg="white", highlightbackground="#d9e2ec", highlightthickness=1)
        bridge.pack(fill="both", pady=(12, 0))
        bridge.configure(padx=16, pady=16)
        bridge.grid_columnconfigure(0, weight=1)

        tk.Label(
            bridge,
            text="Chrome Bridge",
            bg="white",
            fg="#17324d",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            bridge,
            textvariable=self.ai_hint_var,
            bg="white",
            fg="#5f7184",
            font=("Segoe UI", 10),
            wraplength=1080,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        controls = tk.Frame(bridge, bg="white")
        controls.grid(row=2, column=0, sticky="ew")

        tk.Button(
            controls,
            text="Открыть Chrome Bridge",
            command=self.open_chatgpt_in_chrome,
            bg="#eef6ff",
            fg="#17406d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left")
        tk.Checkbutton(
            controls,
            text="Нажимать Enter после вставки",
            variable=self.auto_enter_var,
            bg="white",
            activebackground="white",
        ).pack(side="left", padx=(12, 0))

        tk.Label(
            bridge,
            text=(
                "Первый запуск откроет отдельный Chrome-профиль внутри папки OPERATOR_ASSIST. "
                "Если потребуется, войди в ChatGPT один раз именно в этом окне."
            ),
            bg="white",
            fg="#8091a5",
            font=("Segoe UI", 9),
            wraplength=1080,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(10, 0))

        operator_box = tk.Frame(bridge, bg="white")
        operator_box.grid(row=4, column=0, sticky="nsew", pady=(14, 10))
        operator_box.grid_columnconfigure(0, weight=1)

        tk.Label(
            operator_box,
            text="Условия подсказок",
            bg="white",
            fg="#17324d",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            operator_box,
            text="Этот текст ставится перед распознанной речью собеседника. Поле можно оставить пустым.",
            bg="white",
            fg="#5f7184",
            font=("Segoe UI", 10),
            wraplength=1080,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 8))

        self.operator_prompt_text = _runtime.ScrolledText(
            operator_box,
            wrap="word",
            font=("Segoe UI", 10),
            height=5,
            undo=True,
        )
        self.operator_prompt_text.grid(row=2, column=0, sticky="ew")
        initial_prompt = self.settings.get("operator_prompt", "")
        if initial_prompt:
            self.operator_prompt_text.insert("1.0", initial_prompt)

        buttons_top = tk.Frame(bridge, bg="white")
        buttons_top.grid(row=5, column=0, sticky="w", pady=(10, 8))
        tk.Button(
            buttons_top,
            text="Собрать всё",
            command=self.prepare_chat_prompt_full,
            bg="#eef6ff",
            fg="#17406d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons_top,
            text="Собрать новое",
            command=self.prepare_chat_prompt_delta,
            bg="#eef6ff",
            fg="#17406d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons_top,
            text="Копировать запрос",
            command=self.copy_chat_prompt,
            bg="#fff4df",
            fg="#5b4611",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons_top,
            text="Отправить новое в Chrome",
            command=self.send_new_prompt_to_chrome,
            bg="#e8f8f2",
            fg="#0b5d4f",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons_top,
            text="Отправить всё в Chrome",
            command=self.send_full_prompt_to_chrome,
            bg="#e9f3ff",
            fg="#17406d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left")

        buttons_bottom = tk.Frame(bridge, bg="white")
        buttons_bottom.grid(row=6, column=0, sticky="w", pady=(0, 10))
        tk.Button(
            buttons_bottom,
            text="Очистить условия",
            command=self.clear_operator_prompt,
            bg="#f6f8fb",
            fg="#17324d",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons_bottom,
            text="Сбросить метку отправки",
            command=self.reset_chat_send_marker,
            bg="#fdebec",
            fg="#8a2f39",
            relief="flat",
            padx=12,
            pady=8,
        ).pack(side="left")

        self.ai_prompt_text = _runtime.ScrolledText(
            bridge,
            wrap="word",
            font=("Consolas", 10),
            height=12,
            undo=True,
        )
        self.ai_prompt_text.grid(row=7, column=0, sticky="nsew")

    def _copy_prompt_to_clipboard(self, prompt_text):
        self.root.clipboard_clear()
        self.root.clipboard_append(prompt_text)
        self.root.update()
        _runtime.LOGGER.info("Prompt copied to clipboard for Chrome bridge. chars=%s", len(prompt_text))

    def _chrome_debug_json(self, path, timeout=2.5):
        request = urllib_request.Request(f"{CHROME_BRIDGE_BASE_URL}{path}", method="GET")
        with urllib_request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
        if not raw.strip():
            return {}
        return json.loads(raw)

    def _list_chrome_targets(self):
        try:
            payload = self._chrome_debug_json("/json/list", timeout=1.8)
            if isinstance(payload, list):
                return payload
        except Exception as error:
            _runtime.LOGGER.info("Chrome debug endpoint is not ready yet: %s", error)
        return []

    def _find_chatgpt_target(self):
        targets = self._list_chrome_targets()
        preferred = []

        for target in targets:
            if target.get("type") != "page":
                continue

            url = (target.get("url") or "").strip().lower()
            if any(marker in url for marker in CHATGPT_HOST_MARKERS):
                preferred.append(target)

        if preferred:
            preferred.sort(key=lambda item: item.get("title") or "")
            return preferred[-1]

        return None

    def _wait_for_chatgpt_target(self, timeout_sec):
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            target = self._find_chatgpt_target()
            if target:
                return target
            time.sleep(0.35)
        return None

    def _wait_for_debug_endpoint(self, timeout_sec):
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                version_payload = self._chrome_debug_json("/json/version", timeout=1.5)
                if isinstance(version_payload, dict) and version_payload.get("Browser"):
                    return True
            except Exception:
                pass
            time.sleep(0.35)
        return False

    def _launch_chrome_bridge(self, new_window):
        chrome_exe = _runtime.find_chrome_exe()
        if chrome_exe is None:
            raise RuntimeError("Chrome не найден на этом компьютере.")

        CHROME_BRIDGE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        args = [
            str(chrome_exe),
            f"--remote-debugging-port={CHROME_BRIDGE_PORT}",
            f"--user-data-dir={CHROME_BRIDGE_PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            _runtime.CHATGPT_URL,
        ]
        if new_window:
            args.insert(-1, "--new-window")
        else:
            args.insert(-1, "--new-tab")

        _runtime.LOGGER.info("Launching Chrome bridge. args=%s", args)
        subprocess.Popen(args)

    def _ensure_chrome_bridge_target(self):
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError(
                "В Python не найден модуль websockets, поэтому прямое управление Chrome сейчас недоступно. "
                f"Детали: {WEBSOCKETS_IMPORT_ERROR}"
            )

        target = self._find_chatgpt_target()
        if target:
            return target

        self._launch_chrome_bridge(new_window=True)
        if not self._wait_for_debug_endpoint(timeout_sec=12):
            raise RuntimeError(
                "Chrome Bridge не ответил на debug-порту. Проверь, открылось ли окно Chrome, и попробуй ещё раз."
            )

        target = self._wait_for_chatgpt_target(timeout_sec=16)
        if target:
            return target

        self._launch_chrome_bridge(new_window=False)
        target = self._wait_for_chatgpt_target(timeout_sec=10)
        if target:
            return target

        raise RuntimeError(
            "Не удалось открыть вкладку ChatGPT в Chrome Bridge. Открой это окно вручную и при необходимости войди в ChatGPT."
        )

    async def _cdp_call(self, websocket_url, method, params=None, timeout_sec=8):
        if params is None:
            params = {}

        async with websockets.connect(websocket_url, open_timeout=timeout_sec, close_timeout=1, max_size=4_000_000) as socket:
            message_id = 1
            payload = {"id": message_id, "method": method, "params": params}
            await socket.send(json.dumps(payload, ensure_ascii=False))

            while True:
                raw_message = await asyncio.wait_for(socket.recv(), timeout=timeout_sec)
                response = json.loads(raw_message)
                if response.get("id") != message_id:
                    continue
                if "error" in response:
                    raise RuntimeError(str(response["error"]))
                return response.get("result", {})

    def _build_chrome_injection_expression(self, prompt_text):
        auto_submit = "true" if self.auto_enter_var.get() else "false"
        encoded_prompt = json.dumps(prompt_text, ensure_ascii=False)

        return f"""
(async () => {{
  const text = {encoded_prompt};
  const autoSubmit = {auto_submit};
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const findInput = () => {{
    const selectors = [
      '#prompt-textarea',
      'textarea',
      'div[contenteditable="true"][data-lexical-editor="true"]',
      'div.ProseMirror[contenteditable="true"]',
      'div[contenteditable="true"]'
    ];

    for (const selector of selectors) {{
      const element = document.querySelector(selector);
      if (element && element.isConnected) {{
        return element;
      }}
    }}
    return null;
  }};

  let input = null;
  for (let attempt = 0; attempt < 60; attempt += 1) {{
    input = findInput();
    if (input) {{
      break;
    }}
    await sleep(250);
  }}

  if (!input) {{
    return {{
      ok: false,
      stage: 'find-input',
      title: document.title,
      url: location.href
    }};
  }}

  input.focus();
  const isTextarea = typeof input.value === 'string';

  if (isTextarea) {{
    const prototype = Object.getPrototypeOf(input);
    const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
    if (descriptor && descriptor.set) {{
      descriptor.set.call(input, text);
    }} else {{
      input.value = text;
    }}
    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
  }} else {{
    if (document.queryCommandSupported && document.queryCommandSupported('selectAll')) {{
      document.execCommand('selectAll', false, null);
      document.execCommand('delete', false, null);
      document.execCommand('insertText', false, text);
    }}

    if ((input.innerText || '').trim() !== text.trim()) {{
      input.textContent = text;
    }}

    input.dispatchEvent(new InputEvent('input', {{
      bubbles: true,
      inputType: 'insertText',
      data: text
    }}));
    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
  }}

  input.focus();

  if (!autoSubmit) {{
    return {{
      ok: true,
      submitted: false,
      title: document.title,
      url: location.href,
      tag: input.tagName,
      length: text.length
    }};
  }}

  const findSendButton = () => {{
    const selectors = [
      'button[data-testid="send-button"]',
      'button[aria-label*="Send"]',
      'button[aria-label*="send"]',
      'button[aria-label*="Отправ"]'
    ];

    for (const selector of selectors) {{
      const button = document.querySelector(selector);
      if (button && !button.disabled) {{
        return button;
      }}
    }}
    return null;
  }};

  let sendButton = null;
  for (let attempt = 0; attempt < 20; attempt += 1) {{
    sendButton = findSendButton();
    if (sendButton) {{
      break;
    }}
    await sleep(120);
  }}

  if (sendButton) {{
    sendButton.click();
    return {{
      ok: true,
      submitted: true,
      title: document.title,
      url: location.href,
      tag: input.tagName,
      length: text.length,
      submitMode: 'button'
    }};
  }}

  const keyboardPayload = {{
    key: 'Enter',
    code: 'Enter',
    keyCode: 13,
    which: 13,
    bubbles: true,
    cancelable: true
  }};

  input.dispatchEvent(new KeyboardEvent('keydown', keyboardPayload));
  input.dispatchEvent(new KeyboardEvent('keypress', keyboardPayload));
  input.dispatchEvent(new KeyboardEvent('keyup', keyboardPayload));
  await sleep(200);

  sendButton = findSendButton();
  if (sendButton) {{
    sendButton.click();
    return {{
      ok: true,
      submitted: true,
      title: document.title,
      url: location.href,
      tag: input.tagName,
      length: text.length,
      submitMode: 'keyboard-then-button'
    }};
  }}

  return {{
    ok: true,
    submitted: false,
    title: document.title,
    url: location.href,
    tag: input.tagName,
    length: text.length,
    submitMode: 'manual-enter'
  }};
}})()
""".strip()

    def _inject_prompt_into_chrome(self, prompt_text):
        target = self._ensure_chrome_bridge_target()
        websocket_url = target.get("webSocketDebuggerUrl")
        if not websocket_url:
            raise RuntimeError("У Chrome Bridge не найден debug WebSocket для вкладки ChatGPT.")

        _runtime.LOGGER.info(
            "Injecting prompt into Chrome Bridge. title=%s url=%s auto_enter=%s chars=%s",
            target.get("title"),
            target.get("url"),
            bool(self.auto_enter_var.get()),
            len(prompt_text),
        )

        asyncio.run(self._cdp_call(websocket_url, "Page.bringToFront"))
        result = asyncio.run(
            self._cdp_call(
                websocket_url,
                "Runtime.evaluate",
                {
                    "expression": self._build_chrome_injection_expression(prompt_text),
                    "awaitPromise": True,
                    "returnByValue": True,
                },
                timeout_sec=20,
            )
        )

        payload = ((result or {}).get("result") or {}).get("value")
        if not isinstance(payload, dict):
            raise RuntimeError("Chrome Bridge вернул неожиданный ответ при вставке текста.")

        _runtime.LOGGER.info("Chrome Bridge evaluation payload: %s", json.dumps(payload, ensure_ascii=False))
        if not payload.get("ok"):
            stage = payload.get("stage") or "unknown"
            title = payload.get("title") or "(без заголовка)"
            raise RuntimeError(
                f"Chrome Bridge не нашёл поле ввода ChatGPT. stage={stage}, title={title}. "
                "Открой окно ChatGPT в Bridge Chrome и, если нужно, войди в аккаунт."
            )

        return payload

    def open_chatgpt_in_chrome(self):
        try:
            target = self._ensure_chrome_bridge_target()
        except Exception as error:
            _runtime.LOGGER.exception("Failed to open Chrome Bridge")
            _runtime.messagebox.showerror(_runtime.APP_TITLE, str(error))
            return

        title = target.get("title") or "ChatGPT"
        self.ai_hint_var.set(
            f"Chrome Bridge готов. Найдена вкладка: {title}. Теперь можно отправлять текст напрямую в ChatGPT."
        )
        self._save_settings()

    def _send_prompt_to_chrome(self, prompt_text, sent_label):
        self._copy_prompt_to_clipboard(prompt_text)

        try:
            payload = self._inject_prompt_into_chrome(prompt_text)
        except Exception as error:
            _runtime.LOGGER.exception("Failed to send prompt to Chrome Bridge")
            self.ai_hint_var.set("Не удалось вставить текст в ChatGPT через Chrome Bridge. Запрос уже лежит в буфере обмена.")
            _runtime.messagebox.showinfo(
                _runtime.APP_TITLE,
                f"{error}\n\n"
                "Текст уже скопирован в буфер обмена, так что его можно сразу вставить вручную.",
            )
            return

        self._mark_prompt_sent()
        self._save_settings()

        if payload.get("submitted"):
            self.ai_hint_var.set(f"{sent_label} отправлен в ChatGPT через Chrome Bridge.")
        else:
            self.ai_hint_var.set(
                f"{sent_label} вставлен в ChatGPT через Chrome Bridge. Если нужно, нажми Enter вручную."
            )

    def send_new_prompt_to_chrome(self):
        try:
            prompt_text, snapshot_len = self._build_chat_prompt("delta")
        except ValueError as error:
            _runtime.messagebox.showinfo(_runtime.APP_TITLE, str(error))
            return

        self._render_prompt(prompt_text, snapshot_len)
        self._send_prompt_to_chrome(prompt_text, "Новый запрос")

    def send_full_prompt_to_chrome(self):
        try:
            prompt_text, snapshot_len = self._build_chat_prompt("full")
        except ValueError as error:
            _runtime.messagebox.showinfo(_runtime.APP_TITLE, str(error))
            return

        self._render_prompt(prompt_text, snapshot_len)
        self._send_prompt_to_chrome(prompt_text, "Полный запрос")


def main():
    _runtime.LOGGER.info("Entering Chrome bridge test wrapper main()")
    root = _runtime.tk.Tk()
    OperatorAssistChromeBridgeTestApp(root)
    _runtime.LOGGER.info("Chrome bridge test GUI mainloop starting")
    root.mainloop()
    _runtime.LOGGER.info("Chrome bridge test GUI loop finished")


if __name__ == "__main__":
    main()
