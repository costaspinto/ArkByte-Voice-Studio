# Suggested GitHub repository settings

**Repository name:** `ArkByte-Voice-Studio`
**Description:** Local-first AI narration workspace with voice profiles, persistent scripts/projects and Chatterbox-powered speech generation. No paid inference API required.
**Visibility:** Private.
**Suggested topics:** `nextjs`, `react`, `typescript`, `fastapi`, `python`, `voice-cloning`, `text-to-speech`, `chatterbox`, `local-ai`, `ffmpeg`, `sqlite`, `creator-tools`.

Recommended repository settings:

- Enable Issues and Pull Requests.
- Keep GitHub Actions limited to repository contents read permission by default.
- Enable Dependabot security and version updates.
- Protect `main` with required CI checks after the first successful workflow run.
- Do not add API secrets: the local app generates its own bridge token on each installation.
- Do not commit voice samples, generated narrations, local SQLite databases, `.env.local`, PFX/P12 keys, model weights, Python virtual environments or diagnostic logs.
- Add a release tag only after the release checklist in `docs/RELEASE_CHECKLIST.md` passes on a clean Windows test machine.
