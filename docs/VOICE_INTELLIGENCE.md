# Voice Intelligence Pipeline — ArkByte 1.2.0

## Purpose

ArkByte 1.2.0 adds a multi-recording speaker-enrolment workflow around the existing Chatterbox generation path. The source recordings remain the source of truth. Model-ready references, acoustic diagnostics, transcripts, anchor selection and personal pronunciation substitutions are stored separately.

This pipeline is intentionally explicit about what is measured and what is not. Recording-quality metrics are not speaker verification. Speaker-embedding similarity is not a probability of identity. Accent notes are user-confirmed metadata, not automatic accent recognition.

## Enrolment data

A profile can contain up to ten recordings in the initial enrolment flow, with later additions until the total reaches ten. Each recording must be 5 seconds to 15 minutes and is capped at 250 MB; an upload batch is capped at 500 MB.

For every recording ArkByte stores:

- The original uploaded media, unmodified.
- A separate 24 kHz, mono, PCM WAV model reference made by channel mixing and resampling only.
- The operator-supplied transcript, if provided, or optional Faster-Whisper draft with an explicit reviewed/unreviewed state.
- Duration, input sample rate/channels, RMS level, peak, clipping ratio, silence/activity ratio, pitch estimates, spectral centroid, heuristic quality score and warnings.

The model reference clip is selected from the middle of long recordings and is limited to 30 seconds. The original audio is retained in full. The automatic anchor is the sample with the highest heuristic quality score. An operator can manually change the anchor in Voice Lab.

The heuristic quality score is for triage only. It is sensitive to microphone, room, speaking style and recording level. It does not identify a speaker and must not be optimized at the expense of preserving natural voice characteristics.

## Pipeline stages

| Stage | 1.2.0 behavior | Boundary |
|---|---|---|
| Consent/intake | Requires ownership or explicit permission confirmation | Confirmation is operator-supplied, not a legal determination |
| Audio quality | FFmpeg decode and acoustic diagnostics | Does not certify recording quality or speaker identity |
| Transcription | Optional Faster-Whisper local ASR creates draft transcripts; users can edit, review and explicitly save them | ASR is optional, first use downloads model weights, and draft text is never approved for training until saved by the user |
| Speaker identity | Optional ECAPA-TDNN embedding comparison in Benchmark Studio | Requires SpeechBrain and pretrained weights; first use may download weights |
| Accent/pronunciation | Speaker-confirmed accent notes and personal dictionary | No automatic accent/dialect classifier |
| Prosody | Basic pitch/activity/spectral descriptors; punctuation-aware chunk pauses | No phoneme alignment or learned speaker-specific prosody adapter |
| Reference selection | Quality-ranked anchor with manual override | The best heuristic-quality sample is not necessarily the best perceptual reference; listen and choose |
| Generation | Chatterbox baseline; optional VoxCPM 2 adapter | Model quality and output must be evaluated on the operator's voice |
| Benchmark | Acoustic proxy plus optional ECAPA cosine comparison and A/B playback | No score guarantees perfect cloning, accent or naturalness |

## Pronunciation dictionary

Each profile can map a written term to a spoken text form. The longest matching terms are replaced case-insensitively before generation. Use this for names, acronyms and words that the TTS model consistently misreads.

This is a text-level workaround, not a phoneme synthesizer. Enter a spoken form the selected model can read naturally. The dictionary applies to generated text; it does not alter saved source transcripts or source audio.

## Benchmark interpretation

The built-in acoustic proxy compares generated output with median source values for median F0, RMS level, spectral centroid and active-speech ratio. These are intentionally labelled proxy metrics. They can change because of room acoustics, microphone, script, emotion, sentence length, playback level and model normalization.

The optional ECAPA-TDNN adapter uses SpeechBrain's pretrained `speechbrain/spkrec-ecapa-voxceleb` encoder to calculate embeddings at 16 kHz and a cosine similarity between a reference-embedding centroid and generated audio. This is a model-space comparison, not a calibrated probability, percentage match, accent score or proof of identity. Compare several held-out phrases and listen blindly.

## Dataset export for Qwen3-TTS

Voice Lab can use optional Faster-Whisper for draft transcripts. Users must inspect the audio, correct the draft and click Save transcript. ArkByte tracks this approval separately; an unreviewed ASR draft cannot be exported. Voice Lab can export a Qwen3-TTS single-speaker fine-tuning data bundle only after every enrolment recording has a transcript explicitly reviewed by the user. The bundle contains full source utterances transcoded to 24 kHz mono WAV, one shared anchor reference, `train_raw.jsonl`, a manifest and instructions.

The official Qwen3-TTS fine-tuning workflow currently documents single-speaker fine-tuning for its 0.6B and 1.7B Base models. It expects JSONL fields `audio`, `text` and `ref_audio`, then a data-preparation step and SFT training. ArkByte exports the data; it does not execute Qwen fine-tuning or load the fine-tuned checkpoint in this release. See the [official Qwen3-TTS fine-tuning README](https://github.com/QwenLM/Qwen3-TTS/tree/main/finetuning).

Review every transcript/audio pair before training. A transcript must represent the entire exported original recording, including spoken names, disfluencies and words that are often missed by ASR. If a transcript is missing or an ASR draft has not been explicitly reviewed and saved, export is rejected.

## Local data and privacy

Default Windows data root: `%LOCALAPPDATA%\ArkByte Voice Studio`.

```text
ArkByte Voice Studio/
├── arkbyte_voice_studio.db
├── profiles/<profile-id>/
│   ├── samples/       # Original recordings
│   └── references/    # Separate 24 kHz model references
├── outputs/           # Generated WAV files
├── cache/             # Optional local model cache
└── logs/
```

Voice recordings, model references, transcripts, pronunciation entries and generated outputs are biometric/personal data. Keep the directory private, restrict Windows account access, and do not put it in public cloud-sync folders. The Qwen training ZIP contains copied voice data and should be handled with the same care. Deleting a profile removes its profile directory and database-linked samples/metadata.

## Recommended manual acceptance

Use `MANUAL_VOICE_TESTING.md` to create a ten-recording dataset, verify the transcript coverage, run Chatterbox and (optionally) VoxCPM 2, compare fixed phrases, and note pronunciation/identity/prosody differences. Do not tune using training phrases only; preserve held-out phrases for evaluation.
