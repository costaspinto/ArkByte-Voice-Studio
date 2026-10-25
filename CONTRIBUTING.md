# Contributing

Thanks for helping improve ArkByte Voice Studio.

## Development setup

1. Install Python 3.12 or 3.13, Node.js 22 LTS and FFmpeg/FFprobe.
2. Install Python dependencies with `python -m pip install -r service/requirements-dev.txt`.
3. Install AI dependencies only when testing real voice inference: `python -m pip install -r service/requirements-ai.txt`.
4. Install web dependencies from `web/` with `npm install`.
5. Follow `README.md` to set a local bridge token and start the FastAPI and Next.js processes.

## Before opening a pull request

```powershell
$env:PYTHONPATH = "$PWD\service"
python -m unittest discover -s service/tests -v
cd web
npm run typecheck
npm run build
```

Keep pull requests focused. Add regression tests for bug fixes and API/data changes. Do not commit secrets, local databases, voice recordings, model weights, generated audio, `.env.local` or diagnostic logs.

## Design and security rules

- Preserve local-first operation; do not add mandatory paid APIs or cloud services.
- Keep browser code free of the bridge token and filesystem paths.
- Extend the Next.js API allowlist only for explicit, reviewed endpoints.
- Validate untrusted input at the FastAPI boundary.
- Use bound SQL parameters and path containment checks.
- Avoid silent engine/model fallbacks that change voice identity or quality without telling the user.
- Preserve existing creator data during migrations and repairs.
- Document model licensing separately from the MIT-licensed application code.
