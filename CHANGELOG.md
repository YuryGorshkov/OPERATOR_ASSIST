# Changelog

All notable repository-facing changes are documented here.

## Unreleased

## v1.5.3 - 2026-09-23

Memory and channel-routing hotfix.

Highlights:

- reuse one Whisper instance for both operator and caller channels in precise mode instead of retaining Vosk and Whisper together
- keep application-owned temporary files and caches under the local `data/` directory beside the installed executable
- keep the PyInstaller build cache under the explicitly selected build temp directory instead of the system drive
- release inactive recognition models when switching modes and during application shutdown
- align cross-channel duplicate detection to captured audio time instead of delayed decoder completion time
- remove an already-rendered microphone duplicate when the matching Whisper result arrives later
- expand regression coverage for shared-model routing, local runtime storage and delayed duplicate suppression

## v1.5.2 - 2026-09-23

Real-world recognition hardening release.

Highlights:

- reproduce the confident `Субтитры создавал DimaTorzok` Whisper hallucination on a publisher's music-only podcast intro
- suppress only the reproduced `DimaTorzok` subtitle-credit signature in both provisional and final precise-mode output
- preserve other subtitle-related phrases and the existing probability-based no-speech guard
- validate the fix against the same three unchanged music intros: zero emitted words and zero dropped audio blocks
- validate both selectable Whisper models against the same 83-second accented podcast sample with no dropped audio blocks
- measure `large-v3` at 18.11% WER and 9.02% CER versus `large-v3-turbo` at 32.28% WER and 17.06% CER on that development sample
- retain both profiles because the full model improves accuracy while increasing median final-event latency from 2.51 to 3.84 seconds on the tested GPU
- clarify the model selector and in-app guidance as `Максимальная точность` versus `Быстрый режим`

These measurements describe a small local development sample and the tested machine; they are not a general accuracy guarantee.

## v1.5.1 - 2026-09-22

Real-time recognition diagnostics and silence-boundary release.

Highlights:

- add monotonic end-to-end latency telemetry for audio queueing, recognition, UI dispatch and estimated speech-end delivery
- add a reproducible wall-clock ASR replay that uses independent audio, recognition and UI queues with the desktop application's production timing
- report WER/CER per speaker, queue drops, queue depth, p50/p95 latency and review-only recurring error candidates
- trim confirmed trailing silence before pause-triggered Whisper decoding while retaining a 350 ms VAD guard
- remove the recurring `DimaTorzok` subtitle-credit hallucination from the affected live-style development case without phrase-specific filtering
- reduce live-style WER from 11.54% to 7.69% and CER from 7.29% to 2.59% on nine verified clips from three readers
- measure complete-text latency at 2.02 seconds p50 and 2.30 seconds p95 on the tested GPU, with zero dropped audio blocks
- preserve the existing 5.38% WER and 1.88% CER in the isolated offline regression control

These measurements use a small single-book development corpus and describe the tested machine. Error candidates are never applied automatically and still require human review.

## v1.5.0 - 2026-09-22

User vocabulary release.

Highlights:

- add a `Словарь` action for exact corrections of recurring names, companies, products and domain terms
- keep user rules in the simple editable `config/custom_terms.txt` format: `recognized form = preferred form`
- reload custom rules before every transcription session without restarting the application
- give explicit user rules priority over built-in and optional IT-mode replacements
- ignore malformed or oversized rules safely, cap the file at 500 active entries and report invalid line numbers in the log
- package the editable vocabulary in both portable and installer layouts and document its use
- reject decoder-level hotword bias after the local development comparison worsened WER from 5.38% to 17.69%; the decoder remains unchanged
- reduce WER from 5.38% to 3.08% on the existing nine-clip development set with three explicit post-correction rules and no added inference cost

The measured gain is specific to the small verified development sample. User rules are deterministic corrections for known recurring errors, not general model fine-tuning.

## v1.4.2 - 2026-09-22

Responsive precise-transcription release.

Highlights:

- show one fast provisional Whisper result after 2.5 seconds of continuous speech while preserving the beam-8 final decoder
- reduce measured first visible text from about 5.6 seconds to about 3.4 seconds on the verified 92-second development stream
- preserve the final 11.54% WER and 3.14% CER measured on that stream; provisional text never enters saved transcripts or copied final text
- keep preview work bounded to one greedy pass per pending phrase; measured total RTF remains 0.30 on the local GPU check
- preserve partial-update semantics when a session is stopped and clear provisional text after the final result
- record the model actually used by the last session in exported TXT metadata even after recognition has stopped
- report preview latency separately in the offline ASR lab and exclude provisional decoder calls from final raw-text scoring

These latency and accuracy measurements use a small single-book development sample and describe the tested machine, not a universal performance guarantee.

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
