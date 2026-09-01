# Changelog

All notable repository-facing changes are documented here.

## v1.1.1 - 2026-09-01

GPU runtime reliability fix.

Highlights:

- bundled the CUDA 12 cuBLAS libraries required by `faster-whisper` during real GPU inference
- explicitly preload cuBLAS before starting the precise engine on Windows
- fall back to CPU instead of terminating the recognition worker when the CUDA runtime is unavailable
- added a regression test for Windows CUDA DLL discovery

## v1.1.0 - 2026-09-01

Recognition-quality and audio-routing release.

Highlights:

- added an optional high-accuracy `faster-whisper` `large-v3` mode for the caller channel with CUDA-first execution and safe CPU fallbacks
- moved Whisper initialization to a background loader with visible attempt, backend, and elapsed-time status
- added `Оба канала`, `Только собеседник`, and `Только оператор` capture modes so disconnected or intentionally disabled devices do not block a session
- added a live source probe that can find the active system-audio route while test audio is playing
- locked route selectors during active capture so the displayed source cannot diverge from the running worker
- improved cross-channel duplicate suppression when microphone spill reaches the caller route in either event order
- added deterministic tests for route modes, signal-source selection, Whisper loading progress, and delayed duplicate filtering
- refreshed the public-facing documentation and packaged-install structure introduced in `v1.0.1`

## v1.0.1 - 2026-08-20

Packaged-install cleanup release.

Highlights:

- moved editable packaged files into dedicated `config/`, `data/`, and `support/` folders
- cleaned the installed application root so it looks closer to a normal Windows product
- removed duplicated packaged helper files from the frozen bundle layout
- updated runtime path handling so source and packaged modes keep the correct writable locations
- expanded tests and release docs around the new packaged-install structure

## v1.0.0 - 2026-08-19

First stable public milestone for `OPERATOR_ASSIST`.

Highlights:

- consolidated Windows delivery around portable and installer release assets
- added guided first-launch readiness checks, diagnostics, and calmer startup behavior
- added source-install bootstrap scripts for repeatable setup from Git on clean machines
- improved deployment docs, smoke-check notes, and demo materials for public review
- aligned branding, packaging, and release automation for consistent versioned builds

## v0.1.1 - 2026-08-19

Repository, packaging, and release automation update.

Highlights:

- added a pinned Windows release workflow that builds portable and installer assets on GitHub
- added versioned publish-ready artifacts and SHA256 manifests to the local release pipeline
- added a first-launch readiness panel with model, device, and settings checks
- replaced aggressive startup error popups with a clearer in-app readiness flow
- added quick actions for opening the `models/` folder and the application root
- integrated branded application assets into the runtime and packaging pipeline
- added startup-readiness unit coverage for repository-safe regression checks

## v0.1.0 - 2026-08-19

Initial public release.

Highlights:

- dual-stream Windows desktop transcription workflow for operator scenarios
- offline Russian speech recognition with Vosk
- WASAPI loopback support with fallback capture paths
- IT-mode terminology normalization layer
- prompt-building workflow for AI handoff
- portable PyInstaller release pipeline
- Inno Setup installer scaffold
- repository documentation and architecture notes suitable for public review
