import logging
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from arkbyte_voice_studio.engine import ChatterboxEngine


class FakeModel:
    sr = 24000

    def generate(self, text, **kwargs):
        # Deterministic short signal to validate the output path without downloading AI weights.
        return np.full(2400, 0.05, dtype=np.float32)


class EngineTests(unittest.TestCase):
    def test_generate_writes_valid_wav_from_loaded_local_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref = root / "reference.wav"
            with wave.open(str(ref), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes((np.zeros(2400, dtype="<i2")).tobytes())
            output = root / "output.wav"
            engine = ChatterboxEngine(logging.getLogger("test"))
            engine._model = FakeModel()
            engine._device = "cpu"
            engine._loaded = True
            engine.generate("A short test sentence. " * 20, ref, "en", output)
            self.assertTrue(output.exists())
            with wave.open(str(output), "rb") as wav:
                self.assertEqual(wav.getframerate(), 24000)
                self.assertEqual(wav.getnchannels(), 1)
                self.assertGreater(wav.getnframes(), 2400)


if __name__ == "__main__":
    unittest.main()
