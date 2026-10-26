# ArkByte Voice Studio project structure

The project root intentionally retains the Windows entry-point scripts and runtime probes because installers, CMD wrappers and diagnostics resolve them relative to the root. Do not move or rename those files without updating their callers.

- `service/` — FastAPI backend, voice engines, storage and backend tests.
- `web/` — Next.js frontend, components, API proxy and npm lockfile.
- `docs/` — architecture, setup, security, model, maintenance, release and validation documentation.
- `.github/` — repository automation and contribution templates.
- `.local-backups/` — local-only copies created by patch installers and this organizer; not source-controlled.
- `logs/` and `run/` — local diagnostics and runtime ownership state; not source-controlled.

Keep `.venv*`, `python-runtime.txt`, `web/.env.local`, `web/node_modules`, `web/.next`, and `%LOCALAPPDATA%\ArkByte Voice Studio` in place. They are installation/runtime state, not clutter.