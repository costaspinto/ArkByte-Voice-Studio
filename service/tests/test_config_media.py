import tempfile
import unittest
from pathlib import Path

from arkbyte_voice_studio.config import ensure_within, safe_stem
from arkbyte_voice_studio.errors import AppError
from arkbyte_voice_studio.media import validate_media


class ConfigAndMediaTests(unittest.TestCase):
    def test_safe_stem_removes_path_characters(self):
        value = safe_stem("../my voice: <test>")
        self.assertNotIn("/", value)
        self.assertNotIn("\\", value)
        self.assertLessEqual(len(value), 64)

    def test_ensure_within_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base"
            base.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            with self.assertRaises(ValueError):
                ensure_within(base, outside)

    def test_validate_media_checks_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "video.exe"
            file.write_bytes(b"test")
            with self.assertRaises(AppError):
                validate_media(file)

    def test_validate_media_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "voice.wav"
            file.write_bytes(b"")
            with self.assertRaises(AppError):
                validate_media(file)


if __name__ == "__main__":
    unittest.main()
