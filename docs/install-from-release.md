# Install From Packaged Release

This guide is for reviewers or operators who want to try `OPERATOR_ASSIST` on a Windows machine without setting up the source repository first.

## What To Download

Open the repository Releases page and choose one of these assets:

- `OPERATOR_ASSIST-Setup-<version>.exe` for a normal installer flow,
- `OPERATOR_ASSIST-portable-<version>.zip` for a portable unpack-and-run flow.

Both assets are built from the same release pipeline. The installer is more convenient for a normal desktop setup, while the portable archive is useful for demos, test machines, or USB-style handoff.

## Installer Flow

1. Run `OPERATOR_ASSIST-Setup-<version>.exe`.
2. Complete the Inno Setup wizard.
3. Launch `OPERATOR_ASSIST` from the Start menu or desktop shortcut if you enabled it.

## Portable Flow

1. Extract `OPERATOR_ASSIST-portable-<version>.zip` into a writable folder.
2. Open the extracted `OPERATOR_ASSIST` directory.
3. Start `OPERATOR_ASSIST.exe`.

## Packaged Folder Layout

The packaged app keeps user-editable and writable files out of the top-level application root:

- `data/models/` for the Vosk model,
- `data/logs/` for runtime logs,
- `data/transcripts/` for exported transcripts,
- `config/technical_terms.json` for editable term replacements,
- `config/chatgpt_prompt_template.txt` for the AI handoff template,
- `support/` for helper materials and bridge scripts.

## Required Model Step

The packaged app still expects an external Russian Vosk model. Before first successful recognition:

1. open the local `data/models/` folder,
2. extract one supported model there,
3. confirm one of these folder names exists:
   - `vosk-model-ru-0.42`
   - `vosk-model-ru-0.22`
   - `vosk-model-small-ru-0.22`

The model must be extracted as a folder, not left inside a zip archive.

## First Launch Checklist

On first start, the app should guide the operator through readiness checks:

- model detected,
- microphone selected,
- caller or system-audio source selected,
- settings path available.

Use the readiness actions to open the models folder, re-check the environment, and confirm the final routing before pressing `Старт`.

## If Windows Shows A Trust Warning

The release pipeline is automated, but the current Windows binaries are not code-signed yet. On some machines that means SmartScreen or similar trust warnings may still appear. That is expected for the current stage of the project and does not indicate a packaging failure by itself.

## Recommended Demo Preparation

For a clean demo on another computer:

1. prepare the release asset in advance,
2. prepare one supported Vosk model in advance,
3. verify that the machine exposes either WASAPI loopback or a usable fallback source,
4. run one short audio test before the actual presentation.
