import math
import shutil
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from arkbyte_voice_studio.media import export_mp3, extract_reference


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe not installed")
class FFmpegIntegrationTests(unittest.TestCase):
    def test_reference_extraction_and_mp3_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.wav"
            with wave.open(str(source), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                frames = bytearray()
                for index in range(24000 * 6):
                    sample = int(7000 * math.sin(2 * math.pi * 220 * index / 24000))
                    frames.extend(struct.pack("<h", sample))
                wav.writeframes(frames)
            reference = extract_reference(source, root / "reference.wav", 0, 6, False)
            mp3 = export_mp3(reference, root / "reference.mp3")
            self.assertGreater(reference.stat().st_size, 1000)
            self.assertGreater(mp3.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
