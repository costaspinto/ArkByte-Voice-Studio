from __future__ import annotations

import asyncio
import hmac
import importlib.util
import json
import logging
import os
import re
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from arkbyte_voice_studio.config import (
    ALLOWED_MEDIA_EXTENSIONS,
    MAX_IMPORT_BYTES,
    SUPPORTED_LANGUAGES,
    ensure_app_dirs,
    ensure_within,
    safe_stem,
)
from arkbyte_voice_studio.errors import AppError
from arkbyte_voice_studio.logging_setup import configure_logging
from arkbyte_voice_studio.media import find_executable
from arkbyte_voice_studio.services import VoiceStudioService
from arkbyte_voice_studio.storage import Storage

APP_VERSION = "1.2.0"
DATA_PATHS = ensure_app_dirs()
LOGGER = configure_logging()
STORAGE = Storage(DATA_PATHS["root"] / "arkbyte_voice_studio.db")
STUDIO = VoiceStudioService(STORAGE, LOGGER)
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.RLock()
GENERATOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="arkbyte-generation")

app = FastAPI(
    title="ArkByte Voice Studio Local Bridge",
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class ProjectRequest(BaseModel):
    id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    title: str = Field(min_length=1, max_length=100)
    script: str = Field(min_length=1, max_length=50_000)
    profile_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    language_id: str = Field(min_length=2, max_length=8)
    output_name: str = Field(default="narration", min_length=1, max_length=100)
    exaggeration: float = Field(default=0.5, ge=0.25, le=2.0)
    cfg_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    temperature: float = Field(default=0.8, ge=0.05, le=2.0)
    model_id: str = Field(default="chatterbox", pattern=r"^(chatterbox|voxcpm05|voxcpm2)$")


class GenerateRequest(BaseModel):
    profile_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    script: str = Field(min_length=1, max_length=50_000)
    language_id: str = Field(min_length=2, max_length=8)
    output_name: str = Field(default="narration", min_length=1, max_length=100)
    exaggeration: float = Field(default=0.5, ge=0.25, le=2.0)
    cfg_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    temperature: float = Field(default=0.8, ge=0.05, le=2.0)
    model_id: str = Field(default="chatterbox", pattern=r"^(chatterbox|voxcpm05|voxcpm2)$")
    rights_ack: bool = False


class TranscriptRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=20000)


class DeleteVoiceProfileRequest(BaseModel):
    confirmation_phrase: str = Field(min_length=1, max_length=32)


class PronunciationRequest(BaseModel):
    term: str = Field(min_length=1, max_length=100)
    say_as: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=500)


def require_local_auth(
    request: Request,
    x_arkbyte_token: str | None = Header(default=None),
) -> None:
    expected = os.environ.get("ARKBYTE_BRIDGE_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="The local bridge has not been configured. Run the setup script.")
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="The local bridge accepts loopback connections only.")
    if not x_arkbyte_token or not hmac.compare_digest(x_arkbyte_token, expected):
        raise HTTPException(status_code=401, detail="Local bridge authentication failed.")


def profile_public(item: dict[str, Any]) -> dict[str, Any]:
    try:
        samples = STORAGE.list_voice_samples(item["id"])
        meta = STORAGE.get_profile_analysis(item["id"])
        analysis = meta["analysis"] if meta else None
    except Exception:
        samples, analysis = [], None
    return {
        "id": item["id"],
        "name": item["name"],
        "language": item["language"],
        "source_name": item.get("source_name", "Imported recording"),
        "created_at": item.get("created_at"),
        "sample_count": len(samples),
        "enrollment_completion": analysis.get("enrollment_completion", 0) if analysis else 0,
        "quality_score": analysis.get("median_quality_score") if analysis else None,
        "accent_notes": (meta.get("accent_notes", "") if meta else ""),
    }


def project_public(item: dict[str, Any]) -> dict[str, Any]:
    """Return only user-facing project fields; never expose filesystem paths."""
    return {
        "id": item["id"],
        "title": item["title"],
        "script": item["script"],
        "profile_id": item.get("profile_id"),
        "language_id": item["language_id"],
        "output_name": item["output_name"],
        "exaggeration": float(item["exaggeration"]),
        "cfg_weight": float(item["cfg_weight"]),
        "temperature": float(item["temperature"]),
        "model_id": item.get("model_id", "chatterbox"),
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


def project_summary(item: dict[str, Any]) -> dict[str, Any]:
    """Compact list representation created from a summary-only database query."""
    return {
        "id": item["id"],
        "title": item["title"],
        "script_preview": " ".join(str(item.get("script_preview", "")).split())[:240],
        "character_count": int(item.get("character_count") or 0),
        "profile_id": item.get("profile_id"),
        "language_id": item["language_id"],
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


def history_public(item: dict[str, Any]) -> dict[str, Any]:
    audio_url = None
    try:
        path = ensure_within(DATA_PATHS["outputs"], Path(item["output_path"]))
        if path.is_file():
            audio_url = f"/api/v1/audio/{item['id']}"
    except Exception:
        LOGGER.warning("History item %s has an invalid output path", item.get("id"))
    return {
        "id": item["id"],
        "profile_id": item.get("profile_id"),
        "profile_name": item["profile_name"],
        "script_preview": item["script_preview"],
        "language": item["language"],
        "status": item["status"],
        "created_at": item["created_at"],
        "audio_url": audio_url,
    }


def update_job(job_id: str, **values: Any) -> None:
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(values)


def run_generation(job_id: str, payload: GenerateRequest) -> None:
    update_job(job_id, status="running", progress=0.03, message="Preparing the local voice engine…")

    def progress(message: str) -> None:
        current = 0.1
        match = re.search(r"paragraph\s+(\d+)\s+of\s+(\d+)", message, re.IGNORECASE)
        if match:
            current = min(0.9, 0.12 + (int(match.group(1)) / max(int(match.group(2)), 1)) * 0.76)
        elif "CPU" in message.upper():
            current = 0.12
        update_job(job_id, progress=current, message=message)

    try:
        output = STUDIO.generate(
            profile_id=payload.profile_id,
            script=payload.script,
            language_id=payload.language_id,
            output_name=payload.output_name,
            exaggeration=payload.exaggeration,
            cfg_weight=payload.cfg_weight,
            temperature=payload.temperature,
            progress=progress,
            model_id=payload.model_id,
        )
        latest = STORAGE.list_history(500)
        matching = next((item for item in latest if Path(item["output_path"]).resolve() == output.resolve()), None)
        update_job(
            job_id,
            status="complete",
            progress=1.0,
            message="Narration generated successfully.",
            history_id=matching["id"] if matching else None,
            audio_url=f"/api/v1/audio/{matching['id']}" if matching else None,
            device=STUDIO.last_device,
        )
        LOGGER.info("Web generation job %s completed", job_id)
    except AppError as exc:
        LOGGER.exception("Web generation job %s failed: %s", job_id, exc.code)
        update_job(job_id, status="failed", progress=0.0, message="Generation could not be completed.", error={"code": exc.code, "message": str(exc)})
    except Exception:
        LOGGER.exception("Unexpected web generation failure: %s", job_id)
        update_job(job_id, status="failed", progress=0.0, message="An unexpected local error occurred.", error={"code": "UNEXPECTED_GENERATION_ERROR", "message": "The generation process failed unexpectedly. Open the application log and retry with a shorter script."})


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    try:
        response = await call_next(request)
    except Exception:
        LOGGER.exception("Unhandled request error [%s] %s %s", request_id, request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "The local service encountered an unexpected error. Check the diagnostic log and retry."}},
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    messages = {
        401: ("AUTH_FAILED", "The local bridge could not authenticate this request."),
        403: ("LOCAL_ONLY", "This service is restricted to this computer."),
        404: ("NOT_FOUND", "The requested local resource was not found."),
    }
    code, fallback = messages.get(exc.status_code, ("HTTP_ERROR", str(exc.detail)))
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": {"code": code, "message": fallback}})


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=400, content={"ok": False, "error": {"code": exc.code, "message": str(exc)}})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(part) for part in first.get("loc", []) if part not in {"body", "query", "path"})
    message = f"A request value is invalid{f' ({field})' if field else ''}. Check the form and try again."
    return JSONResponse(status_code=422, content={"ok": False, "error": {"code": "VALIDATION_ERROR", "message": message}})


@app.get("/api/v1/health", dependencies=[Depends(require_local_auth)])
def health() -> dict[str, Any]:
    chatterbox_installed = importlib.util.find_spec("chatterbox") is not None
    torch_present = importlib.util.find_spec("torch") is not None
    torch_installed = False
    cuda = False
    gpu_vram_gb = None
    if torch_present:
        try:
            import torch
            torch_installed = True
            cuda = bool(torch.cuda.is_available())
            if cuda:
                properties = torch.cuda.get_device_properties(0)
                gpu_vram_gb = round(float(properties.total_memory) / (1024 ** 3), 2)
        except Exception as exc:
            LOGGER.warning("PyTorch import or hardware check failed: %s", exc)
    try:
        database_status = STORAGE.integrity_check()
    except Exception:
        LOGGER.exception("Database health check failed")
        database_status = "error"
    return {
        "ok": database_status == "ok",
        "app": "ArkByte Voice Studio",
        "version": APP_VERSION,
        "localOnly": True,
        "engine": {
            "installed": chatterbox_installed and torch_installed,
            "loaded": bool(STUDIO.engine._loaded),
            "device": STUDIO.engine.device,
            "torch": torch_installed,
            "cuda": cuda,
            "gpu_vram_gb": gpu_vram_gb,
        },
        "media": {"ffmpeg": bool(find_executable("ffmpeg")), "ffprobe": bool(find_executable("ffprobe"))},
        "database": {"status": database_status},
        "message": "Local inference only. No paid API is used.",
    }


@app.get("/api/v1/profiles", dependencies=[Depends(require_local_auth)])
def list_profiles() -> dict[str, Any]:
    return {"ok": True, "profiles": [profile_public(item) for item in STORAGE.list_profiles()]}


def _stage_voice_uploads(files: list[UploadFile], total_limit: int = 500 * 1024 * 1024) -> tuple[list[Path], list[str]]:
    if not 1 <= len(files) <= 10:
        raise AppError("Upload between 1 and 10 recordings at a time.", "ENROLLMENT_FILE_COUNT")
    staged: list[Path] = []
    names: list[str] = []
    total = 0
    try:
        for upload in files:
            original_name = (upload.filename or "recording.wav").replace("\\", "/").split("/")[-1]
            suffix = Path(original_name).suffix.lower()
            if suffix not in ALLOWED_MEDIA_EXTENSIONS:
                raise AppError(f"Unsupported recording type for {original_name}.", "MEDIA_TYPE")
            target_path = DATA_PATHS["imports"] / f"enroll_{uuid.uuid4().hex}{suffix}"
            staged.append(target_path)
            size = 0
            with target_path.open("xb") as target:
                while True:
                    chunk = upload.file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    total += len(chunk)
                    if size > 250 * 1024 * 1024:
                        raise AppError("Each recording must be 250 MB or smaller.", "SAMPLE_TOO_LARGE")
                    if total > total_limit:
                        raise AppError("The enrolment batch exceeds 500 MB. Upload fewer or smaller recordings.", "ENROLLMENT_TOO_LARGE")
                    target.write(chunk)
            if size == 0:
                raise AppError(f"{original_name} is empty.", "MEDIA_EMPTY")
            names.append(original_name)
        return staged, names
    except Exception:
        for path in staged:
            path.unlink(missing_ok=True)
        raise


@app.post("/api/v1/enrollments", dependencies=[Depends(require_local_auth)])
async def enroll_voice_profile(
    name: str = Form(..., min_length=1, max_length=80),
    language: str = Form(..., min_length=2, max_length=32),
    accent_notes: str = Form(default="", max_length=2000),
    pronunciation_notes: str = Form(default="", max_length=2000),
    transcripts_json: str = Form(default="[]", max_length=100000),
    consent_ack: bool = Form(...),
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    if language not in SUPPORTED_LANGUAGES and language not in SUPPORTED_LANGUAGES.values():
        raise AppError("Select a supported language for this voice profile.", "LANGUAGE_UNSUPPORTED")
    try:
        transcripts = json.loads(transcripts_json or "[]")
        if not isinstance(transcripts, list) or any(not isinstance(item, str) for item in transcripts):
            raise ValueError("Expected a list of transcript strings")
    except (json.JSONDecodeError, ValueError) as exc:
        raise AppError("Recording transcripts must be a JSON array of text values.", "TRANSCRIPTS_INVALID") from exc
    staged, names = _stage_voice_uploads(files)
    try:
        result = await run_in_threadpool(
            STUDIO.enroll_profile, name, language, staged, names, transcripts,
            consent_ack, accent_notes, pronunciation_notes,
        )
        return {"ok": True, "profile": profile_public(result), "analysis": result["analysis"]}
    finally:
        for path in staged:
            path.unlink(missing_ok=True)
        for upload in files:
            await upload.close()


@app.get("/api/v1/profiles/{profile_id}/detail", dependencies=[Depends(require_local_auth)])
def profile_detail(profile_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", profile_id or ""):
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"ok": True, **STUDIO.profile_detail(profile_id)}


@app.post("/api/v1/profiles/{profile_id}/samples", dependencies=[Depends(require_local_auth)])
async def add_profile_samples(
    profile_id: str,
    transcripts_json: str = Form(default="[]", max_length=100000),
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", profile_id or ""):
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        transcripts = json.loads(transcripts_json or "[]")
        if not isinstance(transcripts, list) or any(not isinstance(item, str) for item in transcripts):
            raise ValueError("Expected a list of transcript strings")
    except (json.JSONDecodeError, ValueError) as exc:
        raise AppError("Recording transcripts must be a JSON array of text values.", "TRANSCRIPTS_INVALID") from exc
    staged, names = _stage_voice_uploads(files)
    try:
        result = await run_in_threadpool(STUDIO.add_samples, profile_id, staged, names, transcripts)
        return {"ok": True, **result, "profile": profile_public(STORAGE.get_profile(profile_id))}
    finally:
        for path in staged:
            path.unlink(missing_ok=True)
        for upload in files:
            await upload.close()


@app.post("/api/v1/profiles/{profile_id}/samples/{sample_id}/transcribe", dependencies=[Depends(require_local_auth)])
def transcribe_profile_sample(profile_id: str, sample_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", profile_id or "") or not re.fullmatch(r"[a-f0-9]{32}", sample_id or ""):
        raise HTTPException(status_code=404, detail="Recording not found")
    return {"ok": True, **STUDIO.transcribe_sample(profile_id, sample_id)}


@app.put("/api/v1/profiles/{profile_id}/samples/{sample_id}/transcript", dependencies=[Depends(require_local_auth)])
def update_sample_transcript(profile_id: str, sample_id: str, payload: TranscriptRequest) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", profile_id or "") or not re.fullmatch(r"[a-f0-9]{32}", sample_id or ""):
        raise HTTPException(status_code=404, detail="Recording not found")
    STUDIO.update_sample_transcript(profile_id, sample_id, payload.transcript)
    return {"ok": True}


@app.get("/api/v1/profiles/{profile_id}/training-export/qwen3", dependencies=[Depends(require_local_auth)])
def export_qwen_training_bundle(profile_id: str) -> Response:
    if not re.fullmatch(r"[a-f0-9]{32}", profile_id or ""):
        raise HTTPException(status_code=404, detail="Profile not found")
    bundle = STUDIO.qwen_training_bundle(profile_id)
    profile = STORAGE.get_profile(profile_id)
    filename = f"ArkByte_Qwen3_Training_{safe_stem(profile['name'], 'Voice_Profile')}.zip"
    return Response(
        content=bundle,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@app.post("/api/v1/profiles/{profile_id}/anchor/{sample_id}", dependencies=[Depends(require_local_auth)])
def set_profile_anchor(profile_id: str, sample_id: str) -> dict[str, Any]:
    STUDIO.set_anchor(profile_id, sample_id)
    return {"ok": True}


@app.get("/api/v1/profile-samples/{sample_id}/audio", dependencies=[Depends(require_local_auth)])
def profile_sample_audio(sample_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}", sample_id or ""):
        raise HTTPException(status_code=404, detail="Recording not found")
    sample = STORAGE.get_voice_sample(sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Recording not found")
    profile_dir = ensure_within(DATA_PATHS["profiles"], DATA_PATHS["profiles"] / sample["profile_id"])
    path = ensure_within(profile_dir, Path(sample["original_path"]))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Original recording is unavailable")
    suffix = path.suffix.lower()
    media_type = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".flac": "audio/flac", ".ogg": "audio/ogg", ".aac": "audio/aac"}.get(suffix, "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=path.name, headers={"Cache-Control": "no-store"})


@app.get("/api/v1/profiles/{profile_id}/pronunciations", dependencies=[Depends(require_local_auth)])
def list_pronunciations(profile_id: str) -> dict[str, Any]:
    if not STORAGE.get_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"ok": True, "pronunciations": STORAGE.list_pronunciations(profile_id)}


@app.post("/api/v1/profiles/{profile_id}/pronunciations", dependencies=[Depends(require_local_auth)])
def add_pronunciation(profile_id: str, payload: PronunciationRequest) -> dict[str, Any]:
    entry = STUDIO.add_pronunciation(profile_id, payload.term, payload.say_as, payload.notes)
    return {"ok": True, "pronunciation": entry}


@app.delete("/api/v1/profiles/{profile_id}/pronunciations/{entry_id}", dependencies=[Depends(require_local_auth)])
def delete_pronunciation(profile_id: str, entry_id: str) -> dict[str, Any]:
    STORAGE.delete_pronunciation(profile_id, entry_id)
    return {"ok": True}


@app.get("/api/v1/models", dependencies=[Depends(require_local_auth)])
def model_registry() -> dict[str, Any]:
    identity = STUDIO.speaker_evaluator.status()
    voxcpm_installed = STUDIO.voxcpm.is_installed()
    candidates = [
        {"id": "chatterbox", "name": "Chatterbox Multilingual V3", "package": "chatterbox", "role": "Default multilingual reference-conditioned generation engine", "status": "installed" if importlib.util.find_spec("chatterbox") and importlib.util.find_spec("torch") else "not_installed", "integrated": True, "first_use_download": True},
        {"id": "voxcpm05", "name": "VoxCPM 0.5B", "package": "voxcpm", "role": "Smaller English/Chinese continuation-cloning engine; requires an exact reviewed reference transcript", "status": "installed" if voxcpm_installed else "not_installed", "integrated": True, "first_use_download": True, "requires_transcript": True, "recommended_vram_gb": 5, "hardware_note": "About 5 GB VRAM in the upstream reference table; 6 GB GPUs are tight. The service unloads the previous engine before switching."},
        {"id": "voxcpm2", "name": "VoxCPM 2 (2B)", "package": "voxcpm", "role": "Multilingual reference and transcript-conditioned cloning engine", "status": "installed" if voxcpm_installed else "not_installed", "integrated": True, "first_use_download": True, "recommended_vram_gb": 8, "hardware_note": "Upstream reports about 8 GB VRAM; 6 GB GPUs may not have enough memory."},
        {"id": "qwen3_tts", "name": "Qwen3-TTS", "package": "qwen_tts", "role": "Single-speaker Base-model fine-tuning dataset export; no in-app inference adapter", "status": "installed" if importlib.util.find_spec("qwen_tts") else "not_installed", "integrated": False},
    ]
    return {"ok": True, "models": candidates, "speaker_identity": identity, "transcription": STUDIO.transcriber.status(), "active_model": STUDIO.last_model, "note": "Chatterbox is the default engine. VoxCPM 0.5B and VoxCPM 2 use the optional VoxCPM package and download their model weights on first selection. VoxCPM 0.5B requires a reviewed transcript matching a reference clip of 30 seconds or less. VoxCPM 2 is a 2B model with an approximately 8 GB VRAM recommendation. Qwen3-TTS export is integrated; Qwen inference and fine-tuning are external workflows. ECAPA-TDNN and Faster-Whisper remain optional."}


@app.post("/api/v1/benchmarks/{history_id}/speaker-identity", dependencies=[Depends(require_local_auth)])
def benchmark_speaker_identity(history_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", history_id or ""):
        raise HTTPException(status_code=404, detail="Generation not found")
    return {"ok": True, "speaker_identity": STUDIO.speaker_identity_comparison(history_id)}


@app.post("/api/v1/benchmarks/{history_id}", dependencies=[Depends(require_local_auth)])
def benchmark_generation(history_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", history_id or ""):
        raise HTTPException(status_code=404, detail="Generation not found")
    return {"ok": True, "benchmark": STUDIO.benchmark_history(history_id)}


@app.post("/api/v1/profiles", dependencies=[Depends(require_local_auth)])
async def create_profile(
    name: str = Form(..., min_length=1, max_length=80),
    language: str = Form(..., min_length=2, max_length=32),
    start_seconds: float = Form(default=0, ge=0, le=86400),
    duration_seconds: float = Form(default=12, ge=5, le=30),
    consent_ack: bool = Form(...),
    denoise: bool = Form(default=False),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if not consent_ack:
        raise AppError("Confirm that you own this voice or have explicit permission from the speaker.", "CONSENT_REQUIRED")
    if language not in SUPPORTED_LANGUAGES and language not in SUPPORTED_LANGUAGES.values():
        raise AppError("Select a supported language for this voice reference.", "LANGUAGE_UNSUPPORTED")
    original_name = (file.filename or "reference.wav").replace("\\", "/").split("/")[-1]
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_MEDIA_EXTENSIONS:
        raise AppError("Unsupported media type. Use MP4, MOV, MKV, AVI, WEBM, WAV, MP3, M4A, FLAC, AAC or OGG.", "MEDIA_TYPE")
    source = DATA_PATHS["imports"] / f"web_{uuid.uuid4().hex}{suffix}"
    size = 0
    try:
        with source.open("xb") as target:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_IMPORT_BYTES:
                    raise AppError("The imported file exceeds the 10 GB limit.", "MEDIA_TOO_LARGE")
                target.write(chunk)
        if size == 0:
            raise AppError("The selected file is empty.", "MEDIA_EMPTY")
        record = await run_in_threadpool(
            STUDIO.create_profile,
            name,
            language,
            source,
            start_seconds,
            duration_seconds,
            consent_ack,
            denoise,
        )
        return {"ok": True, "profile": profile_public(record)}
    finally:
        source.unlink(missing_ok=True)
        await file.close()


@app.delete("/api/v1/profiles/{profile_id}", dependencies=[Depends(require_local_auth)])
def delete_profile(profile_id: str, payload: DeleteVoiceProfileRequest) -> dict[str, Any]:
    if payload.confirmation_phrase != "DELETE VOICE":
        raise AppError('Type "DELETE VOICE" exactly to permanently remove this voice profile.', "DELETE_CONFIRMATION_REQUIRED")
    if not re.fullmatch(r"[a-f0-9]{32}", profile_id or ""):
        raise HTTPException(status_code=404, detail="Voice profile not found")

    # Keep the generation queue lock across the destructive operation. New jobs
    # acquire this same lock before they are queued, so a profile cannot vanish
    # between request validation and generation starting.
    with JOBS_LOCK:
        if any(job.get("status") in {"queued", "running"} for job in JOBS.values()):
            raise AppError("Wait for the active generation to finish before deleting a voice profile.", "GENERATION_BUSY")
        cleanup_complete = STUDIO.delete_profile(profile_id)
    LOGGER.warning("Voice profile deletion requested and confirmed for %s; file_cleanup_complete=%s", profile_id, cleanup_complete)
    return {
        "ok": True,
        "deleted": True,
        "profile_id": profile_id,
        "file_cleanup_complete": cleanup_complete,
        "note": "ArkByte-managed source recordings, reference clips, transcripts and profile metadata were removed. Previously exported copies and generated narrations are not deleted.",
    }


@app.get("/api/v1/projects", dependencies=[Depends(require_local_auth)])
def list_projects() -> dict[str, Any]:
    # Keep dashboard refreshes lightweight: full scripts are loaded on demand.
    return {"ok": True, "projects": [project_summary(item) for item in STORAGE.list_project_summaries()]}


@app.get("/api/v1/projects/{project_id}", dependencies=[Depends(require_local_auth)])
def get_project(project_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", project_id or ""):
        raise HTTPException(status_code=404, detail="Project not found")
    record = STORAGE.get_project(project_id)
    if not record:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True, "project": project_public(record)}


@app.post("/api/v1/projects", dependencies=[Depends(require_local_auth)])
def save_project(payload: ProjectRequest) -> dict[str, Any]:
    title = " ".join(payload.title.split())
    script = payload.script.strip()
    output_name = safe_stem(payload.output_name, "narration")
    if not title:
        raise AppError("Enter a project title before saving.", "PROJECT_TITLE_REQUIRED")
    if len(script) < 1:
        raise AppError("Add narration text before saving this project.", "PROJECT_SCRIPT_REQUIRED")
    if payload.profile_id and not STORAGE.get_profile(payload.profile_id):
        raise AppError("The selected voice profile no longer exists. Choose another profile or clear the voice selection.", "PROFILE_NOT_FOUND")
    project_id = payload.id or uuid.uuid4().hex
    record = STORAGE.save_project({
        "id": project_id,
        "title": title,
        "script": script,
        "profile_id": payload.profile_id,
        "language_id": payload.language_id,
        "output_name": output_name,
        "exaggeration": payload.exaggeration,
        "cfg_weight": payload.cfg_weight,
        "temperature": payload.temperature,
        "model_id": payload.model_id,
    })
    LOGGER.info("Saved local narration project %s", project_id)
    return {"ok": True, "project": project_public(record)}


@app.delete("/api/v1/projects/{project_id}", dependencies=[Depends(require_local_auth)])
def delete_project(project_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", project_id or ""):
        raise HTTPException(status_code=404, detail="Project not found")
    if not STORAGE.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    STORAGE.delete_project(project_id)
    LOGGER.info("Deleted local narration project %s", project_id)
    return {"ok": True}


@app.post("/api/v1/generations", dependencies=[Depends(require_local_auth)])
def create_generation(payload: GenerateRequest) -> dict[str, Any]:
    if not payload.rights_ack:
        raise AppError(
            "Confirm that you own this voice or have the speaker's explicit permission, and agree not to use generated speech for impersonation, deception, fraud, harassment or identity-verification bypass.",
            "USE_POLICY_ACK_REQUIRED",
        )
    if payload.language_id not in SUPPORTED_LANGUAGES.values():
        raise AppError("Select a supported narration language before generating audio.", "LANGUAGE_UNSUPPORTED")
    if payload.model_id == "voxcpm05" and payload.language_id.split("-", 1)[0].lower() not in {"en", "zh"}:
        raise AppError("VoxCPM 0.5B currently supports English and Chinese only. Select English or Chinese, or use Chatterbox for other languages.", "VOXCPM05_LANGUAGE_UNSUPPORTED")
    profile = STORAGE.get_profile(payload.profile_id)
    if not profile or not bool(profile.get("consent_ack")):
        raise AppError("The selected voice profile has no valid permission confirmation. Re-enrol a voice you own or have permission to use.", "VOICE_PERMISSION_REQUIRED")
    if payload.model_id == "chatterbox" and (not importlib.util.find_spec("chatterbox") or not importlib.util.find_spec("torch")):
        raise AppError("The local Chatterbox AI engine is not installed. Run INSTALL_WEB_WINDOWS.ps1 -InstallAI, then restart the services.", "AI_NOT_INSTALLED")
    if payload.model_id in {"voxcpm05", "voxcpm2"} and not STUDIO.voxcpm.is_installed():
        raise AppError("The optional VoxCPM package is not installed. Run INSTALL VOXCPM MODELS.ps1 after reviewing its dependency report, then restart ArkByte. Chatterbox remains available.", "VOXCPM_NOT_INSTALLED")
    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        # Recheck under the same lock used by profile deletion to close the
        # validation/deletion race before a new job is queued.
        current_profile = STORAGE.get_profile(payload.profile_id)
        if not current_profile or not bool(current_profile.get("consent_ack")):
            raise AppError("The selected voice profile was removed or no longer has a valid permission confirmation. Choose another profile.", "VOICE_PERMISSION_REQUIRED")
        if any(job.get("status") in {"queued", "running"} for job in JOBS.values()):
            raise AppError("A narration is already being generated. Wait for it to finish before starting another job.", "GENERATION_BUSY")
        if len(JOBS) > 300:
            for old_id in list(JOBS)[:100]:
                if JOBS[old_id].get("status") in {"complete", "failed"}:
                    JOBS.pop(old_id, None)
        JOBS[job_id] = {"id": job_id, "status": "queued", "progress": 0.0, "message": "Waiting for the local generation worker…"}
    LOGGER.info("Generation rights attestation accepted for job %s using model %s", job_id, payload.model_id)
    GENERATOR.submit(run_generation, job_id, payload)
    return {"ok": True, "job": JOBS[job_id]}


@app.get("/api/v1/generations/{job_id}", dependencies=[Depends(require_local_auth)])
def generation_status(job_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"ok": True, "job": dict(job)}


@app.get("/api/v1/history", dependencies=[Depends(require_local_auth)])
def history() -> dict[str, Any]:
    return {"ok": True, "history": [history_public(item) for item in STORAGE.list_history(200)]}


@app.delete("/api/v1/history/{history_id}", dependencies=[Depends(require_local_auth)])
def delete_history_item(history_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", history_id or ""):
        raise HTTPException(status_code=404, detail="History item not found")
    item = STORAGE.get_history(history_id)
    if not item:
        raise HTTPException(status_code=404, detail="History item not found")
    try:
        output_path = ensure_within(DATA_PATHS["outputs"], Path(item["output_path"]))
    except Exception as exc:
        LOGGER.warning("Blocked deletion of history %s with an invalid output path", history_id)
        raise HTTPException(status_code=409, detail="The stored audio path is outside the ArkByte outputs folder; nothing was deleted.") from exc
    if output_path.exists() and not output_path.is_file():
        raise HTTPException(status_code=409, detail="The stored output is not a regular file; nothing was deleted.")
    try:
        output_path.unlink(missing_ok=True)
    except OSError as exc:
        LOGGER.exception("Could not delete generated audio for history %s", history_id)
        raise HTTPException(status_code=500, detail="The audio file could not be deleted. The history entry was retained.") from exc
    STORAGE.delete_history(history_id)
    with JOBS_LOCK:
        for job in JOBS.values():
            if job.get("history_id") == history_id:
                job["history_id"] = None
                job["audio_url"] = None
    LOGGER.info("Deleted generation history item %s and its output", history_id)
    return {"ok": True, "deleted": 1}


@app.delete("/api/v1/history", dependencies=[Depends(require_local_auth)])
def clear_generation_history() -> dict[str, Any]:
    with JOBS_LOCK:
        if any(job.get("status") in {"queued", "running"} for job in JOBS.values()):
            raise HTTPException(status_code=409, detail="Wait for the active generation to finish before clearing all history.")
    items = STORAGE.list_all_history()
    # Validate every persisted path before deleting anything. Never follow a path
    # outside the app's outputs directory, even if its DB row is malformed.
    paths: list[tuple[str, Path]] = []
    for item in items:
        try:
            output_path = ensure_within(DATA_PATHS["outputs"], Path(item["output_path"]))
        except Exception as exc:
            LOGGER.warning("Blocked bulk history deletion due to invalid output path in %s", item.get("id"))
            raise HTTPException(status_code=409, detail="At least one history entry points outside the ArkByte outputs folder. Nothing was deleted.") from exc
        if output_path.exists() and not output_path.is_file():
            raise HTTPException(status_code=409, detail="At least one stored output is not a regular file. Nothing was deleted.")
        paths.append((item["id"], output_path))

    deleted = 0
    for history_id, output_path in paths:
        try:
            output_path.unlink(missing_ok=True)
        except OSError as exc:
            LOGGER.exception("Bulk history deletion stopped at item %s", history_id)
            raise HTTPException(status_code=500, detail=f"History deletion stopped after {deleted} item(s); the remaining entries were retained.") from exc
        STORAGE.delete_history(history_id)
        deleted += 1

    deleted_ids = {history_id for history_id, _ in paths}
    with JOBS_LOCK:
        for job in JOBS.values():
            if job.get("history_id") in deleted_ids:
                job["history_id"] = None
                job["audio_url"] = None
    LOGGER.info("Cleared %s generation history item(s); voice profiles and projects were retained", deleted)
    return {"ok": True, "deleted": deleted}


@app.get("/api/v1/audio/{history_id}", dependencies=[Depends(require_local_auth)])
def download_audio(history_id: str, download: bool = Query(default=False)):
    if not re.fullmatch(r"[a-f0-9]{32}", history_id or ""):
        raise HTTPException(status_code=404, detail="Audio not found")
    item = next((row for row in STORAGE.list_history(500) if row["id"] == history_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Audio not found")
    try:
        path = ensure_within(DATA_PATHS["outputs"], Path(item["output_path"]))
    except Exception as exc:
        LOGGER.warning("Blocked invalid audio path for history %s", history_id)
        raise HTTPException(status_code=404, detail="Audio not found") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="The generated audio file is no longer available.")
    return FileResponse(path, media_type="audio/wav", filename=path.name, content_disposition_type="attachment" if download else "inline", headers={"Cache-Control": "no-store"})


@app.on_event("shutdown")
def shutdown_event() -> None:
    GENERATOR.shutdown(wait=False, cancel_futures=True)
