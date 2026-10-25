from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from arkbyte_voice_studio.errors import AppError
from arkbyte_voice_studio.transcription import FasterWhisperTranscriber


class FakeWhisperModel:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def transcribe(self, path, **kwargs):
        return iter([SimpleNamespace(text=" Hello there."), SimpleNamespace(text=" This is a test.")]), SimpleNamespace(language="en", language_probability=0.99)


class TranscriptionTests(unittest.TestCase):
    def test_transcriber_lazily_loads_and_returns_reviewable_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "sample.wav"
            audio.write_bytes(b"fake audio")
            instances = []

            def factory(*args, **kwargs):
                obj = FakeWhisperModel(*args, **kwargs)
                instances.append(obj)
                return obj

            transcriber = FasterWhisperTranscriber(Path(tmp) / "cache", logging.getLogger("test"), factory)
            self.assertFalse(transcriber.status()["loaded"])
            result = transcriber.transcribe(audio, "en")
            self.assertEqual(result["transcript"], "Hello there. This is a test.")
            self.assertEqual(result["detected_language"], "en")
            self.assertTrue(result["review_required"])
            self.assertEqual(len(instances), 1)
            self.assertTrue(transcriber.status()["loaded"])

    def test_missing_optional_dependency_returns_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "sample.wav"
            audio.write_bytes(b"fake audio")
            transcriber = FasterWhisperTranscriber(Path(tmp) / "cache", logging.getLogger("test"))
            with patch("arkbyte_voice_studio.transcription.importlib.util.find_spec", return_value=None):
                with self.assertRaises(AppError) as caught:
                    transcriber.transcribe(audio, "en")
            self.assertEqual(caught.exception.code, "TRANSCRIPTION_NOT_INSTALLED")

    def test_missing_audio_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcriber = FasterWhisperTranscriber(Path(tmp) / "cache", logging.getLogger("test"), FakeWhisperModel)
            with self.assertRaises(AppError) as caught:
                transcriber.transcribe(Path(tmp) / "absent.wav")
            self.assertEqual(caught.exception.code, "TRANSCRIPTION_AUDIO_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
