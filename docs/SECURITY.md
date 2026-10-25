# Security notes

- Local-only target: loopback host and client checks in the Python bridge; the launcher binds `127.0.0.1`.
- Random bridge token: a 32-byte cryptographic random value is created on install and kept in `web/.env.local`. Never commit or distribute this file.
- Browser boundary: Next.js API routes validate mutating request origins, expose an explicit route allowlist and do not return the bridge token.
- Path safety: profile IDs are validated; generated media paths are constrained to the ArkByte outputs directory; upload names are not used as destination paths.
- Upload safety: allowlisted file extensions, random destination names, non-empty and maximum-size checks, streamed disk writes, FFmpeg timeouts in the reused extraction function.
- Storage: SQLite uses parameterized SQL, WAL and a busy timeout. No arbitrary SQL endpoint is provided.
- Runtime: the web edition uses its own isolated Python virtual environment; one generation worker avoids simultaneous model inference and memory spikes. Existing engine handles supported GPU-to-CPU retry.
- Creator data: project scripts and voice profiles remain under the local ArkByte data root; no remote sync or telemetry is required.
- Scope: a local single-user utility. Do not expose service ports to the internet or LAN. A multi-user web SaaS needs a separate authentication, tenancy, storage, authorization and job-security design.
