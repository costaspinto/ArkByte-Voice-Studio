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


    def test_voxcpm05_requires_reference_and_exact_transcript(self):
        from arkbyte_voice_studio.voxcpm_engine import VoxCPM05Engine
        with tempfile.TemporaryDirectory() as tmp:
            engine = VoxCPM05Engine(logging.getLogger("test"))
            missing = Path(tmp) / "missing.wav"
            with self.assertRaises(Exception) as caught:
                engine.generate("Hello", missing, Path(tmp) / "out.wav", "Hello")
            self.assertEqual(getattr(caught.exception, "code", None), "PROFILE_AUDIO_MISSING")
            reference = Path(tmp) / "reference.wav"
            reference.write_bytes(b"not decoded by fake model")
            with self.assertRaises(Exception) as caught:
                engine.generate("Hello", reference, Path(tmp) / "out.wav", "  ")
            self.assertEqual(getattr(caught.exception, "code", None), "VOXCPM05_TRANSCRIPT_REQUIRED")

    def test_voxcpm05_adapter_uses_reference_and_verified_prompt_text(self):
        import sys
        import types
        from unittest.mock import patch
        from arkbyte_voice_studio.voxcpm_engine import VoxCPM05Engine

        class FakeModel:
            def __init__(self):
                self.calls = []
                self.tts_model = types.SimpleNamespace(sample_rate=16000)
            def generate(self, **kwargs):
                self.calls.append(kwargs)
                return np.zeros(16000, dtype=np.float32)

        class FakeVoxCPM:
            model = FakeModel()
            @classmethod
            def from_pretrained(cls, *args, **kwargs):
                cls.load_args = (args, kwargs)
                return cls.model

        fake_module = types.SimpleNamespace(VoxCPM=FakeVoxCPM)
        with tempfile.TemporaryDirectory() as tmp:
            reference = Path(tmp) / "reference.wav"
            reference.write_bytes(b"placeholder")
            output = Path(tmp) / "out.wav"
            engine = VoxCPM05Engine(logging.getLogger("test"))
            with patch.object(VoxCPM05Engine, "is_installed", return_value=True), patch.dict(sys.modules, {"voxcpm": fake_module}):
                engine.generate("Generated sentence.", reference, output, "Exact prompt transcript.")
            self.assertTrue(output.is_file())
            self.assertEqual(FakeVoxCPM.load_args[0], ("openbmb/VoxCPM-0.5B",))
            self.assertFalse(FakeVoxCPM.load_args[1]["optimize"])
            self.assertEqual(FakeVoxCPM.model.calls[0]["prompt_text"], "Exact prompt transcript.")
            self.assertEqual(FakeVoxCPM.model.calls[0]["prompt_wav_path"], str(reference))
            with wave.open(str(output), "rb") as wav:
                self.assertEqual(wav.getframerate(), 16000)


if __name__ == "__main__":
    unittest.main()
