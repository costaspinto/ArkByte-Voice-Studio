# Interview guide — ArkByte Voice Studio

This guide helps explain the engineering decisions behind the project. Keep demonstrations to synthetic or authorized voice samples; do not use another person's voice without permission.

## 90-second project introduction

ArkByte Voice Studio is a local-first narration workspace for creators. A user imports a recording they own or are authorized to use, creates a reusable voice reference, saves scripts as projects, and generates narration through a local Chatterbox model. The interface is a Next.js/React application. A server-side Next.js API proxy forwards same-origin browser requests to a loopback-only FastAPI service using a private random bridge token. Python owns file handling, voice inference, SQLite persistence and FFmpeg operations. The product deliberately avoids paid APIs and hosted inference.

## 5-minute demo path

1. Open Overview and explain the health indicators. Distinguish service readiness from AI model readiness.
2. Open Voice Library and import a short recording with explicit permission. Explain the consent confirmation and local file-processing flow.
3. Open Script Studio, select a profile, enter a short script and adjust the model-dependent settings.
4. Save the narration as a Project. Navigate away, reopen Projects, and restore the same script/settings.
5. Generate a short sample. Show queue status, local WAV history and download.
6. Open Settings & Health and explain CPU/CUDA readiness and FFmpeg/database status.

## Architecture and trust boundaries

```text
Browser
  -> Next.js UI (:3000, loopback)
  -> same-origin API route (allowlist + origin check)
  -> FastAPI bridge (:8765, loopback + random token)
  -> service layer
       -> media extraction (FFmpeg/FFprobe)
       -> Chatterbox model (local inference)
       -> SQLite (profiles, history, projects)
       -> local file storage
```

The bridge token is stored in `web/.env.local` and read by the Next.js server. It is not prefixed with `NEXT_PUBLIC_` and is not sent to the browser. The FastAPI process binds to loopback and checks the token with constant-time comparison. File IDs are validated and output paths are constrained to the local data root.

## Important design decisions

### Why a local FastAPI service?

Voice inference and audio-file processing belong in Python, close to PyTorch, Chatterbox and FFmpeg. Keeping that service independent allows the desktop and web interfaces to call the same processing layer without duplicating model code.

### Why a Next.js API proxy?

The browser should not know the bridge token. Same-origin route handlers provide a narrow allowlisted proxy and keep the secret in the server process. The proxy is not a general-purpose open proxy.

### Why SQLite?

This is a single-user local product. SQLite avoids a required database server, works offline and is adequate for profiles, generation history and saved projects. WAL mode, busy timeout and parameterized SQL improve concurrent read behavior and query safety.

### Why serialize generation?

Neural TTS models can occupy several gigabytes of VRAM/RAM. A single generation worker avoids concurrent model runs competing for resources. This trades throughput for predictable resource use on creator PCs.

### Why CPU fallback?

CUDA is preferred when available, but driver/model errors should not always make the app unusable. The engine may retry on CPU when a GPU attempt fails. CPU generation is slower and is not guaranteed to work on every device; the UI reports the effective device.

### Why keep jobs process-local?

The first local release uses an in-process job registry to keep deployment simple. Completed outputs and history are persisted; an in-progress job can be lost if the service restarts. Durable job recovery is a documented future improvement, not something this release claims to solve.

## Trade-offs and limitations to state honestly

- The security model is for a single-user local machine, not public multi-tenant hosting.
- No account registration, cloud synchronization, or remote collaboration is included.
- Project saving is explicit; automatic versioned autosave is a roadmap item.
- A full multitrack DAW, diarization, music separation and subtitle generation are not in this release.
- AI inference depends on downloaded model weights, supported hardware and third-party package/model licenses.
- The source kit does not include a generated `package-lock.json`; generate and commit it after `npm install` before a production release.

## Questions an interviewer may ask

**How do you protect the local bridge?**

Loopback binding, a random bridge secret kept in the Next.js server environment, constant-time token comparison, same-origin checks for browser mutations, a strict proxy endpoint allowlist and server-side path validation.

**What happens when the GPU runs out of memory?**

The model layer attempts cleanup and can retry on CPU for supported failures. This increases latency; if CPU also fails, the request returns a normalized error and diagnostic log rather than pretending a successful result was created.

**How are long scripts handled?**

Text is validated and split into bounded chunks. The engine generates each chunk and joins the samples with a short silence before atomically writing the WAV.

**How do projects survive restarts?**

Project metadata and scripts are stored in SQLite with upsert semantics. Browser state is not the source of truth. The profile foreign key uses `ON DELETE SET NULL`, so deleting a profile does not delete the user's project.

**What would you improve next?**

Durable generation jobs, sentence-level regeneration/segment stitching, project version history/autosave, a real waveform editor, more model adapters, model integrity manifests and expanded Windows hardware testing.
