# OPERATOR_ASSIST Architecture Notes

## Design Goal

`OPERATOR_ASSIST` is not a generic speech-to-text demo. Its design target is a Windows operator workflow where:

- one stream is the operator microphone,
- another stream is the caller or system audio,
- the transcript needs to be actionable immediately,
- the workflow may require a human-in-the-loop AI handoff.

That framing drives the architecture more than raw ML ambition.

## Runtime Layers

### 1. Base desktop runtime

File: `operator_assist_runtime/base_runtime.py`

Responsibilities:

- UI queue orchestration
- background Vosk model loading
- microphone or input capture through `sounddevice`
- transcript accumulation
- duplicate suppression
- transcript export
- prompt generation
- clipboard or Chrome handoff helpers

This module contains the core `TranscriptionWorker` and `OperatorAssistApp` abstractions.

For compatibility, the old path under `backups/operator_assist_chat_bridge_base.py` is retained as a shim while the repository transitions to the cleaner package layout.

### 2. Loopback-enabled Windows runtime

File: `operator_assist_chat_bridge_v5_base.py`

Responsibilities:

- detect WASAPI-capable output devices,
- expose loopback capture as a selectable source,
- fall back to standard recording devices when loopback is unavailable,
- rebind runtime paths to the current working directory.

The key point here is that caller or system audio is treated as a first-class input path rather than an afterthought.

### 3. IT terminology wrapper

File: `operator_assist.py`

Responsibilities:

- load and cache `technical_terms.json`,
- expose switchable IT-mode terminology replacement,
- apply domain-specific normalization after recognition,
- preserve the base dual-stream transcription UX.

This keeps domain adaptation lightweight: no model retraining, just controlled post-processing.

### 4. Chrome bridge experiment

File: `operator_assist_chat_window_test.py`

Responsibilities:

- construct AI-ready prompts from the speaker transcript,
- connect to a Chrome instance via remote debugging,
- inject prompt text into a ChatGPT page.

This is intentionally isolated as an experimental workflow and should not be considered the stable backbone of the project.

### 5. Browser prototypes

Files:

- `app/index.html`
- `app/app.js`
- `app/speaker.html`
- `app/speaker.js`

Responsibilities:

- quick voice-note capture,
- quick single-stream speaker transcription,
- browser-native storage via `localStorage`,
- Web Speech API-based recognition.

These prototypes are useful for demonstrating product surface exploration, but they are less controllable than the offline desktop runtime.

## Desktop Audio Pipeline

### Operator microphone

1. Enumerate recording devices through `sounddevice`.
2. Select a microphone input.
3. Stream PCM chunks into a recognition worker.
4. Push recognition events into the UI queue.

### Caller or system audio

Preferred path:

1. Enumerate loopback-capable devices through `soundcard`.
2. Open WASAPI loopback recorder.
3. Convert float frames to 16-bit PCM.
4. Resample when required.
5. Push chunks into a dedicated recognition worker.

Fallback path:

1. Use a classic recording input such as Stereo Mix.
2. Feed it through the standard `sounddevice` worker path.

This dual-path strategy is important because Windows audio environments vary a lot across machines.

## Recognition and UI Flow

1. The model loads in a background thread.
2. Capture workers push audio chunks into bounded queues.
3. Recognition workers decode Vosk results incrementally.
4. Final and interim results are marshaled back through the UI queue.
5. The UI updates separate panels for operator and speaker text.
6. Final speaker text is additionally used as prompt input for AI workflows.

The queue-based approach prevents the GUI thread from becoming the recognition engine.

## Domain Correction Layer

Technical vocabulary is handled as a deterministic post-processing layer:

- normalization of case and spacing,
- global replacement dictionary,
- optional mode-specific replacements,
- IT-mode toggle persisted in settings.

This is a practical design choice: for operator assistance, deterministic correction of common terms can be more valuable than chasing a heavier model.

## State and Local Data

Local runtime artifacts include:

- `operator_assist_settings.json`
- `technical_terms.json`
- `chatgpt_prompt_template.txt`
- `logs/`
- `transcripts/`
- `models/`

Only the source-level defaults belong in git. User-specific outputs and large models do not.

## Key Trade-Offs

### Why Tkinter?

Because the core value of this project is workflow utility, audio routing, and transcription logic, not bleeding-edge desktop rendering. Tkinter keeps the native tool easy to run and easy to modify.

### Why keep vendor binaries in-repo?

Because Windows loopback support is one of the most fragile parts of the setup. Vendoring critical pieces improves practical portability at the cost of some repository cleanliness.

### Why keep experiments in the same repository?

Because the experimental flows directly exercise the same transcription core and workflow assumptions. Splitting them too early would make iteration slower and hide the product evolution story.

## Production Hardening Priorities

If this were being prepared for broader deployment, the most valuable next moves would be:

1. packaged installer with embedded runtime,
2. automatic dependency or bootstrap script,
3. regression tests on saved audio fixtures,
4. cleaner module boundaries,
5. explicit observability around device selection, latency, and recognition quality,
6. configurable knowledge profiles beyond the current IT dictionary.
