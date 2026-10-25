from __future__ import annotations

import io
import json
import math
import shutil
import struct
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path

from arkbyte_voice_studio.errors import AppError
from arkbyte_voice_studio.qwen_training_export import build_qwen_training_bundle


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg not installed")
class QwenTrainingExportTests(unittest.TestCase):
    def _wav(self, path: Path, seconds: int = 6):
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(24000)
            frames = bytearray()
            for i in range(24000 * seconds):
                value = int(5000 * math.sin(2 * math.pi * 180 * i / 24000))
                frames.extend(struct.pack("<h", value))
            stream.writeframes(frames)

    def test_training_bundle_contains_full_audio_and_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_id = "a" * 32
            profile_dir = root / profile_id
            sample_dir = profile_dir / "samples"; refs_dir = profile_dir / "references"
            sample_dir.mkdir(parents=True); refs_dir.mkdir()
            sample1 = sample_dir / "one.wav"; sample2 = sample_dir / "two.wav"
            reference = refs_dir / "anchor.wav"
            self._wav(sample1); self._wav(sample2); self._wav(reference)
            samples = [
                {"id": "1", "profile_id": profile_id, "source_name": "one.wav", "original_path": str(sample1),
                 "model_reference_path": str(reference), "transcript": "First exact transcript.", "transcript_reviewed": True, "is_anchor": True},
                {"id": "2", "profile_id": profile_id, "source_name": "two.wav", "original_path": str(sample2),
                 "model_reference_path": str(reference), "transcript": "Second exact transcript.", "transcript_reviewed": True, "is_anchor": False},
            ]
            bundle = build_qwen_training_bundle(profile_id, samples, root)
            with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
                self.assertIn("train_raw.jsonl", archive.namelist())
                rows = [json.loads(line) for line in archive.read("train_raw.jsonl").decode().splitlines()]
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["text"], "First exact transcript.")
                self.assertEqual(rows[1]["ref_audio"], "audio/ref.wav")
                self.assertTrue(archive.read("audio/utt001.wav").startswith(b"RIFF"))
                self.assertIn("official instructions", archive.read("README_TRAINING.md").decode().lower())

    def test_export_rejects_unreviewed_asr_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); profile_id = "c" * 32
            with self.assertRaises(AppError) as caught:
                build_qwen_training_bundle(profile_id, [{"source_name": "draft.wav", "transcript": "Draft text", "transcript_reviewed": False}], root)
            self.assertEqual(caught.exception.code, "TRAINING_TRANSCRIPTS_REVIEW_REQUIRED")

    def test_export_rejects_missing_transcripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); profile_id = "b" * 32
            with self.assertRaises(AppError) as caught:
                build_qwen_training_bundle(profile_id, [{"source_name": "missing.wav", "transcript": ""}], root)
            self.assertEqual(caught.exception.code, "TRAINING_TRANSCRIPTS_REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
