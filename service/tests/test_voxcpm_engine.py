from __future__ import annotations

import logging
import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from arkbyte_voice_studio.voxcpm_engine import VoxCPM2Engine


class FakeVoxModel:
    class TTS:
        sample_rate = 24000
    tts_model = TTS()

    def __init__(self):
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return np.full(2400, 0.08, dtype=np.float32)


class FakeVoxCPM:
    model = FakeVoxModel()

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        return cls.model


class VoxCPMEngineTests(unittest.TestCase):
    def test_reference_only_and_transcript_conditioned_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "ref.wav"
            with wave.open(str(reference), "wb") as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
                wav.writeframes(np.zeros(2400, dtype="<i2").tobytes())
            fake_module = types.ModuleType("voxcpm")
            fake_module.VoxCPM = FakeVoxCPM
            output = root / "generated.wav"
            engine = VoxCPM2Engine(logging.getLogger("test"))
            FakeVoxCPM.model.calls.clear()
            with patch.object(VoxCPM2Engine, "is_installed", return_value=True), patch.dict(sys.modules, {"voxcpm": fake_module}):
                engine.generate("Hello there.", reference, output, "Hello there.")
            self.assertTrue(output.is_file())
            self.assertEqual(FakeVoxCPM.model.calls[0]["prompt_text"], "Hello there.")
            self.assertEqual(FakeVoxCPM.model.calls[0]["prompt_wav_path"], str(reference))
            self.assertEqual(FakeVoxCPM.model.calls[0]["reference_wav_path"], str(reference))
            with wave.open(str(output), "rb") as wav:
                self.assertEqual(wav.getframerate(), 24000)

    def test_missing_reference_is_rejected_before_model_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = VoxCPM2Engine(logging.getLogger("test"))
            with self.assertRaises(Exception) as caught:
                engine.generate("Hello", Path(tmp) / "missing.wav", Path(tmp) / "out.wav")
            self.assertEqual(getattr(caught.exception, "code", None), "PROFILE_AUDIO_MISSING")


if __name__ == "__main__":
    unittest.main()
