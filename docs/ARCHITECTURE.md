# Architecture

```text
Browser UI (Next.js / React)
       |
       | same-origin /api/* requests
       v
Next.js API proxy (endpoint allowlist, origin check, secret kept server-side)
       |
       | 127.0.0.1:8765 + random bridge token
       v
FastAPI local bridge
       |-- voice profile import -> FFmpeg extraction -> local profile reference
       |-- generation job queue (one worker)
       |-- health checks / history / audio download
       |-- saved narration projects (create, update, list, delete)
       v
ArkByte Python service layer
       |-- Chatterbox Multilingual V3 (optional local AI dependency)
       |-- CUDA -> CPU fallback when supported by the engine
       |-- SQLite profiles / history / projects
       v
%LOCALAPPDATA%\ArkByte Voice Studio
       |-- profiles/ imports/ outputs/ cache/ logs/
       |-- arkbyte_voice_studio.db
```

The web edition owns an isolated Python virtual environment in the repository's `.venv` directory. It does not install packages into the desktop application's environment. Both can use the same configured ArkByte data root, so the desktop and web frontends can access existing profiles and outputs when they point to the same database.

The UI never receives the bridge token or host filesystem paths. The Next proxy forwards a fixed set of local endpoints only. The Python service binds to loopback only and validates the caller token. Audio references and output files remain inside the configured data root.

Generation is single-worker because local voice models can consume substantial GPU RAM. The job status map is process-local; generated results are persisted in the history database. If the service restarts mid-generation, the UI should show a connection error and the user can inspect Generation History for completed outputs. Saved projects are persisted in SQLite and survive browser restarts and service restarts.


## Project list performance

The project-list endpoint returns compact summaries (title, short script preview, word and character counts, voice reference, language and timestamps). The UI fetches the full script and generation settings from the project-detail endpoint only when the creator opens a project. This avoids repeatedly transferring full narration text during periodic dashboard refreshes.
