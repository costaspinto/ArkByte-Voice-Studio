from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from .errors import AppError
from .media import find_executable, probe_media, validate_media


def _db(value: float) -> float:
    return round(20.0 * math.log10(max(value, 1e-8)), 2)


def _pitch_estimates(samples: np.ndarray, sample_rate: int) -> list[float]:
    """Lightweight autocorrelation F0 estimate; diagnostic only, not ASR/identity."""
    frame_len = int(sample_rate * 0.032)
    hop = int(sample_rate * 0.064)
    min_lag = max(1, int(sample_rate / 350))
    max_lag = int(sample_rate / 70)
    estimates: list[float] = []
    if len(samples) < frame_len:
        return estimates
    for start in range(0, len(samples) - frame_len + 1, hop):
        frame = samples[start:start + frame_len].astype(np.float64)
        frame -= frame.mean()
        rms = float(np.sqrt(np.mean(frame * frame)))
        if rms < 0.012:
            continue
        frame *= np.hanning(len(frame))
        corr = np.correlate(frame, frame, mode="full")[len(frame) - 1:]
        if corr[0] <= 1e-10:
            continue
        corr /= corr[0]
        upper = min(max_lag, len(corr) - 1)
        if upper <= min_lag:
            continue
        section = corr[min_lag:upper + 1]
        lag = int(np.argmax(section)) + min_lag
        strength = float(corr[lag])
        if strength >= 0.28:
            hz = sample_rate / lag
            if 70 <= hz <= 350:
                estimates.append(float(hz))
    return estimates


def analyze_audio_file(path: Path) -> dict[str, Any]:
    """Inspect speech audio without altering the retained source recording.

    Metrics are recording-quality/acoustic descriptors. They are not an accent
    classifier or a neural speaker-identity score.
    """
    source = validate_media(path)
    info = probe_media(source)
    streams = info.get("streams", [])
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not audio_streams:
        raise AppError("This file does not contain an audio track.", "AUDIO_TRACK_MISSING")
    try:
        duration = float(info.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration < 5.0:
        raise AppError("Each enrolment recording must contain at least five seconds of audio.", "SAMPLE_TOO_SHORT")
    if duration > 900:
        raise AppError("Each enrolment recording must be 15 minutes or shorter. Split longer recordings first.", "SAMPLE_TOO_LONG")

    ffmpeg = find_executable("ffmpeg")
    if not ffmpeg:
        raise AppError("FFmpeg is required to analyse voice recordings. Install FFmpeg and restart ArkByte.", "FFMPEG_MISSING")
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1",
    ]
    try:
        result = subprocess.run(command, capture_output=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AppError("Audio analysis timed out. Try a shorter recording.", "AUDIO_ANALYSIS_TIMEOUT") from exc
    if result.returncode != 0 or not result.stdout:
        raise AppError("FFmpeg could not decode this recording. Try a standard WAV, MP3 or M4A file.", "AUDIO_DECODE_FAILED")

    samples = np.frombuffer(result.stdout, dtype="<f4").astype(np.float32)
    if samples.size < 16000 or not np.isfinite(samples).all():
        raise AppError("The decoded recording is empty or invalid.", "AUDIO_DECODE_INVALID")
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    clipping = float(np.mean(np.abs(samples) >= 0.999))
    frame_size = 320  # 20 ms at 16 kHz
    usable = samples[: (len(samples) // frame_size) * frame_size]
    frames = usable.reshape(-1, frame_size)
    frame_rms = np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1))
    active_threshold = max(0.008, rms * 0.16)
    active = frame_rms >= active_threshold
    silence_ratio = float(1.0 - np.mean(active)) if len(active) else 1.0
    active_ratio = 1.0 - silence_ratio
    pitch = _pitch_estimates(samples, 16000)

    # Mean spectral centroid over selected active frames. Used only as an
    # acoustic comparison proxy; it is sensitive to microphone and room setup.
    centroids: list[float] = []
    selected = np.flatnonzero(active)
    for idx in selected[:: max(1, len(selected) // 120 or 1)][:120]:
        frame = frames[int(idx)].astype(np.float64)
        spectrum = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
        total = float(spectrum.sum())
        if total > 1e-8:
            frequencies = np.fft.rfftfreq(len(frame), 1 / 16000)
            centroids.append(float(np.sum(frequencies * spectrum) / total))

    rms_db = _db(rms)
    # Heuristic quality score: adequate length, useful speech occupancy,
    # non-clipped signal and sensible level. This is not a quality truth score.
    duration_score = min(1.0, duration / 30.0)
    level_score = max(0.0, min(1.0, (rms_db + 48.0) / 32.0))
    speech_score = max(0.0, min(1.0, (active_ratio - 0.12) / 0.68))
    clipping_score = max(0.0, 1.0 - min(1.0, clipping * 250.0))
    quality = 100.0 * (0.15 * duration_score + 0.25 * level_score + 0.30 * speech_score + 0.30 * clipping_score)

    return {
        "duration_seconds": round(duration, 2),
        "sample_rate": int(audio_streams[0].get("sample_rate") or 0),
        "channels": int(audio_streams[0].get("channels") or 0),
        "analysis_sample_rate": 16000,
        "rms_dbfs": rms_db,
        "peak_dbfs": _db(peak),
        "clipping_ratio": round(clipping, 6),
        "silence_ratio": round(silence_ratio, 4),
        "active_speech_ratio": round(active_ratio, 4),
        "pitch_median_hz": round(float(np.median(pitch)), 2) if pitch else None,
        "pitch_p10_hz": round(float(np.percentile(pitch, 10)), 2) if pitch else None,
        "pitch_p90_hz": round(float(np.percentile(pitch, 90)), 2) if pitch else None,
        "spectral_centroid_hz": round(float(np.median(centroids)), 2) if centroids else None,
        "quality_score": round(float(quality), 1),
        "quality_grade": "good" if quality >= 72 else "review" if quality >= 52 else "poor",
        "warnings": _warnings(duration, rms_db, clipping, silence_ratio),
        "metric_note": "Quality and acoustic descriptors only; not accent recognition or speaker-identity verification.",
    }


def _warnings(duration: float, rms_db: float, clipping: float, silence_ratio: float) -> list[str]:
    warnings: list[str] = []
    if duration < 12:
        warnings.append("Short sample: record at least 20–60 seconds for a richer voice reference.")
    if rms_db < -38:
        warnings.append("Low recording level: move closer to the microphone or increase recording gain without clipping.")
    if rms_db > -12:
        warnings.append("Very loud recording: check for microphone overload and distortion.")
    if clipping > 0.002:
        warnings.append("Clipping detected: reduce microphone input gain and record again.")
    if silence_ratio > 0.55:
        warnings.append("High silence ratio: trim long pauses or record more continuous speech.")
    return warnings


def aggregate_profile(
    samples: list[dict[str, Any]], accent_notes: str, pronunciation_notes: str,
    transcript_count: int | None = None,
) -> dict[str, Any]:
    def median(key: str):
        values = [float(item[key]) for item in samples if item.get(key) is not None]
        return round(float(np.median(values)), 2) if values else None

    grades = [float(item.get("quality_score", 0)) for item in samples]
    total_duration = round(sum(float(item.get("duration_seconds", 0)) for item in samples), 2)
    transcript_count = max(0, min(len(samples), int(transcript_count or 0)))
    return {
        "sample_count": len(samples),
        "target_sample_count": 10,
        "enrollment_completion": round(min(100, len(samples) / 10 * 100), 1),
        "total_recording_seconds": total_duration,
        "median_quality_score": round(float(np.median(grades)), 1) if grades else 0,
        "median_pitch_hz": median("pitch_median_hz"),
        "median_rms_dbfs": median("rms_dbfs"),
        "median_spectral_centroid_hz": median("spectral_centroid_hz"),
        "median_active_speech_ratio": median("active_speech_ratio"),
        "accent_notes": accent_notes.strip(),
        "pronunciation_notes": pronunciation_notes.strip(),
        "accent_classification": "Not automatically classified. Use speaker-confirmed accent notes and pronunciation examples.",
        "identity_embedding": {"status": "optional_ecapa", "note": "ECAPA-TDNN comparison is available as an optional SpeechBrain adapter; run it from Benchmark Studio after installing its package and loading weights."},
        "pipeline_stages": [
            {"id": "consent", "name": "Consent and intake", "status": "confirmed", "detail": "Profile creation required an ownership/permission confirmation."},
            {"id": "audio_quality", "name": "Audio quality analysis", "status": "complete", "detail": "Duration, signal level, clipping, silence, pitch and spectral descriptors calculated."},
            {"id": "transcription", "name": "Transcript coverage", "status": "complete" if transcript_count == len(samples) and samples else "needs_review", "detail": f"{transcript_count} of {len(samples)} recordings have transcripts explicitly reviewed and saved. Auto-generated drafts do not count until the user reviews and saves them."},
            {"id": "speaker_identity", "name": "Neural speaker identity", "status": "optional", "detail": "ECAPA-TDNN is an optional embedding comparison; no identity similarity is calculated during enrolment."},
            {"id": "accent", "name": "Accent and pronunciation", "status": "speaker_notes" if accent_notes.strip() else "needs_review", "detail": "Accent notes are speaker-confirmed. No automatic accent classification is claimed."},
            {"id": "prosody", "name": "Prosody and delivery", "status": "partial", "detail": "Basic pitch and activity descriptors are available; phoneme alignment and speaker-specific prosody modelling are not included."},
            {"id": "reference", "name": "Reference anchor", "status": "selected", "detail": "Highest heuristic recording-quality sample was selected; you can change the anchor manually."},
        ],
    }
