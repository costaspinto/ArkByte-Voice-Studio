# Quick start — Windows 10/11

## Install

1. Extract the repository ZIP to a writable folder under your user profile.
2. If Windows marks the ZIP as blocked, right-click → **Properties** → **Unblock** (when offered). Do not disable SmartScreen or Defender.
3. Double-click `INSTALL ARKBYTE VOICE STUDIO WEB.cmd`. The installer checks Node.js, Python and FFmpeg, creates the dedicated web Python environment, installs frontend packages and the optional Chatterbox stack, and creates private local bridge credentials.
4. Launch with `RUN ARKBYTE VOICE STUDIO.cmd` for checks/build/start, or `START ARKBYTE VOICE STUDIO WEB.cmd` to launch an already-installed application.
5. Open `http://127.0.0.1:3000`.
6. Stop with `STOP ARKBYTE VOICE STUDIO WEB.cmd`.

The web UI binds to `127.0.0.1:3000`; the Python bridge binds to `127.0.0.1:8765`. Do not expose either service to a LAN or the internet.

## Data and privacy

Voice references, generated audio, history, SQLite metadata and model caches are stored under `%LOCALAPPDATA%\ArkByte Voice Studio` by default. The bridge token is private in `web\.env.local`; never publish that file. Never put voice recordings, model weights, databases or transcript exports in a public repository.

## Optional adapters

Review `service\requirements-voxcpm.txt` and `INSTALL VOXCPM MODELS.ps1` before enabling VoxCPM. The installer performs a dependency dry run and is designed to avoid changing the existing PyTorch/CUDA versions. Checkpoint weights download only on first model use. VoxCPM 0.5B has a tight memory budget on 6 GB GPUs; VoxCPM 2B is not recommended for that hardware.

## Tests and builds

```powershell
$env:PYTHONPATH = "$PWD\service"
python -m compileall -q service
python -m unittest discover -s service\tests -v
Set-Location .\web
npm ci
npm run typecheck
npm run build
```

## Troubleshooting

- Installer and runner logs: `logs\`
- Backend log: `logs\backend.log`
- Next.js log: `logs\nextjs.log`
- Application diagnostics: `%LOCALAPPDATA%\ArkByte Voice Studio\logs\`
- If ports 8765 or 3000 are occupied, use the project Stop command and let its listener-identity checks decide whether a process belongs to ArkByte. Do not kill unverified Python or Node processes.

See [`ARCHITECTURE.md`](ARCHITECTURE.md), [`SECURITY.md`](SECURITY.md), [`SAFE-USE-POLICY.md`](SAFE-USE-POLICY.md), and [`MANUAL_VOICE_TESTING.md`](MANUAL_VOICE_TESTING.md) for additional context.
