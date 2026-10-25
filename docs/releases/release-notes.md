# Release Notes — ArkByte Voice Studio Web 1.2.0

## Highlights

- **Voice Lab:** enrol up to ten recordings for one authorised speaker; retain the source audio and create separate model-ready references.
- **Audio diagnostics:** review sample duration, clipping, level, silence, pitch and spectral descriptors before generation.
- **Speaker profile:** choose an automatic quality-ranked anchor or manually select a more representative reference.
- **Transcript and pronunciation tools:** optional local Faster-Whisper draft transcription, explicit per-recording transcript review, and personal pronunciation substitutions for names, acronyms and difficult words.
- **Benchmark Studio:** A/B playback, acoustic proxy comparisons and optional ECAPA-TDNN speaker-embedding comparison.
- **Optional VoxCPM 2:** a lazy reference-conditioning generation adapter that does not alter the default Chatterbox installation.
- **Qwen3-TTS training data:** export full recordings, transcript-checked JSONL and a shared anchor reference for the official single-speaker fine-tuning workflow.
- **Natural stitching:** punctuation-aware pause durations replace one fixed pause after every chunk.

## Boundaries

This release does not automatically identify accents, certify transcripts without user review, align phonemes, fine-tune Qwen models, or promise a perfect voice match. ECAPA similarity is a model-space cosine score, not a probability or percentage. Qwen fine-tuning and inference remain a separate workflow. See `docs/VOICE_INTELLIGENCE.md`, `docs/MODEL_ADAPTERS.md` and `docs/MANUAL_VOICE_TESTING.md`.

## Validation

- 46 backend tests passed in the build environment.
- Python source compilation passed; TypeScript/TSX syntax transpilation passed for 12 source files with zero syntax errors.
- Full Next.js semantic typecheck and production build could not be completed because npm package downloads failed with registry DNS error `EAI_AGAIN`; a syntax transpile is not a substitute for those checks. Run `npm ci`, `npm run typecheck` and `npm run build` on a networked machine before final deployment.
- Real Chatterbox, VoxCPM and ECAPA inference, Windows installer/startup, GPU/CPU fallback and voice similarity still require manual validation on the target Windows PC with the operator's authorised recordings and hardware.


## Hotfix 1.2.0-HF1 — Windows installer preflight correction

The Windows PowerShell 5.1 installer no longer embeds quoted Python labels inside `python -c` invocations. AI and backend preflight checks run dedicated `.py` files instead, avoiding native-argument quote stripping. The AI preflight checks the exact `ChatterboxMultilingualTTS` class consumed by ArkByte, tests a CPU tensor operation, and treats CUDA availability as informational so CPU-only machines remain supported.
