from __future__ import annotations

import math
import shutil
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from arkbyte_voice_studio.audio_analysis import analyze_audio_file


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe not installed")
class AudioAnalysisTests(unittest.TestCase):
    def _speech_like_wav(self, path: Path) -> None:
        rate = 24000
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(rate)
            data = bytearray()
            for index in range(rate * 7):
                t = index / rate
                envelope = 0.18 if 0.3 < (t % 1.4) < 1.25 else 0.0
                fundamental = 170 + 25 * math.sin(2 * math.pi * 0.4 * t)
                value = envelope * (math.sin(2 * math.pi * fundamental * t) + 0.18 * math.sin(2 * math.pi * 2 * fundamental * t))
                data.extend(struct.pack("<h", int(max(-1, min(1, value)) * 32767)))
            stream.writeframes(data)

    def test_audio_analysis_returns_quality_metrics_not_identity_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "sample.wav"
            self._speech_like_wav(audio)
            result = analyze_audio_file(audio)
            self.assertGreaterEqual(result["duration_seconds"], 6.9)
            self.assertIn(result["quality_grade"], {"good", "review", "poor"})
            self.assertGreaterEqual(result["quality_score"], 0)
            self.assertLessEqual(result["quality_score"], 100)
            self.assertIn("not accent recognition", result["metric_note"].lower())
            self.assertIn("pitch_median_hz", result)

    def test_audio_analysis_rejects_too_short_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "short.wav"
            with wave.open(str(audio), "wb") as stream:
                stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(24000)
                stream.writeframes(b"\x00\x00" * (24000 * 2))
            with self.assertRaises(Exception) as caught:
                analyze_audio_file(audio)
            self.assertEqual(getattr(caught.exception, "code", None), "SAMPLE_TOO_SHORT")


if __name__ == "__main__":
    unittest.main()
