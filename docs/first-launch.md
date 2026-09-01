# First Launch Guide

This guide describes the intended first-run flow for the current desktop build.

## What The App Checks On Startup

When the desktop app opens, it now validates four things before the operator starts a session:

- whether a supported Vosk model is present,
- whether every source required by the selected capture mode is selected,
- whether local settings have already been saved.

The goal is to keep startup informative without forcing the user through modal errors immediately.

## Supported Model Folder Names

The runtime currently looks for one of these local folders:

- source checkout: under `models/`
- packaged install: under `data/models/`

- `vosk-model-ru-0.42`
- `vosk-model-ru-0.22`
- `vosk-model-small-ru-0.22`

The model archive must be extracted, not left as a `.zip`.

## First-Run Operator Flow

1. Launch `Run-Operator-Assist.cmd` or start `python operator_assist.py`.
2. If no model is available, use the `Папка models` button and place a supported Russian Vosk model there.
3. Click `Проверить снова`.
4. Choose `Оба канала`, `Только собеседник`, or `Только оператор`.
5. Confirm the enabled microphone channel points to the operator headset microphone.
6. Confirm the enabled caller channel points to `WASAPI loopback` or a suitable fallback such as `Stereo Mix`.
7. If the correct caller route is unclear, play test audio and click `Найти звук`.
8. Choose `Стабильный (Vosk)` for the fastest start or `Точный (Whisper)` for maximum caller accuracy.
9. Wait until the readiness block reports that the app is ready, then press `Старт`.

## Why This Flow Exists

Speech models are intentionally kept outside git and outside the default repository payload because they are large runtime assets. The first-launch block is there to make that trade-off understandable to the user instead of failing with unclear startup behavior.

## Troubleshooting

- If the model is present but still not detected, check the final extracted folder name.
- If both transcript panes capture the same phrases, use `Только собеседник` for playback tests or review whether loud headphones are spilling into the microphone.
- If the caller channel is empty, prefer `WASAPI loopback` when available; otherwise use a fallback capture source provided by the machine.
- If packaging worked but recognition does not start, open the logs folder from the app and inspect the latest runtime log.
