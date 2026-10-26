<div align="center">

# ARKBYTE VOICE STUDIO

### Your local-first workspace for AI-powered voice generation.

A browser-based voice studio with a Python inference service, modular model adapters, reference-guided voice workflows, and a Windows-friendly local runtime.

<br/>

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Status](https://img.shields.io/badge/STATUS-ACTIVE%20DEVELOPMENT-8B5CF6?style=for-the-badge)](#project-status)

<br/>

**[Product Walkthrough](docs/assets/video/ArkByte-Voice-Studio-Walkthrough.mp4)**
&nbsp; · &nbsp;
**[Architecture](#-architecture)**
&nbsp; · &nbsp;
**[Quickstart](docs/quickstart.md)**
&nbsp; · &nbsp;
**[Documentation](#-documentation)**

</div>

---

## ✦ Project status

> [!IMPORTANT]
> ArkByte Voice Studio is under active development. Model quality, supported hardware, available controls, and inference behavior depend on the selected adapter and local runtime. A successful build or test run does not guarantee identical results across machines.

ArkByte brings a browser-based studio together with a Python inference service and pluggable speech-model integrations. It is designed to keep local inference and user-controlled voice assets close to the machine while providing a structured interface for model selection, generation, and experimentation.

## ✦ At a glance

| Studio experience | Engineering foundation |
|:--|:--|
| Browser-based voice workspace | Next.js 16, React and TypeScript |
| Voice generation and playback | Python inference service |
| Reference-guided voice workflows | Modular model / engine adapters |
| Custom Voice Lab | PyTorch with optional CUDA runtime |
| Windows launch and diagnostics | PowerShell and CMD tooling |

## ✦ Highlights

<table>
<tr>
<td width="50%" valign="top">

### ◈ Browser-based studio
A structured Next.js and TypeScript interface for interacting with the local voice service.

### ◈ Modular model adapters
Model-specific integrations are separated behind adapter and engine boundaries to support experimentation and maintainability.

### ◈ Local inference path
Run through a local Python runtime, including a CUDA-enabled environment when compatible hardware and drivers are available.

</td>
<td width="50%" valign="top">

### ◈ Custom Voice Lab
Explore reference-audio and model-supported voice-conditioning workflows.

### ◈ Windows operations
PowerShell and CMD helpers support launch, shutdown, verification, and model installation workflows.

### ◈ Validation-first development
Backend tests, TypeScript checks, and a production frontend build form part of the verification process.

</td>
</tr>
</table>

## ◈ Product walkthrough

<div align="center">

[![Watch the ArkByte Voice Studio walkthrough](docs/assets/screenshots/00-overview.png)](docs/assets/video/ArkByte-Voice-Studio-Walkthrough.mp4)

**[▶ Watch the full walkthrough](docs/assets/video/ArkByte-Voice-Studio-Walkthrough.mp4)**

</div>

## ◈ Screenshots

The gallery below shows the current application interface and workflows.

<details open>
<summary><strong>Studio overview</strong></summary>
<br/>

<div align="center">

![ArkByte Voice Studio overview](docs/assets/screenshots/00-overview.png)

</div>
</details>

<details open>
<summary><strong>Voice workspace</strong></summary>
<br/>

| Voice Lab | Generation History |
|:--:|:--:|
| ![Voice Lab](docs/assets/screenshots/01-voice-lab.png) | ![Generation History](docs/assets/screenshots/02-generation-history.png) |

| Custom Voice Lab | Script Studio |
|:--:|:--:|
| ![Custom Voice Lab](docs/assets/screenshots/03-custom-voice-lab.png) | ![Script Studio](docs/assets/screenshots/04-script-studio.png) |
</details>

<details>
<summary><strong>Settings and application management</strong></summary>
<br/>

| Settings and Health | About ArkByte |
|:--:|:--:|
| ![Settings and Health](docs/assets/screenshots/05-settings-health.png) | ![About ArkByte](docs/assets/screenshots/06-about-arkbyte.png) |

![Voice profile deletion workflow](docs/assets/screenshots/07-voice-profile-delete.png)
</details>

<details>
<summary><strong>Additional walkthrough captures</strong></summary>
<br/>

| Studio interface | Voice and model selection |
|:--:|:--:|
| ![Studio interface](docs/assets/screenshots/01-studio-overview.jpg) | ![Voice and model selection](docs/assets/screenshots/02-voice-selection.jpg) |

| Speech generation workflow | Custom Voice Lab |
|:--:|:--:|
| ![Speech generation workflow](docs/assets/screenshots/03-generation-workflow.jpg) | ![Custom Voice Lab](docs/assets/screenshots/04-custom-voice-lab.jpg) |

<div align="center">

![Output and playback](docs/assets/screenshots/05-output-and-playback.jpg)

</div>
</details>

---

## ✦ Architecture

ArkByte is organized into four primary layers:

1. **Presentation layer** — Next.js pages and React components render the studio and collect user input.
2. **API boundary** — the Next.js API route proxies supported requests to the local Python service and applies the configured bridge boundary.
3. **Application and orchestration layer** — the Python service validates requests, coordinates voice operations, and selects the appropriate engine or adapter.
4. **Inference and asset layer** — model runtimes perform inference; audio and application data are handled by the relevant service and storage components.

```mermaid
flowchart TB
    U([User]) --> UI[Next.js Studio UI]
    UI --> API[Next.js API Route]
    API -->|Authenticated local bridge| SVC[Python API Service]
    SVC --> VAL[Validation and orchestration]
    VAL --> REG[Model / Engine Adapter]
    REG --> CH[Chatterbox Engine]
    REG --> VX[VoxCPM Engine]
    REG --> OTHER[Other supported adapters]
    CH --> INF[Local model runtime]
    VX --> INF
    OTHER --> INF
    INF --> POST[Audio post-processing]
    POST --> STORE[(Configured output / app storage)]
    STORE --> SVC
    SVC --> API
    API --> UI
    UI --> OUT([Playback / download])
```

### Component responsibilities

| Component | Responsibility |
|:--|:--|
| `web/` | Next.js application, UI components, frontend types, and API proxy route |
| `service/` | Python API, application services, model engines, storage, and backend tests |
| `docs/` | Setup, architecture, model, security, testing, and release documentation |
| `START*` / `RUN*` scripts | Windows startup entry points |
| `STOP*` scripts | Controlled shutdown of verified ArkByte listeners |
| `VERIFY*` scripts | Runtime and launcher diagnostics |
| `INSTALL*` scripts | Optional model/runtime setup helpers |

<sub>The diagram describes the intended request path. Exact adapter availability and optional components depend on the checked-out version and installed model dependencies.</sub>

### System flow

<details>
<summary><strong>1. Startup and readiness</strong></summary>

```mermaid
flowchart TD
    A[Run Windows launcher] --> B[Resolve project root]
    B --> C[Read selected Python runtime]
    C --> D[Validate Python and dependencies]
    D --> E{Runtime valid?}
    E -- No --> X[Print diagnostic and stop]
    E -- Yes --> F[Check local configuration]
    F --> G[Start Python API service]
    G --> H[Wait for backend health]
    H --> I{Backend healthy?}
    I -- No --> Y[Capture logs and report failure]
    I -- Yes --> J[Start Next.js production server]
    J --> K[Wait for frontend port]
    K --> L{Frontend ready?}
    L -- No --> Z[Report frontend startup failure]
    L -- Yes --> M[Open local studio]
    M --> N[Application ready]
```
</details>

<details>
<summary><strong>2. Request-to-audio generation</strong></summary>

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js UI
    participant Proxy as API Proxy
    participant API as Python Service
    participant Engine as Model Adapter
    participant Runtime as Local Model Runtime
    participant Output as Audio Output

    User->>UI: Enter text and generation options
    UI->>Proxy: Submit generation request
    Proxy->>API: Forward through local bridge
    API->>API: Validate payload and options
    API->>Engine: Dispatch to selected adapter
    Engine->>Runtime: Prepare model inputs
    Runtime-->>Engine: Generated audio
    Engine->>Output: Normalize / post-process
    Output-->>API: Audio result and metadata
    API-->>Proxy: Structured response
    Proxy-->>UI: Return result
    UI-->>User: Playback and available actions
```
</details>

<details>
<summary><strong>3. Model selection and adapter dispatch</strong></summary>

```mermaid
flowchart TD
    A[Generation request] --> B[Validate requested model]
    B --> C{Adapter registered?}
    C -- No --> D[Return supported-model error]
    C -- Yes --> E[Load adapter configuration]
    E --> F{Model assets available?}
    F -- No --> G[Return setup guidance]
    F -- Yes --> H[Check runtime compatibility]
    H --> I{Compatible?}
    I -- No --> J[Report hardware / dependency issue]
    I -- Yes --> K[Prepare inference]
    K --> L[Execute selected engine]
    L --> M[Return generated audio]
```
</details>

<details>
<summary><strong>4. Custom voice and reference-audio workflow</strong></summary>

```mermaid
flowchart TD
    A[Open Custom Voice Lab] --> B[Choose supported workflow]
    B --> C[Provide permitted reference audio]
    C --> D[Validate file and request constraints]
    D --> E{Input accepted?}
    E -- No --> F[Show validation feedback]
    E -- Yes --> G[Prepare model-specific conditioning]
    G --> H[Run selected model adapter]
    H --> I[Generate sample output]
    I --> J[Evaluate similarity and quality]
    J --> K{Acceptable result?}
    K -- No --> L[Adjust supported settings or reference]
    L --> G
    K -- Yes --> M[Save or export using configured workflow]
```
</details>

This is a reference-guided workflow, not a claim that the application trains a foundation model from scratch. Model-specific capabilities vary.

## ✦ Voice generation lifecycle

1. Select a supported model and enter text or other supported inputs.
2. The frontend validates required fields and submits the request through the application API.
3. The backend validates the request again; frontend validation is not treated as a security boundary.
4. The orchestration layer dispatches to the selected engine adapter.
5. The adapter prepares model-specific inputs and invokes the installed inference runtime.
6. Generated audio is returned through the service response path.
7. The frontend presents the result for playback and any supported export action.

## ✦ Custom voice workflow

The Custom Voice Lab is intended for controlled experimentation with reference audio and model-supported voice conditioning.

> **Responsible use:** Use only audio you own or have explicit permission to use. A reference sample does not guarantee a perfect or 100% identity match. Results depend on the source recording, model, language, text, settings, and hardware/runtime.

For model-specific instructions, consult the [Custom Voice Lab guide](docs/CUSTOM-VOICE-LAB.md) and [Model Adapters documentation](docs/MODEL_ADAPTERS.md).

## ✦ Technology stack

| Layer | Technologies |
|:--|:--|
| Frontend | Next.js, React, TypeScript |
| Styling and UI | CSS / project UI components |
| Backend | Python, FastAPI-compatible API service |
| Model integration | Model engines and adapter modules |
| ML runtime | PyTorch; optional CUDA runtime where supported |
| Audio | Model-specific audio preprocessing and output handling |
| Local orchestration | PowerShell, CMD, Node.js, npm |
| Quality checks | Python tests, TypeScript compiler, Next.js production build |

---

## ✦ Getting started

### Prerequisites

- Windows 10/11 for the supplied PowerShell/CMD launchers.
- Python 3.12 for the validated local runtime.
- Node.js and npm compatible with the frontend lockfile.
- A supported model runtime and its required model assets.
- NVIDIA driver/CUDA support only if using the CUDA-enabled runtime.
- FFmpeg is optional and used by the documentation helper to extract screenshots from the walkthrough video.

### 1. Configure the Python runtime

The repository may use a dedicated local virtual environment. The selected interpreter is recorded in `python-runtime.txt` when that file is present. Keep machine-specific interpreter paths local; do not publish local absolute paths or virtual environments.

```powershell
Set-Location "C:\Projects\ArkByte Voice Studio Web 1.2.0"
Get-Content .\python-runtime.txt
& (Get-Content .\python-runtime.txt | Select-Object -First 1) --version
```

If the project has a dedicated setup or quickstart guide, follow that guide for dependency installation rather than installing model dependencies into an unrelated global Python environment.

### 2. Configure local secrets

- Start from the tracked example environment files, if present.
- Keep `.env`, `.env.local`, API tokens, bridge tokens, and credentials out of Git.
- Never paste secret values into logs, issue reports, screenshots, or documentation.
- Do not replace an existing bridge token merely to troubleshoot startup; first inspect the relevant error without printing the token.

### 3. Run the application

From the project root, use the supplied launcher:

```powershell
Set-Location "C:\Projects\ArkByte Voice Studio Web 1.2.0"
.\START ARKBYTE VOICE STUDIO WEB.ps1
```

The launcher is expected to verify the configured runtime, start the backend and frontend, and wait for readiness before opening the local studio. Use the exact launcher filename present in your checkout.

### 4. Verify local listeners

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 3000,8765 } |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

Use the supplied stop script for shutdown. It checks the project and listener ownership and requires its exact confirmation phrase. Do not terminate processes by PID unless you have independently verified ownership.

For the guided setup, see **[Quickstart](docs/quickstart.md)**.

---

## ✦ Validation and test results

### Latest recorded local validation

The most recent supplied run reported:

| Check | Recorded result |
|:--|:--|
| Python runtime | Python 3.12.10 |
| PyTorch | 2.6.0 + CUDA 12.6 build |
| CUDA availability | Available on the test machine |
| GPU | NVIDIA GeForce RTX 3050 Laptop GPU, 6 GB |
| `pip check` | No broken requirements reported |
| Backend tests | **61 tests passed** |
| Frontend TypeScript check | Passed (`next typegen` and `tsc --noEmit`) |
| Next.js production build | Passed |
| Production routes | `/`, `/_not-found`, `/api/[...path]`, `/icon.svg` |

> [!WARNING]
> **Known test-runner cleanup warning:** after the backend tests completed successfully, Python reported a Windows `PermissionError [WinError 32]` while cleaning a temporary test log file that was still open. This did not change the reported result of 61 passing tests, but the temporary log-handle cleanup should be fixed and rechecked.

These are recorded results from one local machine and one run, not a guarantee that every environment will produce the same result. Re-run checks after code changes and update this section only from fresh logs.

### Repeatable checks

Run the project's existing test and frontend scripts as defined in its configuration. Do not assume optional model weights are present on a clean clone. Record the command, environment, result, and any warning in `docs/reports/validation-report.md` when that report exists.

## ✦ Repository layout

```text
ArkByte-Voice-Studio/
├── docs/
│   ├── assets/
│   │   ├── screenshots/
│   │   └── video/
│   ├── reports/
│   └── ...
├── service/
│   ├── arkbyte_voice_studio/
│   ├── tests/
│   └── main.py
├── web/
│   ├── app/
│   ├── components/
│   └── lib/
├── START ARKBYTE VOICE STUDIO WEB.ps1
├── STOP ARKBYTE VOICE STUDIO WEB.ps1
├── VERIFY ARKBYTE RUNNERS.ps1
├── python-runtime.txt
└── README.md
```

This is a high-level guide; optional files and model-specific modules may differ by release. The actual checkout is authoritative.

## ✦ Security and responsible use

- Use voice recordings only with the speaker's informed consent or other valid authorization.
- Do not impersonate a person, mislead listeners, commit fraud, or bypass identity/security checks.
- Clearly disclose synthetic or altered audio where context requires it.
- Treat uploaded reference audio, generated audio, model files, logs, and credentials as potentially sensitive.
- Keep secrets and local user data out of source control.
- Review [`SECURITY.md`](SECURITY.md) and the [Safe Use Policy](docs/SAFE-USE-POLICY.md) before distributing or deploying the application.
- A local-first design does not automatically make every integration private; review the data path of any external service or hosted model.

## ✦ Troubleshooting

| Symptom | Checks |
|:--|:--|
| Backend does not start | Confirm the interpreter path, Python dependencies, model assets, port availability, and `logs/backend.log`. |
| Frontend does not start | Confirm Node/npm versions, installed dependencies, port 3000 availability, and `logs/nextjs.log`. |
| CUDA unavailable | Check NVIDIA driver compatibility, the selected PyTorch build, and the interpreter referenced by runtime configuration. |
| Model unavailable | Confirm the selected adapter, model dependencies, and required model assets are installed. |
| API bridge error | Check local configuration and bridge setup without printing or sharing secret values. |
| Stop script cancels | Enter the exact confirmation phrase shown by the script; cancellation intentionally leaves processes running. |
| Test cleanup warning | Inspect test teardown and ensure file handles are closed before temporary directories are removed. |

## ✦ Documentation

| Guide | What it covers |
|:--|:--|
| [Quickstart](docs/quickstart.md) | Local setup and first run |
| [Architecture](docs/ARCHITECTURE.md) | System design and component boundaries |
| [Flowcharts](docs/flowcharts.md) | Workflow diagrams |
| [Custom Voice Lab](docs/CUSTOM-VOICE-LAB.md) | Reference-guided voice workflows |
| [Model Adapters](docs/MODEL_ADAPTERS.md) | Model integration details |
| [Voice Intelligence](docs/VOICE_INTELLIGENCE.md) | Voice-related capabilities and concepts |
| [Safe Use Policy](docs/SAFE-USE-POLICY.md) | Responsible-use guidance |
| [Security](docs/SECURITY.md) | Security notes |
| [Interview Guide](docs/interview-guide.md) | Technical project overview |
| [Manual Voice Testing](docs/MANUAL_VOICE_TESTING.md) | Manual verification |
| [Validation Report](docs/reports/validation-report.md) | Recorded test evidence |
| [Release Audit](docs/reports/repository-release-audit.md) | Repository audit |
| [Release Notes](docs/releases/release-notes.md) | Release history |
| [Repository Settings](docs/project/repository-settings.md) | Repository configuration notes |

## ✦ Development roadmap

- Keep model adapters isolated and document each adapter's supported inputs, dependencies, and limitations.
- Improve automated regression coverage for audio generation, storage, and API validation.
- Resolve the temporary test-log handle cleanup warning and record a clean rerun.
- Maintain reproducible setup instructions for CPU and CUDA environments.
- Keep screenshots, walkthrough video, architecture diagrams, and validation evidence synchronized with the actual release.
- Complete a final repository audit before creating a release or pushing changes.

## ✦ Contributing

1. Review the current architecture and relevant documentation before changing a component.
2. Keep secrets, local environments, model weights, generated audio, and private user data out of commits.
3. Add or update tests for behavior changes.
4. Run backend tests, frontend type checking, and a production build.
5. Update documentation and validation evidence to match the verified implementation.
6. Review `git diff` and `git status` before requesting a commit or push.

## ✦ License

Add the project's chosen license before presenting this repository as an open-source release. Until a license file and explicit license terms are present, all rights remain with the respective copyright holder.

---

<div align="center">

**ARKBYTE VOICE STUDIO**

*Local-first voice experimentation. Modular by design.*

<sub>Built for responsible AI audio workflows.</sub>

</div>
