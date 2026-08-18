const STORAGE_KEY = "speaker_text_window_v1";

const elements = {
  startButton: document.getElementById("start-btn"),
  stopButton: document.getElementById("stop-btn"),
  copyButton: document.getElementById("copy-btn"),
  clearButton: document.getElementById("clear-btn"),
  languageSelect: document.getElementById("language-select"),
  finalText: document.getElementById("final-text"),
  interimText: document.getElementById("interim-text"),
  statusPill: document.getElementById("status-pill"),
  hint: document.getElementById("hint")
};

const SpeechRecognitionApi =
  window.SpeechRecognition || window.webkitSpeechRecognition;

const state = {
  recognition: null,
  listening: false,
  keepListening: false
};

function loadSavedText() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      elements.finalText.value = saved;
    }
  } catch (error) {
    console.error("Could not load saved speaker text", error);
  }
}

function saveText() {
  try {
    localStorage.setItem(STORAGE_KEY, elements.finalText.value);
  } catch (error) {
    console.error("Could not save speaker text", error);
  }
}

function setStatus(message, recording = false) {
  elements.statusPill.textContent = message;
  elements.statusPill.classList.toggle("recording", recording);
}

function updateButtons() {
  elements.startButton.disabled = !state.recognition || state.listening;
  elements.stopButton.disabled = !state.listening;
}

function appendFinalText(text) {
  if (!text.trim()) {
    return;
  }

  const current = elements.finalText.value;
  const spacer = current && !/[\s\n]$/.test(current) ? " " : "";
  elements.finalText.value = `${current}${spacer}${text.trim()}`;
  elements.finalText.scrollTop = elements.finalText.scrollHeight;
  saveText();
}

async function copyText() {
  try {
    await navigator.clipboard.writeText(elements.finalText.value || "");
    elements.hint.textContent = "Текст скопирован в буфер обмена.";
  } catch (error) {
    elements.hint.textContent = "Не удалось скопировать текст.";
  }
}

function clearText() {
  const confirmed = window.confirm("Очистить текст собеседника?");
  if (!confirmed) {
    return;
  }

  elements.finalText.value = "";
  elements.interimText.textContent = "Пока пусто";
  saveText();
}

function setupRecognition() {
  if (!SpeechRecognitionApi) {
    setStatus("Распознавание недоступно");
    elements.interimText.textContent = "Откройте это окно через Chrome или Edge.";
    elements.hint.textContent = "Web Speech API не найден.";
    updateButtons();
    return;
  }

  state.recognition = new SpeechRecognitionApi();
  state.recognition.continuous = true;
  state.recognition.interimResults = true;
  state.recognition.lang = elements.languageSelect.value;

  state.recognition.onstart = () => {
    state.listening = true;
    setStatus("Слушаю источник", true);
    elements.hint.textContent = "Если у вас гарнитура, для речи собеседника нужен Стерео микшер.";
    updateButtons();
  };

  state.recognition.onend = () => {
    state.listening = false;
    updateButtons();

    if (state.keepListening) {
      window.setTimeout(() => {
        try {
          state.recognition.lang = elements.languageSelect.value;
          state.recognition.start();
        } catch (error) {
          state.keepListening = false;
          setStatus("Не удалось продолжить");
        }
      }, 250);
      return;
    }

    setStatus("Готово");
    if (!elements.interimText.textContent.trim()) {
      elements.interimText.textContent = "Пока пусто";
    }
  };

  state.recognition.onerror = (event) => {
    state.keepListening = false;
    state.listening = false;
    updateButtons();

    if (event.error === "not-allowed") {
      setStatus("Нет доступа");
      elements.hint.textContent = "Разрешите доступ к микрофону для этого окна.";
      return;
    }

    if (event.error === "no-speech") {
      setStatus("Нет речи");
      elements.hint.textContent = "Проверьте, что для окна выбран Стерео микшер или нужный источник.";
      return;
    }

    setStatus(`Ошибка: ${event.error}`);
    elements.hint.textContent = "Попробуйте остановить и запустить прослушивание снова.";
  };

  state.recognition.onresult = (event) => {
    let interim = "";

    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      const transcript = result[0].transcript;

      if (result.isFinal) {
        appendFinalText(transcript);
      } else {
        interim += transcript;
      }
    }

    elements.interimText.textContent = interim.trim() || "Пока пусто";
  };

  updateButtons();
}

function startRecognition() {
  if (!state.recognition) {
    return;
  }

  state.keepListening = true;
  state.recognition.lang = elements.languageSelect.value;

  try {
    state.recognition.start();
  } catch (error) {
    setStatus("Не удалось запустить");
  }
}

function stopRecognition() {
  state.keepListening = false;
  if (state.recognition && state.listening) {
    state.recognition.stop();
  }
}

function attachEvents() {
  elements.startButton.addEventListener("click", startRecognition);
  elements.stopButton.addEventListener("click", stopRecognition);
  elements.copyButton.addEventListener("click", copyText);
  elements.clearButton.addEventListener("click", clearText);

  elements.languageSelect.addEventListener("change", () => {
    if (state.recognition) {
      state.recognition.lang = elements.languageSelect.value;
    }
  });

  elements.finalText.addEventListener("input", saveText);

  window.addEventListener("beforeunload", () => {
    saveText();
    stopRecognition();
  });
}

function init() {
  loadSavedText();
  attachEvents();
  setupRecognition();
}

init();
