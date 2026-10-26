from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import numpy as np

from .errors import AppError
from .engine import ChatterboxEngine
from .text_processing import pause_after_chunk_seconds, split_script

Progress = Callable[[str], None]


class VoxCPM2Engine:
    """Optional lazy VoxCPM 2 adapter. It never loads unless selected by the user."""

    MODEL_ID = "openbmb/VoxCPM2"

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self._model = None
        self._loaded = False
        self.device = "not loaded"

    @staticmethod
    def is_installed() -> bool:
        try:
            import importlib.util
            return importlib.util.find_spec("voxcpm") is not None
        except (ImportError, ValueError):
            return False

    def unload(self) -> None:
        """Release model tensors before another adapter claims GPU memory."""
        self._model = None
        self._loaded = False
        self.device = "not loaded"
        try:
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as exc:
            self.logger.debug("VoxCPM CUDA cache cleanup skipped: %s", exc)

    def load(self, progress: Progress | None = None) -> None:
        if self._loaded:
            return
        if not self.is_installed():
            raise AppError(
                "VoxCPM 2 is not installed. Install it only in a separate test environment first, then point ArkByte to that environment or opt in to the VoxCPM dependency setup.",
                "VOXCPM_NOT_INSTALLED",
            )
        if progress:
            progress("Loading VoxCPM 2. The first run downloads model weights and can take several minutes…")
        try:
            from voxcpm import VoxCPM
            self._model = VoxCPM.from_pretrained(
                self.MODEL_ID,
                load_denoiser=False,
                device="auto",
                optimize=False,
            )
            self.device = "automatic device selection"
            self._loaded = True
            self.logger.info("VoxCPM 2 loaded successfully")
        except Exception as exc:
            self.logger.exception("VoxCPM 2 model loading failed")
            self._model = None
            self._loaded = False
            raise AppError(
                "VoxCPM 2 could not load. The model may need additional memory, a compatible PyTorch build, or a fresh isolated environment. Chatterbox remains available.",
                "VOXCPM_LOAD_FAILED",
            ) from exc

    def generate(self, text: str, reference_audio: Path, output_path: Path,
                 prompt_text: str = "", progress: Progress | None = None) -> Path:
        if not reference_audio.is_file():
            raise AppError("The selected voice reference file is missing.", "PROFILE_AUDIO_MISSING")
        self.load(progress)
        chunks = split_script(text)
        generated: list[np.ndarray] = []
        sample_rate = int(getattr(getattr(self._model, "tts_model", None), "sample_rate", 48000))
        for index, chunk in enumerate(chunks, start=1):
            if progress:
                progress(f"VoxCPM 2 generating paragraph {index} of {len(chunks)}…")
            kwargs = {
                "text": chunk,
                "reference_wav_path": str(reference_audio),
                "cfg_value": 2.0,
                "inference_timesteps": 10,
                "denoise": False,
            }
            # VoxCPM's transcript-conditioned Hi-Fi mode requires the exact
            # transcript of the supplied prompt audio; the service only passes
            # one when the enrolled sample is no longer than the reference clip.
            if prompt_text.strip():
                kwargs["prompt_wav_path"] = str(reference_audio)
                kwargs["prompt_text"] = prompt_text.strip()
            try:
                audio = self._model.generate(**kwargs)
                data = np.asarray(audio, dtype=np.float32).squeeze()
                if data.ndim != 1:
                    data = data.reshape(-1)
                if data.size == 0 or not np.isfinite(data).all():
                    raise ValueError("Model returned empty or non-finite audio")
                generated.append(np.clip(data, -1.0, 1.0))
            except Exception as exc:
                self.logger.exception("VoxCPM 2 generation failed on paragraph %s", index)
                raise AppError(
                    f"VoxCPM 2 failed on paragraph {index}. Try a shorter script, a different reference recording, or Chatterbox.",
                    "VOXCPM_GENERATION_FAILED",
                ) from exc
        if not generated:
            raise AppError("VoxCPM 2 returned no audio.", "VOXCPM_NO_OUTPUT")
        parts: list[np.ndarray] = []
        for index, audio in enumerate(generated):
            if index:
                pause = pause_after_chunk_seconds(chunks[index - 1])
                parts.append(np.zeros(int(sample_rate * pause), dtype=np.float32))
            parts.append(audio)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ChatterboxEngine._write_wav_atomic(output_path, np.concatenate(parts), sample_rate)
        self.logger.info("VoxCPM 2 generated %s chunks to %s", len(generated), output_path)
        return output_path


class VoxCPM05Engine:
    """Optional VoxCPM 0.5B adapter for transcript-conditioned voice continuation."""

    MODEL_ID = "openbmb/VoxCPM-0.5B"
    SAMPLE_RATE = 16000

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self._model = None
        self._loaded = False
        self.device = "not loaded"
        self.sample_rate = self.SAMPLE_RATE

    @staticmethod
    def is_installed() -> bool:
        try:
            import importlib.util
            return importlib.util.find_spec("voxcpm") is not None
        except (ImportError, ValueError):
            return False

    def unload(self) -> None:
        """Release model tensors before another adapter claims GPU memory."""
        self._model = None
        self._loaded = False
        self.device = "not loaded"
        try:
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as exc:
            self.logger.debug("VoxCPM CUDA cache cleanup skipped: %s", exc)

    def load(self, progress: Progress | None = None) -> None:
        if self._loaded:
            return
        if not self.is_installed():
            raise AppError(
                "VoxCPM is not installed. Run INSTALL VOXCPM MODELS.ps1 after reviewing the dependency check, then restart ArkByte.",
                "VOXCPM_NOT_INSTALLED",
            )
        if progress:
            progress("Loading VoxCPM 0.5B. The first load downloads its model weights…")
        try:
            from voxcpm import VoxCPM

            # Disable torch.compile for predictable Windows behavior and to avoid
            # introducing a second compilation cache into the existing runtime.
            try:
                self._model = VoxCPM.from_pretrained(
                    self.MODEL_ID,
                    device="auto",
                    optimize=False,
                )
                try:
                    import torch
                    self.device = "cuda" if torch.cuda.is_available() else "cpu"
                except Exception:
                    self.device = "automatic device selection"
            except Exception as gpu_exc:
                message = str(gpu_exc).lower()
                is_memory_error = any(token in message for token in ("out of memory", "cuda error", "cublas status alloc"))
                if not is_memory_error:
                    raise
                self._model = None
                try:
                    import gc
                    import torch
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
                if progress:
                    progress("VoxCPM 0.5B could not fit in GPU memory. Retrying on CPU; generation will be slower…")
                self._model = VoxCPM.from_pretrained(
                    self.MODEL_ID,
                    device="cpu",
                    optimize=False,
                )
                self.device = "cpu (GPU memory fallback)"
            self.sample_rate = int(getattr(getattr(self._model, "tts_model", None), "sample_rate", self.SAMPLE_RATE))
            self._loaded = True
            self.logger.info("VoxCPM 0.5B loaded on %s", self.device)
        except Exception as exc:
            self._model = None
            self._loaded = False
            self.logger.exception("VoxCPM 0.5B model load failed")
            raise AppError(
                "VoxCPM 0.5B could not load. Check the optional package installation, available RAM/VRAM and the local model cache. Chatterbox remains available.",
                "VOXCPM05_LOAD_FAILED",
            ) from exc

    @staticmethod
    def _to_numpy(audio) -> np.ndarray:
        if hasattr(audio, "detach"):
            audio = audio.detach().float().cpu().numpy()
        data = np.asarray(audio, dtype=np.float32).squeeze()
        if data.ndim != 1:
            data = data.reshape(-1)
        if data.size == 0 or not np.isfinite(data).all():
            raise AppError("VoxCPM 0.5B returned empty or invalid audio.", "VOXCPM05_AUDIO_INVALID")
        return np.clip(data, -1.0, 1.0)

    def generate(
        self,
        text: str,
        reference_audio: Path,
        output_path: Path,
        prompt_text: str,
        progress: Progress | None = None,
    ) -> Path:
        if not reference_audio.is_file():
            raise AppError("The selected voice reference file is missing.", "PROFILE_AUDIO_MISSING")
        if not prompt_text.strip():
            raise AppError(
                "VoxCPM 0.5B requires the exact, reviewed transcript for the selected reference recording. Add or review the anchor transcript in Voice Lab, then save it.",
                "VOXCPM05_TRANSCRIPT_REQUIRED",
            )

        self.load(progress)
        chunks = split_script(text)
        generated: list[np.ndarray] = []
        for index, chunk in enumerate(chunks, start=1):
            if progress:
                progress(f"VoxCPM 0.5B generating paragraph {index} of {len(chunks)}…")
            try:
                audio = self._model.generate(
                    text=chunk,
                    prompt_wav_path=str(reference_audio),
                    prompt_text=prompt_text.strip(),
                    cfg_value=2.0,
                    inference_timesteps=10,
                    normalize=True,
                    denoise=False,
                    retry_badcase=False,
                )
                generated.append(self._to_numpy(audio))
            except AppError:
                raise
            except Exception as exc:
                self.logger.exception("VoxCPM 0.5B generation failed for paragraph %s", index)
                raise AppError(
                    f"VoxCPM 0.5B failed on paragraph {index}. Confirm the transcript matches the reference audio and try a shorter sentence.",
                    "VOXCPM05_GENERATION_FAILED",
                ) from exc

        if not generated:
            raise AppError("VoxCPM 0.5B returned no audio.", "VOXCPM05_NO_OUTPUT")

        parts: list[np.ndarray] = []
        for index, audio in enumerate(generated):
            if index:
                pause = pause_after_chunk_seconds(chunks[index - 1])
                parts.append(np.zeros(int(self.sample_rate * pause), dtype=np.float32))
            parts.append(audio)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ChatterboxEngine._write_wav_atomic(output_path, np.concatenate(parts), self.sample_rate)
        self.logger.info("VoxCPM 0.5B generated %s chunks to %s", len(generated), output_path)
        return output_path
