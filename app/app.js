const STORAGE_KEY = "voice_notes_desktop_v1";

const elements = {
  notesList: document.getElementById("notes-list"),
  noteCount: document.getElementById("note-count"),
  editor: document.getElementById("editor"),
  titleInput: document.getElementById("title-input"),
  micButton: document.getElementById("mic-btn"),
  stopButton: document.getElementById("stop-btn"),
  deleteButton: document.getElementById("delete-btn"),
  newNoteButton: document.getElementById("new-note-btn"),
  copyButton: document.getElementById("copy-btn"),
  exportButton: document.getElementById("export-btn"),
  languageSelect: document.getElementById("language-select"),
  statusPill: document.getElementById("status-pill"),
  autosaveState: document.getElementById("autosave-state"),
  interimText: document.getElementById("interim-text"),
  noteTemplate: document.getElementById("note-item-template")
};

const SpeechRecognitionApi =
  window.SpeechRecognition || window.webkitSpeechRecognition;

const state = {
  notes: [],
  currentId: null,
  recognition: null,
  listening: false,
  keepListening: false,
  saveTimer: null
};

function createId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }

  return `note-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createNote(content = "", title = "") {
  return {
    id: createId(),
    title,
    content,
    updatedAt: new Date().toISOString()
  };
}

function readStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }

    return JSON.parse(raw);
  } catch (error) {
    console.error("Storage read failed", error);
    return null;
  }
}

function writeStorage() {
  const payload = {
    notes: state.notes,
    currentId: state.currentId
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  elements.autosaveState.textContent = `Сохранено ${formatDateTime(new Date().toISOString())}`;
}

function scheduleSave() {
  window.clearTimeout(state.saveTimer);
  elements.autosaveState.textContent = "Сохраняю...";
  state.saveTimer = window.setTimeout(writeStorage, 250);
}

function loadState() {
  const saved = readStorage();

  if (saved && Array.isArray(saved.notes) && saved.notes.length > 0) {
    state.notes = saved.notes;
    state.currentId = saved.currentId && saved.notes.some((note) => note.id === saved.currentId)
      ? saved.currentId
      : saved.notes[0].id;
    return;
  }

  const firstNote = createNote();
  state.notes = [firstNote];
  state.currentId = firstNote.id;
  writeStorage();
}

function getCurrentNote() {
  return state.notes.find((note) => note.id === state.currentId) || null;
}

function deriveTitle(note) {
  const explicitTitle = (note.title || "").trim();
  if (explicitTitle) {
    return explicitTitle;
  }

  const derived = (note.content || "").replace(/\s+/g, " ").trim();
  return derived ? derived.slice(0, 40) : "Новая заметка";
}

function getPreview(note) {
  const preview = (note.content || "").replace(/\s+/g, " ").trim();
  return preview ? preview.slice(0, 70) : "Пока пусто";
}

function formatDateTime(isoString) {
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(isoString));
}

function sortNotes() {
  state.notes.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
}

function renderNoteList() {
  sortNotes();
  elements.notesList.innerHTML = "";
  elements.noteCount.textContent = String(state.notes.length);

  for (const note of state.notes) {
    const fragment = elements.noteTemplate.content.cloneNode(true);
    const button = fragment.querySelector(".note-item");
    const title = fragment.querySelector(".note-item-title");
    const date = fragment.querySelector(".note-item-date");
    const preview = fragment.querySelector(".note-item-preview");

    title.textContent = deriveTitle(note);
    date.textContent = formatDateTime(note.updatedAt);
    preview.textContent = getPreview(note);

    if (note.id === state.currentId) {
      button.classList.add("active");
    }

    button.addEventListener("click", () => {
      state.currentId = note.id;
      render();
      scheduleSave();
    });

    elements.notesList.appendChild(fragment);
  }
}

function renderEditor() {
  const note = getCurrentNote();
  if (!note) {
    return;
  }

  elements.titleInput.value = note.title || "";
  elements.editor.value = note.content || "";
}

function renderStatus(message, isRecording = false) {
  elements.statusPill.textContent = message;
  elements.statusPill.classList.toggle("recording", isRecording);
}

function render() {
  renderNoteList();
  renderEditor();
}

function updateCurrentNote(patch) {
  const note = getCurrentNote();
  if (!note) {
    return;
  }

  Object.assign(note, patch, { updatedAt: new Date().toISOString() });
  renderNoteList();
  scheduleSave();
}

function appendToCurrentNote(text) {
  const note = getCurrentNote();
  if (!note || !text.trim()) {
    return;
  }

  const currentText = note.content || "";
  const spacer = currentText && !/[\s\n]$/.test(currentText) ? " " : "";
  note.content = `${currentText}${spacer}${text.trim()}`;
  note.updatedAt = new Date().toISOString();

  elements.editor.value = note.content;
  renderNoteList();
  scheduleSave();
}

function createNewNote() {
  const note = createNote();
  state.notes.unshift(note);
  state.currentId = note.id;
  render();
  scheduleSave();
  elements.titleInput.focus();
}

function deleteCurrentNote() {
  if (state.notes.length === 1) {
    state.notes = [createNote()];
    state.currentId = state.notes[0].id;
    render();
    scheduleSave();
    return;
  }

  state.notes = state.notes.filter((note) => note.id !== state.currentId);
  state.currentId = state.notes[0].id;
  render();
  scheduleSave();
}

function exportCurrentNote() {
  const note = getCurrentNote();
  if (!note) {
    return;
  }

  const title = deriveTitle(note).replace(/[<>:"/\\|?*]+/g, "_");
  const blob = new Blob([note.content || ""], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${title}.txt`;
  link.click();
  URL.revokeObjectURL(url);
}

async function copyCurrentNote() {
  const note = getCurrentNote();
  if (!note) {
    return;
  }

  try {
    await navigator.clipboard.writeText(note.content || "");
    elements.autosaveState.textContent = "Текст скопирован в буфер обмена";
  } catch (error) {
    elements.autosaveState.textContent = "Не удалось скопировать текст";
  }
}

function updateSpeechButtons() {
  elements.micButton.disabled = !state.recognition || state.listening;
  elements.stopButton.disabled = !state.listening;
}

function setupRecognition() {
  if (!SpeechRecognitionApi) {
    renderStatus("Распознавание речи недоступно в этом браузере");
    elements.micButton.disabled = true;
    elements.stopButton.disabled = true;
    elements.interimText.textContent = "Попробуйте открыть приложение через Chrome или Edge.";
    return;
  }

  state.recognition = new SpeechRecognitionApi();
  state.recognition.continuous = true;
  state.recognition.interimResults = true;
  state.recognition.lang = elements.languageSelect.value;

  state.recognition.onstart = () => {
    state.listening = true;
    renderStatus("Идет запись", true);
    elements.interimText.textContent = "Слушаю...";
    updateSpeechButtons();
  };

  state.recognition.onend = () => {
    state.listening = false;
    updateSpeechButtons();

    if (state.keepListening) {
      window.setTimeout(() => {
        try {
          state.recognition.lang = elements.languageSelect.value;
          state.recognition.start();
        } catch (error) {
          renderStatus("Не удалось продолжить запись");
          state.keepListening = false;
          updateSpeechButtons();
        }
      }, 250);
      return;
    }

    renderStatus("Готово");
    elements.interimText.textContent = "Пока пусто";
  };

  state.recognition.onerror = (event) => {
    state.keepListening = false;
    state.listening = false;
    updateSpeechButtons();

    if (event.error === "not-allowed") {
      renderStatus("Нет доступа к микрофону");
      elements.interimText.textContent = "Разрешите доступ к микрофону и запустите запись снова.";
      return;
    }

    if (event.error === "no-speech") {
      renderStatus("Речь не распознана");
      elements.interimText.textContent = "Говорите ближе к микрофону.";
      return;
    }

    renderStatus(`Ошибка: ${event.error}`);
    elements.interimText.textContent = "Попробуйте остановить и запустить запись снова.";
  };

  state.recognition.onresult = (event) => {
    let interim = "";

    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      const transcript = result[0].transcript;

      if (result.isFinal) {
        appendToCurrentNote(transcript);
      } else {
        interim += transcript;
      }
    }

    elements.interimText.textContent = interim.trim() || "Пока пусто";
  };

  updateSpeechButtons();
}

function startListening() {
  if (!state.recognition) {
    return;
  }

  state.keepListening = true;
  state.recognition.lang = elements.languageSelect.value;

  try {
    state.recognition.start();
  } catch (error) {
    renderStatus("Не удалось запустить запись");
  }
}

function stopListening() {
  state.keepListening = false;
  if (state.recognition && state.listening) {
    state.recognition.stop();
  }
}

function attachEvents() {
  elements.newNoteButton.addEventListener("click", createNewNote);

  elements.deleteButton.addEventListener("click", () => {
    const confirmed = window.confirm("Удалить текущую заметку?");
    if (confirmed) {
      deleteCurrentNote();
    }
  });

  elements.exportButton.addEventListener("click", exportCurrentNote);
  elements.copyButton.addEventListener("click", copyCurrentNote);
  elements.micButton.addEventListener("click", startListening);
  elements.stopButton.addEventListener("click", stopListening);

  elements.languageSelect.addEventListener("change", () => {
    if (state.recognition) {
      state.recognition.lang = elements.languageSelect.value;
    }
  });

  elements.titleInput.addEventListener("input", () => {
    updateCurrentNote({ title: elements.titleInput.value });
  });

  elements.editor.addEventListener("input", () => {
    updateCurrentNote({ content: elements.editor.value });
  });

  window.addEventListener("beforeunload", () => {
    window.clearTimeout(state.saveTimer);
    writeStorage();
    stopListening();
  });
}

function init() {
  loadState();
  render();
  attachEvents();
  setupRecognition();
}

init();
