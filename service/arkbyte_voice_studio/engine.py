from __future__ import annotations

import logging
import wave
from pathlib import Path
from typing import Callable

import numpy as np

from .errors import AppError
from .text_processing import pause_after_chunk_seconds, split_script

Progress = Callable[[str], None]


class ChatterboxEngine:
    """Lazy local Chatterbox Multilingual V3 wrapper with CUDA -> CPU fallback."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self._model = None
        self._torch = None
        self._device = None
        self._loaded = False

    @property
    def device(self) -> str:
        return self._device or "not loaded"

    def _choose_device(self) -> str:
        try:
            import torch
            self._torch = torch
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except Exception as exc:  # hardware probing must not crash the UI
            self.logger.warning("Device detection failed: %s", exc)
        return "cpu"

    def unload(self) -> None:
        """Release the resident model so another local model can use GPU memory."""
        self._model = None
        self._loaded = False
        self._device = None
        try:
            import gc
            gc.collect()
            if self._torch is None:
                import torch
                self._torch = torch
            if self._torch.cuda.is_available():
                self._torch.cuda.empty_cache()
        except Exception as exc:
            self.logger.debug("CUDA cache cleanup skipped: %s", exc)

    def load(self, progress: Progress | None = None, force_cpu: bool = False) -> None:
        if self._loaded:
            return
        if progress:
            progress("Loading the local Chatterbox model. The first load downloads model weights…")
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        except Exception as exc:
            self.logger.exception("Chatterbox import failed")
            raise AppError(
                "The AI engine is not installed. Run the AI setup command from the project folder, then restart the app.",
                "AI_NOT_INSTALLED",
            ) from exc
        device = "cpu" if force_cpu else self._choose_device()
        try:
            self._model = ChatterboxMultilingualTTS.from_pretrained(device=device)
            self._device = device
        except Exception as exc:
            self.logger.exception("Chatterbox model load failed on %s", device)
            if device == "cpu":
                raise AppError(
                    "The local AI model could not be loaded. Check the installation, free disk space and model download, then use Help > Open Logs.",
                    "AI_LOAD_FAILED",
                ) from exc
            if progress:
                progress(f"{device.upper()} model loading failed. Retrying with CPU…")
            try:
                if self._torch is None:
                    import torch
                    self._torch = torch
                if self._torch.cuda.is_available():
                    self._torch.cuda.empty_cache()
                self._model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
                self._device = "cpu"
            except Exception as cpu_exc:
                self.logger.exception("Chatterbox CPU fallback failed")
                raise AppError(
                    "The AI model failed on both the preferred device and CPU. Check the troubleshooting guide and application log.",
                    "AI_CPU_FALLBACK_FAILED",
                ) from cpu_exc
        self._loaded = True
        self.logger.info("Chatterbox loaded on %s", self._device)

    @staticmethod
    def _to_numpy(audio) -> np.ndarray:
        if hasattr(audio, "detach"):
            audio = audio.detach().float().cpu().numpy()
        data = np.asarray(audio, dtype=np.float32).squeeze()
        if data.ndim != 1:
            data = data.reshape(-1)
        if data.size == 0 or not np.isfinite(data).all():
            raise AppError("The model returned empty or invalid audio. Retry with a different voice sample or shorter text.", "AI_AUDIO_INVALID")
        return np.clip(data, -1.0, 1.0)

    def _fallback_to_cpu(self, progress: Progress | None = None) -> None:
        if self._device == "cpu":
            return
        if progress:
            progress("GPU generation failed. Clearing GPU memory and retrying on CPU…")
        try:
            if self._torch is None:
                import torch
                self._torch = torch
            if self._torch.cuda.is_available():
                self._torch.cuda.empty_cache()
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            self._model = None
            self._model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
            self._device = "cpu"
        except Exception as exc:
            self.logger.exception("CPU fallback initialization failed")
            raise AppError("GPU generation failed and the CPU fallback could not start. See the application log.", "AI_FALLBACK_FAILED") from exc

    def generate(self, text: str, reference_audio: Path, language_id: str, output_path: Path,
                 exaggeration: float = 0.5, cfg_weight: float = 0.5,
                 temperature: float = 0.8, progress: Progress | None = None) -> Path:
        if not reference_audio.is_file():
            raise AppError("The selected voice profile reference file is missing. Recreate the voice profile.", "PROFILE_AUDIO_MISSING")
        if not 0.25 <= exaggeration <= 2.0:
            raise AppError("Expression setting must be between 0.25 and 2.0.", "SETTING_EXAGGERATION")
        if not 0.0 <= cfg_weight <= 1.0:
            raise AppError("Pace setting must be between 0.0 and 1.0.", "SETTING_PACE")
        if not 0.05 <= temperature <= 2.0:
            raise AppError("Temperature must be between 0.05 and 2.0.", "SETTING_TEMPERATURE")

        chunks = split_script(text)
        self.load(progress=progress)
        sample_rate = int(getattr(self._model, "sr", 24000))
        generated: list[np.ndarray] = []

        for index, chunk in enumerate(chunks, start=1):
            if progress:
                progress(f"Generating paragraph {index} of {len(chunks)} on {self._device.upper()}…")
            try:
                audio = self._model.generate(
                    chunk,
                    language_id=language_id,
                    audio_prompt_path=str(reference_audio),
                    exaggeration=float(exaggeration),
                    cfg_weight=float(cfg_weight),
                    temperature=float(temperature),
                )
            except Exception as exc:
                self.logger.exception("Generation failed for chunk %s on %s", index, self._device)
                if self._device != "cpu":
                    self._fallback_to_cpu(progress)
                    try:
                        audio = self._model.generate(
                            chunk,
                            language_id=language_id,
                            audio_prompt_path=str(reference_audio),
                            exaggeration=float(exaggeration),
                            cfg_weight=float(cfg_weight),
                            temperature=float(temperature),
                        )
                        sample_rate = int(getattr(self._model, "sr", sample_rate))
                    except Exception as retry_exc:
                        self.logger.exception("CPU retry failed for chunk %s", index)
                        raise AppError(f"Audio generation failed on both GPU and CPU at paragraph {index}. Try a shorter script or another reference sample.", "AI_GENERATION_FAILED") from retry_exc
                else:
                    raise AppError(f"Audio generation failed at paragraph {index}. Try a shorter paragraph or recreate the voice profile.", "AI_GENERATION_FAILED") from exc
            generated.append(self._to_numpy(audio))

        if not generated:
            raise AppError("No audio was generated. Check the script and try again.", "AI_NO_OUTPUT")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined_parts: list[np.ndarray] = []
        for idx, piece in enumerate(generated):
            if idx:
                pause = pause_after_chunk_seconds(chunks[idx - 1])
                combined_parts.append(np.zeros(int(sample_rate * pause), dtype=np.float32))
            combined_parts.append(piece)
        combined = np.concatenate(combined_parts)
        self._write_wav_atomic(output_path, combined, sample_rate)
        self.logger.info("Generated %s chunks (%s seconds) to %s", len(generated), round(len(combined) / sample_rate, 2), output_path)
        return output_path

    @staticmethod
    def _write_wav_atomic(path: Path, samples: np.ndarray, sample_rate: int) -> None:
        temp_path = path.with_suffix(path.suffix + ".partial")
        pcm = np.clip(samples, -1.0, 1.0)
        pcm16 = (pcm * 32767.0).astype("<i2")
        try:
            with wave.open(str(temp_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(pcm16.tobytes())
            temp_path.replace(path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
