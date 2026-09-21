# Changelog

All notable repository-facing changes are documented here.

## Unreleased

No unreleased changes.

## v1.4.1 - 2026-09-21

Precise-decoder search tuning release.

Highlights:

- increase the pause-aware Whisper beam width from 5 to 8 without changing the selected model or audio route
- reduce WER from 8.11% to 6.80% across 32 correlated tempo stress cases up to 1.5x speed
- reduce WER from 6.15% to 5.38% on nine separately verified clips from three readers
- preserve identical WER on the verified 92-second continuous-stream development sample
- retain beam 5 and beam 10 as lab-only controls; beam 10 added cost without another accuracy gain

Beam 8 increased measured processing time by about 6% on these local checks. The corpus is small, single-book and partly synthetic, so the result is directional rather than a universal accuracy claim.

## v1.4.0 - 2026-09-21

Pause-aware recognition tuning release.

Highlights:

- delay phrase-boundary decoding from 450 ms to 600 ms to avoid cutting natural Russian pauses too early
- reduce WER on the verified 92-second continuous-stream development sample from 15.38% to 11.54%
- preserve WER 6.15% and CER 2.00% on nine separately verified clips from three readers
- improve measured real-time factor on both development checks without changing the selected Whisper model
- add lab-only one-variable pause profiles so future tuning remains reproducible and separate from production defaults

These measurements use a small single-book development corpus and are directional, not a universal accuracy claim.

## v1.3.2 - 2026-09-21

Recognition-profile persistence hotfix.

Highlights:

- persist the selected precise Whisper model together with the audio route and compute device
- prevent `large-v3-turbo` from silently reverting to the heavier `large-v3` after restart
- cover the production chat-wrapper settings path with a restart regression test

## v1.3.1 - 2026-09-21

Audio-input diagnostics hotfix.

Highlights:

- detect sustained near-full-scale PCM samples before recognition
- show a clear `перегруз` state with the measured clipping percentage
- keep the overload warning visible for the session and explain which Windows level to reduce
- preserve compatibility with older three-field level events used by tests and wrappers
- verify both Whisper profiles on the same real Stereo Mix capture; no phrase-specific filtering is used

## v1.3.0 - 2026-09-20

Selectable Whisper performance profiles and measured startup improvements.

Highlights:

- add `large-v3-turbo` as an optional fast precise-recognition model while preserving `large-v3`
- let users choose the Whisper model independently from the GPU/CPU compute selector
- open complete local model snapshots directly instead of resolving the hub cache on every launch
- log CUDA preparation, model-open and total loading durations separately
- retain compatibility with settings saved before the model selector existed
- validate the production pause-aware engine on nine verified Russian samples: the local development corpus measured WER 6.15% and RTF 0.285 for turbo versus WER 9.23% and RTF 0.501 for large-v3; this small single-book set is directional, not a universal quality claim

- added separate, opt-in offline ASR lab tooling with nine single-factor profiles
- compare the unchanged desktop baseline against context, term-hint, buffering, VAD, beam-search and preprocessing experiments
- report corpus-weighted WER/CER, raw results, term coverage, input diagnostics and offline processing time
- validate human-verified audio/text pairs and reject alternate-voice passage leakage or overlapping audio across data splits
- support authorized local audio conversion and verified-pair export without starting recording or training
- preserve per-run errors, source/model hashes and completion status; never overwrite earlier runs
- exclude experiment recordings, references, reports and checkpoints from Git
- install runtime dependencies in CI and run the offline lab regressions without downloading speech models
- initialize the Windows CI Python cache inside a runner step instead of using runner context in job-level environment

Model fine-tuning remains separate from runtime tuning and requires a larger licensed corpus.

## v1.2.2 - 2026-09-20

Release-metadata consistency fix.

Highlights:

- align the application, wrapper, package, and installer version shown at runtime
- add a repository contract test that prevents future version drift
- replace fixed six-second Whisper cuts with pause-aware streaming and timestamp-owned boundary overlap
- preserve original PCM silence for VAD instead of removing the evidence needed to find safe phrase boundaries
- keep the decoder's non-speech guard active without matching or blacklisting recognized phrases
- suppress isolated one-character shutdown debris while preserving short replies such as `да`
- promote the streaming strategy only after verified multi-voice evaluation and exact replay of a captured control session
- report the active Whisper or combined Vosk/Whisper route correctly in logs, hints, and saved transcripts

## v1.2.1 - 2026-09-20

Precise-recognition reliability fix.

Highlights:

- reject Whisper segments that the decoder classifies as non-speech instead of filtering known phrases
- preserve speech when confidence metadata is absent or invalid, preventing compatibility-related data loss
- keep rejected text out of the context supplied to subsequent recognition windows
- record aggregate rejection diagnostics without writing recognized content to the application log
- validate the change against a real captured session and multi-voice, variable-tempo regression corpora

## v1.2.0 - 2026-09-01

Startup and precise-recognition tuning release.

Highlights:

- stopped loading the multi-gigabyte Vosk model for `Только собеседник + Точный (Whisper)` sessions
- preload the saved recognition engine in the background as soon as the application opens
- persist capture and speaker-recognition modes across restarts
- increased Whisper's continuous-speech window from 3.2 to 6 seconds to avoid cutting names and sentences into tiny fragments
- feed a bounded tail of the previous result back as recognition context
- log audio duration, inference duration, and real-time factor for every Whisper segment
- added a saved `GPU/CUDA` or `CPU` Whisper compute selector; CPU mode never allocates CUDA, while GPU mode retains a safe CPU fallback
- unload the previous Whisper instance before changing compute devices to avoid duplicate RAM or VRAM use
- added regression coverage for lazy Vosk loading and Whisper context continuity

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
