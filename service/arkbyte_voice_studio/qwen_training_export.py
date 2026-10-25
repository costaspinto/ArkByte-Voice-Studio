from __future__ import annotations

import io
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from .config import ensure_within
from .errors import AppError
from .media import find_executable


def build_qwen_training_bundle(profile_id: str, samples: list[dict[str, Any]], profiles_root: Path) -> bytes:
    """Build a transcript-verified Qwen3-TTS single-speaker SFT data package.

    No model weights or training code are bundled. Every source utterance is
    transcoded in full to mono 24 kHz WAV, retaining transcript/audio alignment.
    """
    if not samples:
        raise AppError("This voice profile has no enrolled recordings.", "TRAINING_DATASET_EMPTY")
    missing = [sample.get("source_name", sample.get("id", "recording"))
               for sample in samples
               if not str(sample.get("transcript", "")).strip() or not bool(sample.get("transcript_reviewed", False))]
    if missing:
        preview = ", ".join(str(name) for name in missing[:5])
        raise AppError(
            f"Add and explicitly review the exact transcript for every recording before exporting. Incomplete or unreviewed: {preview}",
            "TRAINING_TRANSCRIPTS_REVIEW_REQUIRED",
        )
    anchors = [sample for sample in samples if sample.get("is_anchor")]
    anchor = anchors[0] if anchors else samples[0]
    anchor_path = ensure_within(profiles_root / profile_id, Path(anchor["model_reference_path"]))
    if not anchor_path.is_file():
        raise AppError("The selected reference anchor is missing. Re-select an available recording.", "TRAINING_ANCHOR_MISSING")
    ffmpeg = find_executable("ffmpeg")
    if not ffmpeg:
        raise AppError("FFmpeg is required to prepare Qwen training audio.", "FFMPEG_MISSING")

    memory = io.BytesIO()
    metadata: list[dict[str, str]] = []
    with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(anchor_path, "audio/ref.wav")
        for index, sample in enumerate(samples, start=1):
            source = ensure_within(profiles_root / profile_id, Path(sample["original_path"]))
            if not source.is_file():
                raise AppError(f"Original recording is unavailable: {sample.get('source_name', index)}", "TRAINING_AUDIO_MISSING")
            relative_audio = f"audio/utt{index:03d}.wav"
            converted = io.BytesIO()
            command = [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source),
                "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", "-f", "wav", "pipe:1",
            ]
            try:
                result = subprocess.run(command, capture_output=True, timeout=240, check=False)
            except subprocess.TimeoutExpired as exc:
                raise AppError(f"Audio conversion timed out for {sample.get('source_name', index)}.", "TRAINING_AUDIO_TIMEOUT") from exc
            if result.returncode != 0 or not result.stdout:
                raise AppError(f"Could not convert {sample.get('source_name', index)} to WAV.", "TRAINING_AUDIO_CONVERSION_FAILED")
            converted.write(result.stdout)
            archive.writestr(relative_audio, converted.getvalue())
            metadata.append({
                "audio": relative_audio,
                "text": str(sample["transcript"]).strip(),
                "ref_audio": "audio/ref.wav",
            })
        archive.writestr("train_raw.jsonl", "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in metadata))
        archive.writestr("MANIFEST.json", json.dumps({
            "dataset_type": "Qwen3-TTS single-speaker fine-tuning input",
            "profile_id": profile_id,
            "utterance_count": len(metadata),
            "sample_rate_hz": 24000,
            "channels": 1,
            "transcript_validation": "Every transcript was explicitly marked reviewed by the user; exactness remains the speaker/operator's responsibility.",
            "reference_audio": "audio/ref.wav",
        }, indent=2))
        archive.writestr("README_TRAINING.md", _readme(len(metadata)))
    return memory.getvalue()


def _readme(count: int) -> str:
    return f'''# Qwen3-TTS single-speaker training data\n\nThis archive contains {count} source utterances, a shared reference recording, and `train_raw.jsonl`. It does **not** contain Qwen model weights, tokenizer weights, or training code.\n\n## Before training\n\n- Review every transcript in `train_raw.jsonl` against its corresponding audio. Correct all omissions, punctuation, names, disfluencies, and pronunciation text before training.\n- This dataset is intended for one consenting speaker only. Do not mix speakers.\n- Ten recordings are a useful enrolment set but may be too little for robust adaptation. Add more diverse, accurately transcribed utterances where appropriate.\n- Back up this package securely; it contains biometric voice data.\n\n## Official workflow\n\nFollow the current official instructions at https://github.com/QwenLM/Qwen3-TTS/tree/main/finetuning. The official Base-model workflow uses JSONL fields `audio`, `text`, and `ref_audio`, then runs `prepare_data.py` followed by `sft_12hz.py`.\n\nExample (run from the official Qwen3-TTS `finetuning` directory after installing its documented dependencies and downloading the tokenizer and a Base checkpoint):\n\n```bash\npython prepare_data.py \\\n  --device cuda:0 \\\n  --tokenizer_model_path /path/to/Qwen3-TTS-Tokenizer-12Hz \\\n  --input_jsonl /path/to/this-package/train_raw.jsonl \\\n  --output_jsonl /path/to/train_with_codes.jsonl\n\npython sft_12hz.py \\\n  --init_model_path /path/to/Qwen3-TTS-12Hz-0.6B-Base \\\n  --output_model_path /path/to/voice-adapter-output \\\n  --train_jsonl /path/to/train_with_codes.jsonl \\\n  --batch_size 1 \\\n  --lr 2e-6 \\\n  --num_epochs 3 \\\n  --speaker_name arkbyte_speaker\n```\n\nThe example uses a conservative batch size and epoch count, not a guaranteed optimum. Choose the Base model and training settings for your available GPU memory; monitor validation audio, overfitting, and checkpoint quality. Do not train on your primary production environment before testing in a separate environment.\n\n## Important limitations\n\n- Dataset export is implemented; model fine-tuning is not run by ArkByte in this release.\n- A complete exact transcript for each full source recording is required.\n- Fine-tuning can overfit small datasets and does not guarantee perfect identity, accent, or prosody reproduction.\n- Always validate on held-out phrases not present in the training recordings.\n'''
