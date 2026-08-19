# OPERATOR_ASSIST Deployment Notes

## Supported Environment

Primary target:

- Windows 10 or Windows 11
- Python 3.10
- microphone input available
- either WASAPI loopback support or a fallback source such as Stereo Mix

Secondary target:

- Chromium-based browser for the lightweight browser prototypes

## Python Dependencies

Install from:

```bash
pip install -r requirements.txt
```

The project uses a mixed dependency model:

- environment-installed packages for the core runtime,
- vendored packages under `vendor/` for loopback-related portability.

## Speech Models

Vosk models are not committed to git.

Expected local paths:

- `models/vosk-model-ru-0.42`
- `models/vosk-model-ru-0.22`
- `models/vosk-model-small-ru-0.22`

For a public repository, excluding these models is the correct trade-off:

- the repo stays lightweight,
- the source remains reviewable,
- runtime assets stay local.

## Desktop Launchers

Current launchers include:

- `Run-Operator-Assist.cmd`
- `Run-Operator-Assist.ps1`
- `Run-VoiceNotes.cmd`
- `Run-Speaker-Text.cmd`
- corresponding `.vbs` wrappers

Current status:

The main operator launcher now resolves Python more defensively instead of hardcoding one user-specific path. This is a meaningful improvement for portability, although it is still not the same as a packaged installer.

## Preflight Check

The repository includes a local environment validation script:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\Check-Environment.ps1
```

It verifies:

- presence of a usable Python runtime,
- presence of key source files,
- visible Vosk model directories,
- vendored loopback dependencies,
- critical Python packages for the desktop runtime.

## Browser Prototype Hosting

The repository includes a minimal static file server:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\Serve-App-Tcp.ps1
```

Default local URL:

```text
http://127.0.0.1:8765/
```

This is intentionally small and self-contained. It is good enough for demos and local review, not intended as a production web backend.

## Local-Only Data

The following are intentionally excluded from version control:

- `logs/`
- `transcripts/`
- `models/`
- `operator_assist_settings.json`
- build and packaging output

This protects the repository from being polluted with runtime noise and large artifacts.

## Packaging Workflow

The repository now contains a committed Windows release path:

- PyInstaller spec: `packaging/pyinstaller/operator_assist.spec`
- Inno Setup script: `packaging/inno/OperatorAssist.iss`
- release orchestration: `scripts/Build-Release.ps1`

Install build-time tooling:

```bash
pip install .[build]
```

Build the release:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\Build-Release.ps1
```

By default the script:

1. runs `python -m unittest discover -s tests`,
2. builds a PyInstaller one-folder bundle,
3. assembles `release/portable/OPERATOR_ASSIST`,
4. writes a small `BUILD_INFO.txt`,
5. creates a portable zip archive,
6. tries to build an Inno Setup installer when `ISCC.exe` is available.

Useful switches:

- `-SkipTests`
- `-SkipZip`
- `-SkipInstaller`
- `-NoClean`

## Frozen Runtime Behavior

The runtime now separates:

- the bundle directory used by frozen Python modules,
- the application directory next to the executable where editable and writable files live.

That keeps the packaged app aligned with the existing product behavior:

- `technical_terms.json` stays editable,
- `chatgpt_prompt_template.txt` stays editable,
- `models/` stays external,
- `logs/` and `transcripts/` stay writable next to the executable.

## Recommended Demo Setup

For live demos or technical reviews:

1. prepare one working local Vosk model,
2. verify the microphone source,
3. verify the loopback or Stereo Mix source,
4. keep the IT mode available but describe it as optional domain correction,
5. present the Chrome bridge as an experiment, not as the core promise.

That framing keeps the project honest and technically strong.
