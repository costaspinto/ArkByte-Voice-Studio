# Workflow diagrams

The SVG summaries below are designed for quick scanning in GitHub; the Mermaid definitions that follow preserve the editable source for each workflow.

<p align="center"><img src="assets/diagrams/creator-workflow.svg" alt="Creator workflow" width="100%" /></p>

<p align="center"><img src="assets/diagrams/safety-quality-gates.svg" alt="Safety and quality gates" width="100%" /></p>

---

## Profile enrolment

```mermaid
flowchart TD
  A[Select audio or video] --> B[Confirm voice ownership or permission]
  B --> C[Validate media type and size]
  C --> D[FFmpeg extracts selected segment]
  D --> E[Create managed profile + 24 kHz reference]
  E --> F[Optional additional recordings]
  F --> G[Audio quality analysis]
  G --> H[Transcript entry or optional ASR draft]
  H --> I[User reviews and saves transcript]
  I --> J[Choose anchor sample]
  J --> K[Reusable local voice profile]
```

## Narration generation

```mermaid
flowchart TD
  A[Select saved voice profile] --> B[Enter narration script]
  B --> C[Select language, model and controls]
  C --> D[Rights acknowledgement]
  D --> E[API validates profile consent and request]
  E --> F{Generation worker available?}
  F -- No --> G[Return busy / validation response]
  F -- Yes --> H[Load or reuse selected engine]
  H --> I[Generate local audio]
  I --> J[Write output under managed outputs directory]
  J --> K[Persist history row]
  K --> L[Play or download output]
```

## Custom training-data export

```mermaid
flowchart TD
  A[Voice profile with multiple samples] --> B[Transcript status inspection]
  B --> C{Every sample has a reviewed transcript?}
  C -- No --> D[Edit / transcribe / review / save]
  D --> B
  C -- Yes --> E[Export source clips + reference + JSONL]
  E --> F[Separate Qwen3-TTS fine-tuning workflow]
  F --> G[Held-out speaker and intelligibility evaluation]
  G --> H[Independent checkpoint packaging / integration]
```

The export is the boundary of the current product. Training and custom-checkpoint inference are not yet part of ArkByte 1.2.0.

## Destructive-action safeguards

```mermaid
flowchart TD
  A[User requests deletion] --> B{Profile deletion or history deletion?}
  B -->|Profile| C[Require exact DELETE VOICE phrase]
  B -->|History| D[Confirm selected item or clear all]
  C --> E[Backend checks generation lock]
  D --> F[Backend checks generation lock]
  E --> G[Validate path stays inside profile root]
  F --> H[Validate paths stay inside outputs root]
  G --> I[Remove profile-managed files + dependent metadata]
  H --> J[Remove generated audio + history entries]
  I --> K[Preserve projects, output history and model cache]
  J --> L[Preserve profiles, projects and model cache]
```
