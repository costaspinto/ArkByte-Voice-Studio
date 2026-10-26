# Model adapters — ArkByte 1.2.0

## Chatterbox Multilingual V3

The existing Chatterbox engine remains the default. It is integrated with the existing local generation workflow and uses the selected profile anchor through `audio_prompt_path`. It continues to rely on the separately installed `chatterbox-tts` and PyTorch packages and model weights.

## VoxCPM 2 (optional generation adapter)

An optional, lazy adapter is included. It does not import, install, download or load VoxCPM during normal startup. The model loads only when the user selects it and submits generation.

The adapter uses `VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, device="auto", optimize=False)` and the model's `reference_wav_path` cloning interface. If the anchor recording has a manually supplied transcript and is 30 seconds or shorter, the adapter may also pass the same audio and transcript as a paired `prompt_wav_path` / `prompt_text` for transcript-conditioned Hi-Fi cloning. The transcript must exactly match the full reference clip; do not use a transcript that describes the longer original when the selected audio is a crop.

Install only in a cloned/tested environment after reviewing compatibility with the active PyTorch, CUDA and torchaudio packages. The app's optional requirement file is `service/requirements-voxcpm.txt`. The model downloads from the upstream model repository on first load. Chatterbox remains the fallback selected by the operator if the optional adapter is unavailable.

Official usage docs: https://voxcpm.readthedocs.io/en/latest/usage_guide.html

## Qwen3-TTS (single-speaker training data export)

The Voice Lab exporter writes a full-audio, transcript-required dataset in the official JSONL layout (`audio`, `text`, `ref_audio`). The app does not install Qwen, train model weights, create the final custom-voice checkpoint or run Qwen inference. Use the official `Qwen3-TTS-12Hz-0.6B-Base` or `1.7B-Base` workflow from a separate environment after reviewing the source dataset and hardware requirements.

Official instructions: https://github.com/QwenLM/Qwen3-TTS/tree/main/finetuning

## Faster-Whisper (optional local transcript drafts)

Voice Lab offers a per-recording Auto-transcribe action. It uses `faster-whisper` lazily; no model is loaded or downloaded on application startup. The first transcription may download model weights into the ArkByte cache. The default model is `small`; set `ARKBYTE_WHISPER_MODEL` to `tiny`, `base`, `small`, `medium`, or `large-v3` before starting the backend to select another size. Install using `service/requirements-transcription.txt`.

Transcripts are drafts, not ground truth. ArkByte stores them as unreviewed until the user verifies the complete original recording and clicks Save transcript. The Qwen exporter rejects missing or unreviewed transcripts.

## ECAPA-TDNN (optional speaker-identity evaluation)

Benchmark Studio has an optional SpeechBrain adapter for `speechbrain/spkrec-ecapa-voxceleb`. It loads lazily on explicit request, creates a mean reference embedding from the profile samples and compares generated audio to that centroid with cosine similarity. First model use may download pretrained weights to the ArkByte local cache.

The adapter requirement file is `service/requirements-speaker-id.txt`. SpeechBrain, PyTorch and torchaudio versions must be compatible with one another. For the safest setup, clone the web Python environment before installing optional dependencies and test CPU/CUDA inference there. The adapter is not a voice cloning engine and does not classify accents.

Official model usage: https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb

## Not integrated in 1.2.0

- Qwen3-TTS inference/checkpoint loading inside ArkByte.
- Automated Qwen fine-tuning.
- WavLM speaker embedding model.
- Automatic accent classification, phoneme alignment and learned speaker-specific prosody adaptation. Optional Faster-Whisper transcription is implemented as a draft-only local adapter.
- Phoneme alignment, automatic accent classification and learned speaker-specific prosody adaptation.

These are not represented as installed or completed capabilities in the model registry.


## VoxCPM model options (1.2.0 maintenance update)

ArkByte exposes two VoxCPM checkpoints through the optional `voxcpm` package:

- `voxcpm05` uses `openbmb/VoxCPM-0.5B`. This is a smaller continuation-cloning path for English and Chinese. It requires the exact reviewed transcript of the selected anchor reference and limits that anchor to 30 seconds or less. The upstream FAQ lists approximately 5 GB VRAM for the 0.5B generation family; this is tight on a 6 GB laptop GPU and is not a guarantee that generation will fit.
- `voxcpm2` uses `openbmb/VoxCPM2` for multilingual reference conditioning. The upstream FAQ lists approximately 8 GB VRAM. It is not recommended on a 6 GB GPU.

The service releases the previously loaded adapter before loading another model to avoid keeping Chatterbox and VoxCPM weights resident together. Switching back can require Chatterbox to load again. Model weights are downloaded on first use; installing the Python package alone does not download checkpoints.

Use `INSTALL VOXCPM MODELS.ps1` only after inspecting the dry-run package plan. The installer pins already installed versions of PyTorch, torchaudio, torchvision, NumPy, Triton and xformers, and aborts if pip proposes changing one of them. It does not install model weights.

VoxCPM 0.5B support in this build is inference-only. It is not fine-tuned by uploading ten recordings. The current app uses a single selected anchor and a reviewed transcript; multi-recording training/fine-tuning would require a separate dataset preparation and training pipeline.
