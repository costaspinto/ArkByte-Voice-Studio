from __future__ import annotations

import re

from .config import MAX_CHUNK_CHARS, MAX_SCRIPT_CHARS
from .errors import AppError


def validate_script(text: str) -> str:
    cleaned = (text or "").replace("\x00", "").strip()
    if not cleaned:
        raise AppError("Paste or type a script before generating audio.", "SCRIPT_EMPTY")
    if len(cleaned) > MAX_SCRIPT_CHARS:
        raise AppError(f"The script is too long. The current limit is {MAX_SCRIPT_CHARS:,} characters.", "SCRIPT_TOO_LONG")
    if not any(ch.isalnum() for ch in cleaned):
        raise AppError("The script must contain readable text.", "SCRIPT_INVALID")
    return cleaned


def split_script(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text on paragraph/sentence boundaries without dropping characters."""
    text = validate_script(text)
    max_chars = max(80, min(int(max_chars), 1000))
    # Preserve paragraph-level boundaries first, then sentence boundaries.
    sentences: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        pieces = re.split(r"(?<=[.!?।])\s+", paragraph)
        sentences.extend(piece.strip() for piece in pieces if piece.strip())

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            words = sentence.split()
            fragment = ""
            for word in words:
                candidate = f"{fragment} {word}".strip()
                if len(candidate) > max_chars and fragment:
                    if current:
                        chunks.append(current)
                        current = ""
                    chunks.append(fragment)
                    fragment = word
                else:
                    fragment = candidate
            if fragment:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(fragment)
            continue
        candidate = f"{current} {sentence}".strip()
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def pause_after_chunk_seconds(text: str) -> float:
    """Choose a small pause from sentence punctuation instead of fixed padding.

    This is a deterministic stitching cue, not learned speaker prosody.
    Paragraph-level pauses and speaker-specific rhythm require richer alignment.
    """
    ending = (text or "").rstrip()[-1:]
    if ending in {",", ";", ":"}:
        return 0.11
    if ending in {"?", "!", "؟", "！", "？"}:
        return 0.28
    if ending in {".", "।", "。"}:
        return 0.22
    return 0.17
