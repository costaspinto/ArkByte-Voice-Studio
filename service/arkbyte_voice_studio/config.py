from __future__ import annotations

import os
import re
import sys
from pathlib import Path

APP_NAME = "ArkByte Voice Studio"
MAX_IMPORT_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB per file
MAX_SCRIPT_CHARS = 50_000
MAX_CHUNK_CHARS = 280
ALLOWED_MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"}
SUPPORTED_LANGUAGES = {
    "English": "en", "Hindi": "hi", "Portuguese": "pt", "Spanish": "es",
    "French": "fr", "German": "de", "Italian": "it", "Japanese": "ja",
    "Korean": "ko", "Chinese": "zh", "Arabic": "ar", "Russian": "ru",
    "Dutch": "nl", "Polish": "pl", "Turkish": "tr", "Danish": "da",
    "Greek": "el", "Finnish": "fi", "Hebrew": "he", "Malay": "ms",
    "Norwegian": "no", "Swahili": "sw", "Swedish": "sv",
}


def app_data_dir() -> Path:
    override = os.environ.get("ARKBYTE_VOICE_HOME")
    if override:
        base = Path(override).expanduser()
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def ensure_app_dirs() -> dict[str, Path]:
    root = app_data_dir()
    paths = {
        "root": root,
        "profiles": root / "profiles",
        "imports": root / "imports",
        "outputs": root / "outputs",
        "logs": root / "logs",
        "cache": root / "cache",
        "temp": root / "temp",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def safe_stem(value: str, fallback: str = "item") -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", value or "")
    value = re.sub(r"[\s.]+", "_", value.strip(" ._"))
    value = value[:64].strip("._")
    return value or fallback


def ensure_within(base: Path, candidate: Path) -> Path:
    base_resolved = base.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError("The selected path is outside the allowed application folder.") from exc
    return candidate_resolved
