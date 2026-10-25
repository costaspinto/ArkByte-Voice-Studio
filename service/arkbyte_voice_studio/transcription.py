from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
from typing import Any, Callable

from .errors import AppError


class FasterWhisperTranscriber:
    """Optional, lazy local ASR adapter. Model weights are fetched only on first use."""

    ALLOWED_MODELS = {"tiny", "base", "small", "medium", "large-v3"}

    def __init__(self, cache_dir: Path, logger: logging.Logger,
                 model_factory: Callable[..., Any] | None = None) -> None:
        self.cache_dir = cache_dir
        self.logger = logger
        configured = os.environ.get("ARKBYTE_WHISPER_MODEL", "small").strip().lower()
        self.model_size = configured if configured in self.ALLOWED_MODELS else "small"
        self._model_factory = model_factory
        self._model = None

    def status(self) -> dict[str, Any]:
        installed = self._model_factory is not None or importlib.util.find_spec("faster_whisper") is not None
        return {
            "id": "faster_whisper",
            "name": "Faster-Whisper local transcription",
            "installed": installed,
            "model_size": self.model_size,
            "loaded": self._model is not None,
            "status": "ready" if installed else "optional_dependency_missing",
            "first_use_download": self._model is None,
            "note": "Transcription is a draft. Review every word and punctuation mark before using it for speaker adaptation.",
        }

    def _load(self):
        if self._model is not None:
            return self._model
        factory = self._model_factory
        if factory is None:
            if importlib.util.find_spec("faster_whisper") is None:
                raise AppError(
                    "Local transcription is optional. Install service/requirements-transcription.txt, then restart ArkByte.",
                    "TRANSCRIPTION_NOT_INSTALLED",
                )
            try:
                from faster_whisper import WhisperModel
                factory = WhisperModel
            except Exception as exc:
                raise AppError("Faster-Whisper could not be imported. Check its CTranslate2 installation.",
                               "TRANSCRIPTION_IMPORT_FAILED") from exc
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = factory(
                self.model_size,
                device="auto",
                compute_type="default",
                download_root=str(self.cache_dir),
            )
            return self._model
        except Exception as exc:
            self.logger.exception("Could not load Faster-Whisper model")
            raise AppError(
                "The local transcription model could not load. Check available RAM/VRAM and model download access.",
                "TRANSCRIPTION_MODEL_LOAD_FAILED",
            ) from exc

    def transcribe(self, audio_path: Path, language: str | None = None) -> dict[str, Any]:
        if not audio_path.is_file():
            raise AppError("The original recording is unavailable.", "TRANSCRIPTION_AUDIO_NOT_FOUND")
        model = self._load()
        try:
            segments, info = model.transcribe(
                str(audio_path),
                language=language or None,
                beam_size=5,
                vad_filter=True,
                word_timestamps=False,
            )
            pieces = [str(segment.text).strip() for segment in segments if str(segment.text).strip()]
            transcript = " ".join(pieces).strip()
            if not transcript:
                raise AppError("No usable speech was detected. Check the recording or enter its transcript manually.",
                               "TRANSCRIPTION_EMPTY")
            return {
                "transcript": transcript[:20000],
                "detected_language": getattr(info, "language", None),
                "language_probability": round(float(getattr(info, "language_probability", 0.0)), 4),
                "model": self.model_size,
                "review_required": True,
            }
        except AppError:
            raise
        except Exception as exc:
            self.logger.exception("Local transcription failed for %s", audio_path.name)
            raise AppError("Local transcription failed. Check the audio codec and available memory.",
                           "TRANSCRIPTION_FAILED") from exc
