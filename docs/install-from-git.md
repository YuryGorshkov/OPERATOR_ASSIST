# Install From Git Repository

This guide is for installing `OPERATOR_ASSIST` directly from the public GitHub repository source code instead of using a packaged release.

## What You Need

Before you start:

- Windows 10 or Windows 11
- Git installed
- Python `3.10.x` or newer
- one supported Russian Vosk model prepared separately

## Clone The Repository

Open PowerShell or Windows Terminal and run:

```powershell
git clone https://github.com/YuryGorshkov/OPERATOR_ASSIST.git
cd OPERATOR_ASSIST
```

## Run The Source Setup Script

The repository now includes a bootstrap script that prepares a local virtual environment, installs dependencies, creates runtime folders, and runs a preflight check:

```text
Setup-From-Git.cmd
```

Equivalent PowerShell command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Setup-From-Git.ps1
```

By default this setup:

1. locates a usable Python interpreter,
2. creates `.venv` inside the repository,
3. installs `requirements.txt`,
4. ensures `models/`, `logs/`, and `transcripts/` exist,
5. runs `scripts/Check-Environment.ps1`.

The default dependency set now also includes the optional high-accuracy speaker path based on `faster-whisper`.
That means a clean source install is enough to expose the precise mode in the UI; the first precise launch may still
download the Whisper model itself into `models/whisper-cache`.

## Add A Speech Model

The app still expects a local Russian Vosk model in one of these folders:

- `models/vosk-model-ru-0.42`
- `models/vosk-model-ru-0.22`
- `models/vosk-model-small-ru-0.22`

The archive must be extracted as a normal folder, not left as a zip file.

## Start The App

After setup completes:

```text
Run-Operator-Assist.cmd
```

The launcher now prefers the project-local `.venv` automatically if it exists, so the source installation stays self-contained.

If you choose the precise speaker mode, expect the first model load to be noticeably slower than the normal Vosk path.

## If You Want To Re-Check The Environment

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Check-Environment.ps1
```

## Useful Optional Flags

The source setup script also supports a few optional switches:

- `-NoVenv` if you intentionally want to use the current Python environment
- `-SkipPackageInstall` if dependencies are already installed
- `-SkipEnvironmentCheck` if you only want the bootstrap step

Example:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Setup-From-Git.ps1 -SkipEnvironmentCheck
```
