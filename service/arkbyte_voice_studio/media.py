from __future__ import annotations

import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Callable

from .config import ALLOWED_MEDIA_EXTENSIONS, MAX_IMPORT_BYTES, ensure_app_dirs, safe_stem
from .errors import AppError

Progress = Callable[[str], None]


def find_executable(name: str) -> str | None:
    """Find media tools, preferring the copy bundled beside a packaged app.

    The MSIX/PyInstaller build places FFmpeg under:
    <application folder>/Media Tools/FFmpeg/Bin. Direct NSIS installations
    continue to work through PATH, which their launcher configures.
    """
    executable_names = [name]
    if sys.platform == "win32" and not name.lower().endswith(".exe"):
        executable_names.insert(0, f"{name}.exe")

    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
        bundled_bin = app_dir / "Media Tools" / "FFmpeg" / "Bin"
        for executable_name in executable_names:
            candidate = bundled_bin / executable_name
            if candidate.is_file():
                return str(candidate)

    return shutil.which(name)


def validate_media(path: Path) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise AppError("The selected media file does not exist.", "MEDIA_MISSING") from exc
    if not resolved.is_file():
        raise AppError("Please select a file, not a folder.", "MEDIA_NOT_FILE")
    if resolved.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
        raise AppError("This file type is not supported. Use MP4, MOV, MKV, AVI, WEBM, WAV, MP3, M4A, FLAC, AAC or OGG.", "MEDIA_TYPE")
    if resolved.stat().st_size > MAX_IMPORT_BYTES:
        raise AppError("The selected file exceeds the 10 GB import limit.", "MEDIA_TOO_LARGE")
    if resolved.stat().st_size == 0:
        raise AppError("The selected file is empty.", "MEDIA_EMPTY")
    return resolved


def probe_media(path: Path, timeout: int = 20) -> dict:
    ffprobe = find_executable("ffprobe")
    if not ffprobe:
        raise AppError("FFprobe was not found. Install FFmpeg and make sure its bin folder is on PATH.", "FFPROBE_MISSING")
    path = validate_media(path)
    cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,sample_rate,channels", "-of", "json", str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AppError("Media inspection timed out. Try a smaller file.", "PROBE_TIMEOUT") from exc
    if result.returncode != 0:
        raise AppError("FFprobe could not read this file. The media may be damaged or use an unsupported codec.", "PROBE_FAILED")
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise AppError("FFprobe returned invalid media information.", "PROBE_INVALID") from exc


def extract_reference(source: Path, destination: Path, start_seconds: float = 0.0,
                      duration_seconds: float = 12.0, denoise: bool = False,
                      progress: Progress | None = None) -> Path:
    source = validate_media(source)
    if not find_executable("ffmpeg"):
        raise AppError("FFmpeg was not found. Run the setup script or install FFmpeg, then restart the app.", "FFMPEG_MISSING")
    if start_seconds < 0 or start_seconds > 24 * 60 * 60:
        raise AppError("Start time must be between 0 and 86400 seconds.", "START_TIME_INVALID")
    if duration_seconds < 5 or duration_seconds > 30:
        raise AppError("Reference duration must be between 5 and 30 seconds.", "DURATION_INVALID")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(".partial.wav")
    filters = ["highpass=f=70", "lowpass=f=11000"]
    if denoise:
        filters.append("afftdn=nf=-25")
    filters.append("loudnorm=I=-20:TP=-2:LRA=7")
    cmd = [find_executable("ffmpeg") or "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{start_seconds:.3f}", "-i", str(source), "-vn", "-t", f"{duration_seconds:.3f}",
           "-ac", "1", "-ar", "24000", "-af", ",".join(filters), "-c:a", "pcm_s16le", str(temp_path)]
    if progress:
        progress("Extracting and normalizing a reference voice clip…")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as exc:
        temp_path.unlink(missing_ok=True)
        raise AppError("Audio extraction timed out. Try a shorter reference segment.", "EXTRACT_TIMEOUT") from exc
    if result.returncode != 0 or not temp_path.exists():
        temp_path.unlink(missing_ok=True)
        raise AppError("Could not extract audio. Check that the selected segment contains an audio track.", "EXTRACT_FAILED")
    try:
        with wave.open(str(temp_path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            duration = frames / float(rate or 1)
            if wav.getnchannels() != 1 or rate != 24000 or duration < 3:
                raise AppError("The extracted audio is too short or has an unexpected format. Choose a segment with clear speech.", "REFERENCE_INVALID")
    except (wave.Error, OSError) as exc:
        temp_path.unlink(missing_ok=True)
        raise AppError("The extracted reference audio is invalid.", "REFERENCE_INVALID") from exc
    temp_path.replace(destination)
    return destination


def export_mp3(wav_path: Path, mp3_path: Path, bitrate: str = "192k") -> Path:
    ffmpeg = find_executable("ffmpeg")
    if not ffmpeg:
        raise AppError("FFmpeg is required to export MP3. Your WAV export is still available.", "FFMPEG_MISSING")
    temp_path = mp3_path.with_suffix(".partial.mp3")
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", bitrate, str(temp_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as exc:
        temp_path.unlink(missing_ok=True)
        raise AppError("MP3 conversion timed out. The WAV file remains available.", "MP3_TIMEOUT") from exc
    if result.returncode != 0 or not temp_path.exists():
        temp_path.unlink(missing_ok=True)
        raise AppError("MP3 conversion failed. The WAV file remains available.", "MP3_FAILED")
    temp_path.replace(mp3_path)
    return mp3_path


def extract_model_reference(source: Path, destination: Path, start_seconds: float = 0.0,
                            duration_seconds: float = 20.0, progress: Progress | None = None) -> Path:
    """Create a model-ready mono 24 kHz reference without denoising or loudness shaping.

    The original recording is retained separately. Only resampling/channel mixing
    is applied here so that EQ, noise reduction and normalization cannot silently
    become part of the speaker's permanent source of truth.
    """
    source = validate_media(source)
    ffmpeg = find_executable("ffmpeg")
    if not ffmpeg:
        raise AppError("FFmpeg was not found. Install FFmpeg and restart ArkByte.", "FFMPEG_MISSING")
    if start_seconds < 0 or duration_seconds < 5 or duration_seconds > 30:
        raise AppError("Reference segment must be 5–30 seconds and start at zero or later.", "REFERENCE_RANGE_INVALID")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(".partial.wav")
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start_seconds:.3f}",
           "-i", str(source), "-vn", "-t", f"{duration_seconds:.3f}", "-ac", "1", "-ar", "24000",
           "-c:a", "pcm_s16le", str(temp_path)]
    if progress:
        progress("Creating an unprocessed model-ready reference; original recording remains unchanged…")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as exc:
        temp_path.unlink(missing_ok=True)
        raise AppError("Reference preparation timed out.", "REFERENCE_TIMEOUT") from exc
    if result.returncode != 0 or not temp_path.exists():
        temp_path.unlink(missing_ok=True)
        raise AppError("Could not prepare the model reference from this recording.", "REFERENCE_PREPARE_FAILED")
    try:
        with wave.open(str(temp_path), "rb") as wav:
            actual_duration = wav.getnframes() / float(wav.getframerate() or 1)
            if wav.getnchannels() != 1 or wav.getframerate() != 24000 or actual_duration < 4.5:
                raise AppError("The prepared reference is too short or has an invalid audio format.", "REFERENCE_INVALID")
    except (wave.Error, OSError) as exc:
        temp_path.unlink(missing_ok=True)
        raise AppError("The prepared reference audio is invalid.", "REFERENCE_INVALID") from exc
    temp_path.replace(destination)
    return destination
