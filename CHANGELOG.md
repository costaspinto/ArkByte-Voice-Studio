# Changelog

All notable changes to ArkByte Voice Studio Web are documented here.

## [1.2.0-HF1] - 2026-10-26

### Fixed
- Removed quoted inline `python -c` checks from the Windows installer and diagnostics. Windows PowerShell 5.1 could strip embedded quotes and turn output labels such as `PyTorch` into undefined Python names, causing a false `NameError`.
- Added file-based Python runtime, AI engine and backend preflight checks.
- AI preflight imports the exact `ChatterboxMultilingualTTS` class used by the ArkByte engine, exercises a CPU tensor operation, and treats CUDA availability as informational so CPU-only installs remain supported.
- Recovery now runs a temporary Python probe file instead of native `python -c` source.

## [1.2.0] - 2026-10-25

### Added
- Voice Lab multi-recording enrolment (up to ten original recordings per profile), add-samples workflow and manual reference-anchor selection.
- Non-destructive audio handling: original media is retained; model-ready mono 24 kHz references are created separately without noise reduction or loudness normalization.
- FFmpeg-based sample diagnostics for duration, sample rate/channels, RMS/peak, clipping, silence/activity, pitch estimates, spectral centroid and heuristic quality warnings.
- Editable per-recording transcripts, optional lazy Faster-Whisper local draft transcription, explicit transcript-reviewed state and a personal pronunciation dictionary. Qwen export rejects unreviewed transcripts.
- Transparent voice-intelligence pipeline status for consent, audio quality, transcript coverage, optional identity, accent notes, prosody and reference selection.
- Benchmark Studio with A/B reference/output playback and acoustic proxy comparisons.
- Optional lazy SpeechBrain ECAPA-TDNN speaker-embedding comparison with local model cache.
- Optional lazy VoxCPM 2 reference-conditioned generation adapter.
- Qwen3-TTS single-speaker training-data ZIP export with full audio, shared reference, transcript validation, JSONL manifest and workflow instructions.
- Punctuation-aware chunk stitching pauses.
- 19 additional backend tests for the new voice workflow, adapters, export, transcription and API routes.

### Changed
- Versioned web application and local API as 1.2.0.
- Project records now persist the selected generation model while migrating existing SQLite projects safely.
- Updated Voice Lab, Benchmark Studio, model registry, API route allowlist, release docs and manual acceptance plan.

### Explicit limitations
- Accent is not automatically classified; accent notes are speaker-confirmed.
- Faster-Whisper is an optional local ASR draft adapter; every transcript requires manual review. Phoneme alignment is not included.
- ECAPA and VoxCPM 2 require optional dependencies and model weights; no model downloads occur during normal startup.
- Qwen dataset export is included; Qwen fine-tuning and in-app inference are not included.
- No claim of 100% voice similarity or guaranteed accent reproduction is made.

## [1.1.2] - 2026-10-25
- Fixed Windows Python discovery for custom Python.org and WinGet installation paths.
- Added `-PythonPath` for explicit selection of an installed Python 3.12/3.13 x64 interpreter.
- Added `py -0p`, command PATH and Python registry discovery, with validation to reject Store aliases and 32-bit runtimes.
- Re-scans Python after WinGet installation and PATH refresh.

## [1.1.1] - 2026-10-25

### Added
- Persistent Projects workspace backed by SQLite.
- Project API with create, update, list and delete operations.
- Script, voice profile, language, output filename and generation settings persistence.
- Foreign-key behavior that preserves projects when a referenced voice profile is deleted.
- Next.js route-level error, loading and not-found states.
- GitHub Actions CI, contribution guidance and security reporting policy.
- Dedicated web-only Python environment; web dependencies no longer modify the desktop environment.
- Windows prerequisite bootstrap for Node.js, Python and FFmpeg/FFprobe.
- Optional, separate Chatterbox AI dependency install step.

### Changed
- Improved local API error normalization and project UI states.
- Project lists now return compact summaries; full scripts are fetched on demand when a project is opened.
- Updated docs, release notes and validation status.

## [1.0.0] - Initial web edition

- Initial local-first Next.js interface and FastAPI bridge.
- Voice profile import, script generation, local history and system health.
