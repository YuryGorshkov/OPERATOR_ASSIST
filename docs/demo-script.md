# Demo Script

This script is meant for a short technical walkthrough of `OPERATOR_ASSIST` in an interview, portfolio review, or live product demo.

## What To Open In Advance

Before the demo starts, prepare:

1. the repository page,
2. the latest GitHub Release page,
3. the desktop app with a working local Vosk model,
4. one short real or synthetic audio scenario for testing.

## Five-Minute Walkthrough

### 1. Position the project in one sentence

Start with:

`OPERATOR_ASSIST is a Windows-first dual-stream transcription tool that separates the operator microphone from caller or system audio, adds local Russian speech recognition, and prepares the result for immediate operational use.`

### 2. Show the repository surface

Point out:

- public repo with packaging and release automation,
- CI status,
- tagged release artifacts,
- architecture and deployment docs.

This quickly frames the project as more than a raw script.

### 3. Show the startup-readiness block

In the app, explain:

- model detection,
- microphone selection,
- caller/system-audio selection,
- saved settings awareness.

This is a strong product-quality moment because it shows that the app guides first launch instead of failing silently.

### 4. Show the audio diagnostics block

Point out:

- separate source summaries for both channels,
- live level meters,
- explicit hints when one side has no signal,
- overlap warning when channels appear to capture the same speech.

This is the best moment to explain the hard part of the project: Windows audio routing is inconsistent across machines, so the product has to help the operator debug routing, not just transcribe.

### 5. Run one short transcription test

Use one controlled example:

- say a short phrase into the microphone,
- play or route one short phrase into the caller/system-audio channel,
- show that the panes update independently,
- copy or save the output.

If the Chrome bridge is shown, present it as optional workflow automation, not the core product promise.

## What To Emphasize

For a senior-level presentation, emphasize:

- real Windows audio engineering instead of a toy CRUD problem,
- practical productization: readiness checks, logs, packaging, releases,
- controlled scope: stable workflow separated from experiments,
- honest trade-offs: local models stay external, unsigned Windows binaries still warn on some machines.

## What Not To Oversell

Avoid presenting the project as:

- perfect AI,
- production-grade diarization,
- cloud-scale speech platform,
- final enterprise support stack.

The strongest positioning is:

- desktop workflow engineering,
- Windows capture and routing problem-solving,
- iterative hardening from prototype toward product.
