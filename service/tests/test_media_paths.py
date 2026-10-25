import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arkbyte_voice_studio.media import find_executable


class BundledMediaPathTests(unittest.TestCase):
    def test_packaged_windows_app_prefers_bundled_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            bin_dir = app_dir / "Media Tools" / "FFmpeg" / "Bin"
            bin_dir.mkdir(parents=True)
            ffmpeg = bin_dir / "ffmpeg.exe"
            ffmpeg.write_bytes(b"test executable placeholder")

            with patch.object(sys, "platform", "win32"), \
                 patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(app_dir / "ArkByte Voice Studio.exe")), \
                 patch("arkbyte_voice_studio.media.shutil.which", return_value="PATH_FFMPEG"):
                self.assertEqual(find_executable("ffmpeg"), str(ffmpeg))

    def test_packaged_windows_app_falls_back_to_path_when_bundle_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            with patch.object(sys, "platform", "win32"), \
                 patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(app_dir / "ArkByte Voice Studio.exe")), \
                 patch("arkbyte_voice_studio.media.shutil.which", return_value="PATH_FFPROBE"):
                self.assertEqual(find_executable("ffprobe"), "PATH_FFPROBE")


if __name__ == "__main__":
    unittest.main()
