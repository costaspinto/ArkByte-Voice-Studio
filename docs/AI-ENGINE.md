# Local AI engines and evaluation — 1.2.0

## Default: Chatterbox Multilingual V3

The Windows installer runs `verify_ai_engine.py` as a file and checks the same `ChatterboxMultilingualTTS` import used by the application. It avoids quoted `python -c` commands because Windows PowerShell 5.1 may strip embedded quotes from native arguments.

The web UI can start in service-only mode without neural model weights. Voice generation requires Chatterbox and PyTorch in the isolated web Python runtime selected by `python-runtime.txt`.

To install or repair the AI packages:

```powershell
.\INSTALL_WEB_WINDOWS.ps1 -InstallAI
```

The optional AI requirements install `chatterbox-tts==0.1.7` plus `soundfile`; these large dependencies are kept separate from the base API requirements. PyTorch dependencies are resolved by the Chatterbox package for the environment. GPU availability depends on the installed PyTorch wheel and NVIDIA driver. Verify:

```powershell
$Python = (Get-Content .\python-runtime.txt -Raw).Trim()
& $Python .\verify_ai_engine.py
```

Model weights are downloaded by Chatterbox on first model load. Subsequent inference is local. If CUDA generation fails, the existing ArkByte engine attempts CPU fallback; CPU generation is slower.

## Optional: VoxCPM 2 generation

`service/requirements-voxcpm.txt` describes an optional VoxCPM package. Do not install into the working Chatterbox environment without reviewing package and PyTorch compatibility. Test in a cloned environment first. The 1.2.0 adapter loads lazily after model selection; first use may download `openbmb/VoxCPM2`. It uses reference audio and, when the exact transcript matches the whole reference clip, transcript-conditioned Hi-Fi mode. It is not imported or loaded during normal startup.

## Optional: ECAPA-TDNN speaker evaluation

`service/requirements-speaker-id.txt` describes the optional SpeechBrain package. It must be compatible with the app's PyTorch and torchaudio versions. Benchmark Studio loads `speechbrain/spkrec-ecapa-voxceleb` on explicit user action and stores model files in the ArkByte cache. The result is a cosine similarity in a pretrained embedding space, not a calibrated probability or accent score.

## Qwen3-TTS data export

Voice Lab exports full 24 kHz mono utterances with exact transcripts and one shared reference audio in the official Qwen3-TTS single-speaker Base-model fine-tuning JSONL format. ArkByte does not run the tokenizer data-preparation or SFT steps, load the trained checkpoint, or run Qwen inference in 1.2.0. Follow the current official workflow from a separate environment.

See `docs/MODEL_ADAPTERS.md` for model status and `docs/MANUAL_VOICE_TESTING.md` for speaker testing.
