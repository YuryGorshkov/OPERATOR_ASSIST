# OPERATOR_ASSIST

![Windows](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4?logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/python-3.10-3776AB?logo=python&logoColor=white)
![Speech](https://img.shields.io/badge/STT-Vosk%20offline-2EA44F)
![Audio](https://img.shields.io/badge/audio-WASAPI%20loopback%20%2F%20Stereo%20Mix-8A2BE2)
![UI](https://img.shields.io/badge/UI-Tkinter%20%2B%20browser%20prototypes-F59E0B)

Windows-first real-time speech tooling for operator workflows, voice note capture, and AI-assisted prompt preparation.

`OPERATOR_ASSIST` is a product-style repository built around a practical problem: splitting speech streams in live conversations, transcribing them with local Russian speech recognition, and turning the result into something an operator can immediately use.

The project combines:

- a native desktop runtime for dual-stream transcription,
- a domain-specific technical-term correction layer,
- an experimental ChatGPT/Chrome bridge,
- browser-based voice note and speaker-text prototypes for lighter use cases.

Desktop UI is currently Russian-first. Repository documentation is English-first so the project is easier to review in a public portfolio.

## Showcase

![OPERATOR_ASSIST workflow overview](docs/images/operator-assist-overview.svg)

## Why This Project Is Interesting

- It solves a real UX problem, not a toy CRUD task: one stream is the operator microphone, the other is the system or caller audio path.
- It handles a non-trivial Windows audio capture problem using WASAPI loopback with fallback paths.
- It separates product surfaces: desktop workflow, prompt-building workflow, and browser-first lightweight prototypes.
- It uses an explicit post-processing layer for technical terminology instead of pretending raw STT output is always good enough.
- It keeps large runtime assets and local operator data out of git, which is closer to how a real desktop tool is maintained.

## Core Capabilities

- Simultaneous transcription of microphone audio and speaker/system audio into separate panels.
- Offline Russian speech recognition using Vosk models.
- Automatic detection of WASAPI loopback sources, with fallback to classic recording inputs such as Stereo Mix.
- Technical-term normalization layer with switchable IT terminology mode.
- Transcript export, clipboard copy, and local logging.
- Prompt assembly workflow for AI assistance based on the caller stream.
- Experimental Chrome bridge that can inject prepared prompts into a ChatGPT session.
- Lightweight browser prototypes for voice notes and a single-stream speaker-text window.

## System Architecture

```mermaid
flowchart LR
    Mic[Operator microphone] --> MicWorker[TranscriptionWorker]
    Speaker[WASAPI loopback / Stereo Mix] --> SpeakerWorker[Loopback or fallback worker]
    MicWorker --> Queue[UI event queue]
    SpeakerWorker --> Queue
    Dict[Technical term dictionary] --> PostProcess[Post-processing layer]
    Queue --> PostProcess
    PostProcess --> UI[Desktop UI]
    UI --> Export[Copy / Save TXT / Logs]
    UI --> Prompt[Prompt builder]
    Prompt --> Clipboard[Clipboard]
    Prompt --> Chrome[Experimental Chrome Bridge]
```

More detail: [docs/architecture.md](docs/architecture.md)

## Runtime Modes

| Mode | Entry point | Purpose | Status |
| --- | --- | --- | --- |
| Desktop operator assistant | `operator_assist.py` | Main product workflow with IT mode and dual transcription UX | Primary |
| Desktop loopback wrapper | `operator_assist_chat_bridge_v5_base.py` | Adds WASAPI loopback capture and Windows audio source selection | Primary dependency |
| Base runtime | `backups/operator_assist_chat_bridge_base.py` | Core recognition engine, UI queue, transcript handling, prompt builder | Primary dependency |
| Chrome bridge experiment | `operator_assist_chat_window_test.py` | Prompt injection into ChatGPT via Chrome remote debugging | Experimental |
| Browser voice notes | `app/index.html` | Lightweight voice-note UI using Web Speech API | Prototype |
| Browser speaker window | `app/speaker.html` | Lightweight speaker-text UI using Web Speech API | Prototype |

## Repository Layout

```text
OPERATOR_ASSIST/
├─ app/                               Browser prototypes (voice notes + speaker window)
├─ backups/
│  └─ operator_assist_chat_bridge_base.py
├─ docs/
│  ├─ architecture.md
│  ├─ deployment.md
│  └─ images/
├─ scripts/
│  ├─ paste_to_chat_window.vbs
│  └─ Serve-App-Tcp.ps1
├─ vendor/                            Vendored loopback dependencies for Windows runtime
├─ operator_assist.py                 Top wrapper with IT-mode terminology layer
├─ operator_assist_chat_bridge_v5_base.py
├─ operator_assist_chat_window_test.py
├─ requirements.txt
└─ technical_terms.json
```

Note: despite the filename, `backups/operator_assist_chat_bridge_base.py` is not archival trash. It is the active base runtime module used by the layered wrappers.

## Tech Stack

- Python 3.10
- Tkinter for the native Windows desktop UI
- Vosk for offline speech recognition
- `sounddevice` for microphone/input capture
- `soundcard` + NumPy + CFFI for WASAPI loopback capture
- WebSockets for the Chrome bridge experiment
- HTML/CSS/JavaScript + Web Speech API for browser prototypes
- Local JSON/text persistence for settings, prompt templates, logs, and transcripts

## Quick Start

### 1. Install Python

The desktop runtime was developed against Python `3.10.x`.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add a Vosk model

Place one supported Russian model under the local `models/` directory. The runtime checks these paths:

- `models/vosk-model-ru-0.42`
- `models/vosk-model-ru-0.22`
- `models/vosk-model-small-ru-0.22`

Speech models are intentionally excluded from git because they are large runtime assets, not source code.

### 4. Launch the main desktop app

Windows launcher:

```text
Run-Operator-Assist.cmd
```

Main Python entry point:

```bash
python operator_assist.py
```

### 5. Launch the browser prototypes

Serve the local `app/` directory with the included PowerShell server:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\Serve-App-Tcp.ps1
```

Then open:

- `http://127.0.0.1:8765/`
- `http://127.0.0.1:8765/speaker.html`

## Dependency Strategy

This repository uses a mixed dependency model on purpose:

- `vosk`, `sounddevice`, and `websockets` are expected from the Python environment.
- `soundcard`, `numpy`, `cffi`, and related binaries are also vendored under `vendor/` to make the loopback path easier to move between Windows machines.
- Large Vosk models, transcripts, logs, and local settings are kept outside version control.

That is not the cleanest packaging story yet, but it is an explicit trade-off between reproducibility and practical Windows portability.

## Engineering Decisions

### Local STT over cloud STT

The primary workflow is designed around local or offline recognition for privacy, latency, and independence from API quotas.

### Layered wrappers instead of one giant script

The codebase evolved into a layered runtime:

- base recognition engine,
- loopback-enabled desktop wrapper,
- IT-mode enrichment wrapper,
- Chrome bridge experiment.

This keeps experiments from rewriting the core transcription flow.

### Post-processing dictionary instead of model fine-tuning

For technical interviews and support scenarios, improving the last 10% of domain vocabulary is often more useful than replacing the recognizer. The IT mode is implemented as a controlled correction layer over raw transcript output.

### Separate UX surfaces for separate jobs

The repository does not force one interface to solve every scenario. It includes:

- a desktop operator workflow,
- a browser voice-note workflow,
- a browser speaker-only window,
- an experimental AI handoff flow.

## Current Constraints

- Windows-first implementation for the primary desktop mode.
- The desktop launchers currently assume a local Python installation path and are not yet fully environment-agnostic.
- The Chrome bridge is experimental and should be treated as an optional workflow, not the default.
- There is no automated test suite yet.
- The repository is optimized for practical usage and iteration speed, not for library-style packaging purity.

## What I Would Do Next For Production

- Replace path-specific launchers with a packaged installer or embedded runtime.
- Add automated audio-fixture regression tests for transcription and post-processing.
- Introduce VAD or diarization to reduce noise and cross-talk.
- Move prompt engineering into configurable profiles instead of hard-coded workflow assumptions.
- Add a knowledge-base layer for company-specific support content.
- Separate stable runtime modules from experiments into clearer package boundaries.

## Additional Documentation

- [Architecture notes](docs/architecture.md)
- [Deployment and packaging notes](docs/deployment.md)

## Portfolio Framing

This project is strongest when presented as:

- a Windows audio-capture and speech-workflow engineering project,
- a local-first operator productivity tool,
- an example of iterative productization from prototype to multi-surface utility.

It is not positioned as "perfect AI". It is positioned as a practical system that makes difficult audio and workflow problems tractable on a real operator machine.
