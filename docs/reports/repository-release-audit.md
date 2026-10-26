# Repository release audit — ArkByte Voice Studio 1.2.0

**Audit date:** 26 October 2026
**Scope:** Clean GitHub portfolio snapshot, documentation, demo media and publication safeguards.

## Source and documentation checks

| Check | Result |
|---|---|
| README / documentation relative links | 36 checked; 0 broken |
| SVG assets | 5 parsed as valid XML |
| Animated README preview | 50 frames, 960 × 438 |
| Curated walkthrough | 27.46 seconds, 1280 × 584, H.264 video-only, no audio stream |
| Screenshot gallery | 8 application captures included |
| Historical patch-install notes | Excluded from the public portfolio snapshot; release history remains in the changelog |

## Security and publication checks

| Check | Result |
|---|---|
| Text-source secret scan | 108 text files scanned; 0 secret-like matches after allowing the runtime-generated `arkbyte-test-only-` test token pattern |
| Private runtime / model / recording scan | 0 blocked files found |
| `.gitignore` | Excludes local environments, bridge configuration, app data, user voice media, database files, model weights and build output |
| Public demo media | Only the curated muted walkthrough is allowlisted; the original uploaded screen recording is not included |
| Git publication helper | Requires typed confirmation, checks authenticated owner and target non-existence, refuses pre-existing history/remotes, and never force-pushes |

## Backend checks

- `python -m compileall -q service` passed.
- Backend and API regression suite: **61/61 passed** in the packaging environment, with no temporary-log cleanup traceback.

## Frontend and Windows checks

The project owner supplied a Windows acceptance record for Python 3.12.10, PyTorch 2.6.0+cu126, CUDA and an RTX 3050 Laptop GPU (6 GB): backend tests, TypeScript typecheck, Next.js 16.4.3 production build, production startup, Stop and duplicate-start checks passed.

A separate `npm ci` attempt in the packaging container timed out before dependencies were installed, so the frontend build was not independently rerun in this container. The owner-run Windows production build succeeded; GitHub Actions will provide a clean CI run after publication.

The owner previously observed a Windows `WinError 32` after tests passed, while Python attempted to remove a temporary `application.log` held open. The test module in this snapshot explicitly closes the FastAPI test client, generation executor and application logger handlers before temporary-directory cleanup. It passed in the packaging environment without the traceback; rerun on Windows to confirm the platform-specific lock is resolved.

## Not claimed as validated

- Live VoxCPM checkpoint downloads/inference on every target GPU.
- Qwen3-TTS fine-tuning, custom checkpoint import or in-app inference. Custom Voice Lab exports a reviewed training dataset only.
- 100% speaker similarity or identity verification.
- Public multi-user deployment. The application is single-user and loopback-only.
- A GitHub Actions result for this new repository; CI runs after the first push.
