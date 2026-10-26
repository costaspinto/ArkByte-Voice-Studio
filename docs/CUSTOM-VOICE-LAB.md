# Custom Voice Lab – HF3

## What this patch adds

The Custom Voice Lab page selects an existing consenting speaker profile, reads its enrolled samples and exposes transcript review status. Once every recording has a non-empty transcript explicitly reviewed and saved by the operator, the page enables **Export training dataset**.

The existing local API export endpoint packages the full source utterances as mono 24 kHz PCM WAV, a reference anchor, `train_raw.jsonl`, a manifest and a training README. The dataset is intended for the official Qwen3-TTS single-speaker Base fine-tuning workflow.

## Workflow

1. Create one voice profile for a speaker whose voice you own or have explicit permission to use.
2. Add multiple varied, clean recordings of that same speaker. Do not mix speakers.
3. Open Voice Lab and review each recording's transcript against the actual audio. Correct names, punctuation, disfluencies, omissions and pronunciations, then save the transcript.
4. Open **Custom Voice Lab**, select the profile and confirm every recording shows **Verified**.
5. Export the ZIP. Keep it private; it contains biometric voice data.
6. In a separate Python/CUDA environment, follow the official upstream instructions: https://github.com/QwenLM/Qwen3-TTS/tree/main/finetuning . Install the exact dependencies and obtain the Base checkpoint and tokenizer as instructed upstream. Run the `prepare_data.py` and `sft_12hz.py` steps documented in the exported README.
7. Test the resulting checkpoint on held-out sentences that were not included in training. Listen for identity drift, pronunciation, prosody and overfitting before considering it usable.

## Explicit scope boundary

HF3 adds dataset readiness and export to the web UI. It does **not** run Qwen fine-tuning, install Qwen training dependencies, download model weights, import a trained checkpoint, or provide a one-click trained-model inference adapter. Those remain separate follow-on engineering tasks. A data export is not a trained custom voice.

## Hardware note

The known target laptop has an RTX 3050 Laptop GPU with 6 GB VRAM. Do not assume full fine-tuning fits in this memory budget. Use a larger GPU or hosted training environment unless the upstream project documents a supported memory-efficient configuration that has been validated on the target setup.

## Privacy and consent

Voice recordings and derived speaker models are biometric data. Use only your own voice or a voice for which you have explicit, informed permission. Do not use the workflow for deceptive impersonation, fraud, harassment, non-consensual intimate content or bypassing identity verification. Securely store and delete exported datasets when no longer needed.
