from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from .config import ensure_app_dirs, ensure_within
from .errors import AppError
from .media import find_executable


class EcapaSpeakerEvaluator:
    """Optional SpeechBrain ECAPA-TDNN speaker embedding comparison.

    First use downloads the public pretrained encoder into the local app cache.
    Cosine similarity is a model score, not a calibrated probability or proof
    that two recordings are the same person.
    """

    SOURCE = "speechbrain/spkrec-ecapa-voxceleb"

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self._encoder = None
        self._device = "cpu"
        self._model_dir = ensure_app_dirs()["cache"] / "speechbrain-ecapa"

    @staticmethod
    def is_installed() -> bool:
        try:
            import importlib.util
            return importlib.util.find_spec("speechbrain") is not None
        except (ImportError, ValueError):
            return False

    def status(self) -> dict[str, Any]:
        return {
            "id": "ecapa_tdnn",
            "name": "SpeechBrain ECAPA-TDNN",
            "package": "speechbrain",
            "installed": self.is_installed(),
            "weights_cached": (self._model_dir / "embedding_model.ckpt").exists(),
            "status": "ready" if self.is_installed() and (self._model_dir / "embedding_model.ckpt").exists()
                      else "installed_weights_not_cached" if self.is_installed() else "optional_dependency_missing",
            "first_use_download": True,
        }

    def _load(self) -> None:
        if self._encoder is not None:
            return
        if not self.is_installed():
            raise AppError(
                "ECAPA speaker evaluation is optional. Install the matching SpeechBrain and PyTorch dependencies first.",
                "ECAPA_NOT_INSTALLED",
            )
        try:
            import torch
            from speechbrain.inference.speaker import EncoderClassifier
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model_dir.mkdir(parents=True, exist_ok=True)
            self._encoder = EncoderClassifier.from_hparams(
                source=self.SOURCE,
                savedir=str(self._model_dir),
                run_opts={"device": self._device},
            )
        except Exception as exc:
            self.logger.exception("Unable to load ECAPA-TDNN speaker encoder")
            self._encoder = None
            raise AppError(
                "ECAPA could not load. Check the PyTorch/torchaudio/SpeechBrain versions and model cache/network access.",
                "ECAPA_LOAD_FAILED",
            ) from exc

    @staticmethod
    def _read_16k(path: Path) -> np.ndarray:
        ffmpeg = find_executable("ffmpeg")
        if not ffmpeg:
            raise AppError("FFmpeg is required for speaker embedding evaluation.", "FFMPEG_MISSING")
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"],
            capture_output=True, timeout=180, check=False,
        )
        if result.returncode != 0 or not result.stdout:
            raise AppError(f"Could not decode audio for speaker evaluation: {path.name}", "ECAPA_AUDIO_DECODE_FAILED")
        audio = np.frombuffer(result.stdout, dtype="<f4").astype(np.float32)
        if len(audio) < 16000 or not np.isfinite(audio).all():
            raise AppError(f"Audio is too short or invalid for speaker evaluation: {path.name}", "ECAPA_AUDIO_TOO_SHORT")
        return audio

    def _embedding(self, path: Path) -> np.ndarray:
        import torch
        waveform = torch.from_numpy(self._read_16k(path)).unsqueeze(0)
        with torch.no_grad():
            tensor = self._encoder.encode_batch(waveform)
        embedding = tensor.detach().float().cpu().numpy().reshape(-1)
        norm = float(np.linalg.norm(embedding))
        if not np.isfinite(embedding).all() or norm <= 1e-8:
            raise AppError("ECAPA returned an invalid speaker embedding.", "ECAPA_EMBEDDING_INVALID")
        return embedding / norm

    def compare(self, profile_id: str, samples: list[dict[str, Any]], generated_audio: Path,
                profiles_root: Path) -> dict[str, Any]:
        if len(samples) < 2:
            raise AppError("ECAPA comparison requires at least two reference recordings for a more stable centroid.", "ECAPA_NEEDS_MULTIPLE_REFERENCES")
        generated_audio = generated_audio.resolve(strict=True)
        profile_dir = ensure_within(profiles_root, profiles_root / profile_id)
        self._load()
        embeddings: list[np.ndarray] = []
        for sample in samples:
            source = ensure_within(profile_dir, Path(sample["original_path"]))
            embeddings.append(self._embedding(source))
        reference = np.mean(np.stack(embeddings, axis=0), axis=0)
        reference_norm = float(np.linalg.norm(reference))
        if reference_norm <= 1e-8:
            raise AppError("Reference speaker embeddings could not be aggregated.", "ECAPA_REFERENCE_INVALID")
        reference /= reference_norm
        output_embedding = self._embedding(generated_audio)
        cosine = float(np.clip(np.dot(reference, output_embedding), -1.0, 1.0))
        per_sample = [float(np.clip(np.dot(item, output_embedding), -1.0, 1.0)) for item in embeddings]
        return {
            "model": self.SOURCE,
            "model_type": "ECAPA-TDNN speaker embedding",
            "device": self._device,
            "reference_count": len(embeddings),
            "centroid_cosine_similarity": round(cosine, 4),
            "per_reference_cosine": [round(score, 4) for score in per_sample],
            "score_interpretation": "Cosine similarity in this pretrained embedding space. It is not a percentage, calibrated probability, accent score, or guarantee of identity. Use held-out speech and blind listening.",
        }
