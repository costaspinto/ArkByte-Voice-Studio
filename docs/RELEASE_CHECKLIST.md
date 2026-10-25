# Release checklist

## Source and dependency hygiene
- [ ] Review changes and update `CHANGELOG.md` / release notes.
- [ ] Run `python -m compileall -q service`.
- [ ] Run `PYTHONPATH=service python -m unittest discover -s service/tests -v`.
- [ ] Run `npm install` in `web/` and commit `web/package-lock.json`.
- [ ] Run `npm run typecheck` and `npm run build` in `web/`.
- [ ] Inspect `git status`; ensure no `.env.local`, token, DB, voice sample, generated audio, model weight, private key or log is staged.

## Local functional testing
- [ ] Install from a clean Windows 10/11 x64 user account.
- [ ] Verify the local services bind only to loopback.
- [ ] Verify health status for Python, FFmpeg, SQLite and AI runtime.
- [ ] Import a voice recording for which the operator has permission.
- [ ] Save, close, reopen and delete a project.
- [ ] Generate a short sample with Chatterbox on a supported GPU.
- [ ] Repeat with CPU mode where feasible.
- [ ] Confirm output playback and download.
- [ ] Verify errors, interrupted startup and service restart recovery.

## Distribution
- [ ] Review all third-party package and model licenses.
- [ ] Generate and verify SHA-256 checksums.
- [ ] Test the release ZIP in a clean Windows VM.
- [ ] Never ship `.env.local`, local databases, creator data, model weights or signing private keys.
- [ ] Do not claim public SaaS readiness; current architecture is local single-user only.
