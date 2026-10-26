# Changelog

All notable changes to ArkByte Voice Studio Web are documented here.

## [1.2.0-HF2] - 2026-10-26

### Added
- Individual generation-history deletion and a bulk Clear history action. Both remove the history row and its generated audio file while preserving voice profiles, original recordings, saved projects and model caches.
- Server-side output-path containment checks for deletion; malformed entries outside the ArkByte outputs directory are rejected without deleting the referenced file.
- Required responsible-use acknowledgement on every generation request, in addition to the existing consent gate on voice-profile creation and enrolment.
- Responsible voice-use policy covering consent, impersonation, fraud, harassment, identity-verification bypass, non-consensual intimate content and synthetic-voice disclosure.

### Security notes
- Deletion is normal filesystem deletion, not forensic erasure. Backups and exported copies may remain.
- Local consent and policy acknowledgements are deterrence controls; they cannot independently verify a speaker's identity or guarantee that illegal use is impossible.

### Validation
- Backend suite: 58 tests passed, including individual and bulk deletion, path containment, preservation of profiles/projects, active-generation protection, and generation permission gates.
- Full Windows frontend typecheck/build and live Windows acceptance still require running the supplied runner on the target machine.

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


## 1.2.0 maintenance patch - model registry, UI and launcher

- Added an optional VoxCPM 0.5B transcript-conditioned adapter and aligned the model IDs across API, service and UI.
- Kept VoxCPM 2 visible but marked its approximately 8 GB VRAM requirement; it is not a good fit for 6 GB GPUs.
- Added single-model-at-a-time release hooks before model switching.
- Added English/Chinese validation and exact reviewed-transcript checks for VoxCPM 0.5B.
- Fixed progress-message encoding, textarea styling and the repeated Workspace label; added an About ArkByte page.
- Added a guarded optional VoxCPM installer, one-click check/build/launch runner, and PID ownership validation in the Stop script.

## HF3 – Custom Voice Lab (2026-10-26)

- Added a dedicated Custom Voice Lab page to select an existing voice profile, inspect enrolled recordings and transcript-review status, and export a Qwen3-TTS single-speaker fine-tuning dataset.
- Added a clear readiness gate: export remains disabled until every sample has a non-empty transcript explicitly reviewed and saved by the user.
- Added in-app guidance for dataset preparation, separate-environment fine-tuning, held-out evaluation, biometric-data privacy and GPU-memory limitations.
- Reuses the existing authenticated local Qwen3 dataset export endpoint; no model training is represented as complete or run automatically by this patch.


## HF4 maintenance hotfix — typed voice-profile deletion and sidebar layout

- Voice-profile deletion now requires the exact `DELETE VOICE` phrase in the UI and is independently checked by the local API.
- Deletion is blocked while a generation is queued or running; the generation queue revalidates a profile under the same lock to prevent a deletion/start race.
- Profile deletion verifies all recorded reference paths stay inside that profile's managed directory, quarantines the directory, deletes the profile and dependent biometric records, then purges the quarantined audio. A failed final purge is retried at the next service start.
- Generated narrations, saved projects, model files and caches remain outside the deletion scope. Previously exported/copied files cannot be removed by ArkByte.
- Sidebar navigation now scrolls within its own region, and the privacy/footer area remains fixed and visible in short desktop windows.

## Runner reliability hotfix — 2026-10-26

- Reworked Stop to discover live listeners on ports 8765 and 3000 and verify each listener's executable, command line, loopback bind and exact project path before stopping it; stale PID/ownership records no longer prevent a safe stop.
- Added a second identity check immediately before termination to guard against PID reuse, typed `STOP ARKBYTE` confirmation, and a post-stop listener verification window.
- Startup now records the actual listening Python and Next.js process IDs rather than the transient `cmd.exe` launcher PID.
- Start is idempotent: a healthy existing ArkByte instance is reported as already running and no duplicate process is launched.
- The one-click runner now treats a healthy existing instance as success instead of reporting a port conflict; unrelated or partial listeners remain untouched and produce actionable diagnostics.
- Updated CMD wrappers to pass arguments, use a per-process execution-policy bypass, and report nonzero exit status accurately.
- Added a PowerShell parser and structural verification script that does not start or stop any application process.
