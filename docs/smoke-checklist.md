# Smoke Checklist For Another PC

Use this checklist when testing a packaged release on a different Windows machine.

## Before Launch

- Download the latest release asset.
- Confirm one supported Vosk model is already available.
- Confirm the target machine has a microphone.
- Confirm the machine exposes either `WASAPI loopback` or a usable fallback like `Stereo Mix`.

## Install Or Extract

- Run `OPERATOR_ASSIST-Setup-<version>.exe` or extract `OPERATOR_ASSIST-portable-<version>.zip`.
- Open the installed or extracted app folder.
- Check that `models/`, `logs/`, and `transcripts/` exist or can be created.

## First Start

- Launch `OPERATOR_ASSIST`.
- Confirm the app opens without a crash.
- Confirm the readiness block is visible.
- If no model is detected, place the model in `models/` and click `Проверить снова`.

## Device Selection

- Confirm the operator microphone appears in the left device selector.
- Confirm the caller or system-audio source appears in the right selector.
- Confirm the audio diagnostics block shows readable source summaries.

## Live Signal Check

- Press `Старт`.
- Speak one short phrase into the operator microphone.
- Confirm the left level meter moves and the left transcript updates.
- Feed one short phrase into the caller/system-audio path.
- Confirm the right level meter moves and the right transcript updates.

## Negative Checks

- Temporarily mute the microphone and confirm the diagnostics hint becomes more explicit.
- Temporarily select a wrong caller source and confirm the right side stays empty with a useful hint.
- If both panes capture the same phrase, confirm the overlap warning appears.

## Output Checks

- Use `Копировать собеседника`.
- Use `Копировать всё`.
- Save one transcript as TXT.
- Open the logs folder.

## Pass Criteria

Treat the smoke test as successful when:

- the app launches,
- the model loads,
- both channels can be selected,
- both channels show independent signal during a short test,
- transcript export and log access work,
- diagnostics remain understandable when routing is wrong.
