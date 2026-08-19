# Changelog

All notable repository-facing changes are documented here.

## Unreleased

Repository and product-polish work prepared after `v1.0.0`.

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
