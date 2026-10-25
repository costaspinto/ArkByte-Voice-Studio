# Validation Report — ArkByte Voice Studio Web 1.2.0-HF1

## Checks completed in this build environment

| Check | Result |
|---|---|
| Python source compilation (`PYTHONPATH=service python -m compileall -q service`) | Passed |
| Backend unit and integration tests (`PYTHONPATH=service python -m pytest service/tests -q`) | **46 passed** |
| FFmpeg audio analysis and media integration tests | Passed where FFmpeg is available |
| SQLite profile/sample/transcript/anchor/pronunciation migration and persistence | Passed |
| Transcript review state; unreviewed ASR drafts blocked from Qwen export | Passed |
| Qwen3-TTS dataset ZIP creation, audio conversion, JSONL and manifest checks | Passed |
| Optional ECAPA, VoxCPM 2 and Faster-Whisper lazy adapters | Mocked adapter tests passed; real weights/inference not run |
| Transcript review gate | Unreviewed ASR drafts cannot enter Qwen training export | Passed
| API auth, route validation, model registry and transcript/export endpoints | Passed |
| TypeScript/TSX syntax transpilation | **12 source files, 0 syntax errors** |
| Frontend proxy path allowlist spot checks | Passed for enrolment, transcript, transcription, model registry and Qwen export paths |
| CSS variable reference review for new screens | Fixed new undefined theme variables |
| ZIP contents and checksum | Verified when producing release archive |
| HF1 Python verification scripts (`verify_python_runtime.py`, `verify_ai_engine.py`, `verify_backend_preflight.py`) compile | Passed |
| Windows installer AI/backend preflight no longer uses inline quoted Python `-c` source | Source inspection passed |
| AI preflight target class matches `ChatterboxEngine` (`ChatterboxMultilingualTTS`) | Source inspection passed |
| `verify_python_runtime.py` under Python 3.13.5 x64 | Passed; reports interpreter path, version and architecture |
| `verify_backend_preflight.py` in build environment | Passed; FastAPI, Uvicorn and NumPy imported |
| `verify_ai_engine.py` in build environment | PyTorch 2.10 CPU tensor passed; absence of Chatterbox produced a full, specific `ModuleNotFoundError`; success path also exercised against a test stub matching `ChatterboxMultilingualTTS` |
| PowerShell 5.1 script syntax/runtime | Not executable in this Linux environment; source was statically reviewed, target Windows run remains required |

The test run emits two FastAPI deprecation warnings because the existing shutdown handler uses `@app.on_event("shutdown")`. This does not fail the test suite; a lifespan-handler migration is still desirable.

## Checks not completed in this environment

- Full npm dependency installation did not complete because the npm registry was unreachable from this build environment (`EAI_AGAIN` / DNS timeout). `web/package-lock.json` is included in the release, but semantic TypeScript checking with installed Next/React type packages and `next build` were not run.
- TypeScript syntax transpilation checks parsing only. It does not replace `npm run typecheck` or `npm run build`.
- The Windows PowerShell 5.1 installer, WinGet dependency installation, file-based native invocation and Windows startup scripts were not executed in this Linux build environment; the source was statically reviewed only. The actual Chatterbox package import and model inference must still be validated on the target PC. The HF1 source patch is specifically intended to eliminate the confirmed quote-stripping `NameError`; target-PC confirmation is still required.
- Real Chatterbox model download/inference and CUDA/CPU hardware fallback require testing on the target Windows PC.
- VoxCPM 2, ECAPA-TDNN and Faster-Whisper adapters were tested with mocked model objects or dependency-absence paths. Their real model weights, first-run downloads, GPU compatibility and output quality still require target-machine verification.
- Qwen3-TTS training-data export is implemented; the separate Qwen fine-tuning job and in-app fine-tuned inference are not included in this release.
- No evaluation has yet been run against the user's voice recordings. Accent fidelity, speaker similarity, pronunciation and prosody must be measured in manual testing.

## Required acceptance on Windows

From the extracted repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\INSTALL_WEB_WINDOWS.ps1 -InstallAI
```

Run backend regression tests:

```powershell
$env:PYTHONPATH = "$PWD\service"
.\.venv\Scripts\python.exe -m pytest service\tests -q
```

Install optional local transcription only when needed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r service\requirements-transcription.txt
```

Then verify the frontend from `web/`:

```powershell
cd web
npm ci
npm run typecheck
npm run build
```

Finally start the application, enrol ten recordings of the authorised speaker, use Auto-transcribe where installed, review and save every transcript, select the best reference anchor, generate held-out phrases, and compare outputs in Benchmark Studio. Test Chatterbox first; only add optional models in a separate test environment after recording the baseline.

Do not describe this release as a publicly hosted multi-user SaaS. It remains a single-user, loopback-only local application.
