# Local production build

This is a self-hosted local web workspace, not a cloud SaaS deployment.

1. Install dependencies with `INSTALL_WEB_WINDOWS.ps1` on Windows.
2. Use `INSTALL_WEB_WINDOWS.ps1 -InstallAI` to install optional Chatterbox/PyTorch dependencies.
3. Verify the local AI service can import FastAPI and the ArkByte engine modules.
4. Build the frontend using `BUILD ARKBYTE VOICE STUDIO WEB.cmd`.
5. Launch with:

   ```powershell
   .\START ARKBYTE VOICE STUDIO WEB.ps1 -Production
   ```

The production Next.js server still binds to `127.0.0.1` and uses the same token-protected local Python bridge. Keep both ports loopback-only. Do not use a public hosting service for this local AI bridge without redesigning the security model.

## Data and upgrade behavior

- The web application has its own Python virtual environment at `.venv`; it does not modify the desktop app's Python packages.
- By default, desktop and web editions use `%LOCALAPPDATA%\ArkByte Voice Studio` on Windows. This allows their voice profiles, history, outputs and SQLite projects to be shared locally.
- Back up the complete ArkByte data directory before manual database edits or migrations.
- Do not move the extracted repository after installation without rerunning the setup script; the generated `python-runtime.txt` contains the venv path.
- The local bridge token is generated in `web/.env.local`; preserve it across restarts, do not commit it and do not copy it to another computer.
