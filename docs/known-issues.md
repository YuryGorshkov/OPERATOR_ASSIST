# Known Issues

This document lists the current limitations that are important to mention during review, demo, or handoff.

## Audio And Recognition

- Offline Russian recognition quality still depends on source quality and routing; Vosk favors low latency, while Whisper offers a larger `large-v3` quality profile and a smaller `large-v3-turbo` profile.
- Loading multi-gigabyte Whisper weights from an HDD remains slower than loading from an SSD; the turbo profile reduces but cannot eliminate this storage limit.
- Whisper preview text is intentionally provisional and may change when the higher-accuracy final pass completes after a pause.
- Domain vocabulary is improved mainly through deterministic post-processing, not through model fine-tuning.
- Acoustic cross-talk can still happen when loud headphones physically spill into a nearby microphone; delayed duplicate filtering reduces repeated text but cannot reconstruct perfectly separated audio.
- Real-world audio regression tests with saved fixtures are not yet part of the automated suite.

## Platform Scope

- The primary desktop workflow is Windows-first.
- WASAPI loopback behavior varies between machines and drivers.
- Some machines expose clean loopback sources; others require fallback sources such as Stereo Mix.

## Packaging And Distribution

- The app now has portable and installer outputs, but the release is still not code-signed.
- Speech models are not bundled with the repository and must still be provided locally.
- First launch is therefore clearer than before, but not yet fully zero-setup.

## Experimental Surfaces

- The Chrome bridge should still be treated as an optional experiment rather than the main product promise.
- Browser prototypes are useful for demos, but they are less deterministic than the offline desktop runtime.

## Why This File Exists

Keeping limitations explicit is part of the engineering story. It helps reviewers understand what is intentionally solved, what is partially solved, and what is still an honest next step rather than hidden debt.
