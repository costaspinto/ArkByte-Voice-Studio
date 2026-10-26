# Security Policy

## Supported versions

Security fixes are developed against the latest release on the default branch. Older ZIP copies should be updated before reporting a vulnerability.

## Reporting a vulnerability

Please do not publish exploitable details in a public issue. Open a private GitHub Security Advisory for this repository, or contact the repository maintainer through the private contact method listed on the GitHub profile.

Include the affected version, reproduction steps, expected impact and any proof-of-concept that does not expose real voice recordings or personal data.

## Local security boundary

ArkByte Voice Studio Web is intended for a single-user local workstation. The supplied launch scripts bind to loopback and the FastAPI bridge requires a random local token. Do not forward ports 3000 or 8765, bind to `0.0.0.0`, or expose the app through a public reverse proxy.

Before sharing diagnostics, review them for usernames, filesystem paths, filenames and voice/project metadata. Never attach `.env.local`, SQLite databases, voice references, model caches or generated audio to public issues.

## Voice consent

Only create or use a voice profile when you own the voice or have explicit permission from the speaker. Do not use the application to impersonate a person, mislead an audience, commit fraud, harass anyone, create non-consensual intimate content or bypass identity/biometric verification. Disclose synthetic speech where a listener could mistake it for a genuine recording.

Profile creation and each generation require separate permission/responsible-use acknowledgements. These are deterrence controls, not identity verification and not a guarantee against misuse. See `docs/SAFE-USE-POLICY.md` for the complete policy.
