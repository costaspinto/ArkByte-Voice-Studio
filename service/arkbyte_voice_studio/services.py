from __future__ import annotations

import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from .audio_analysis import aggregate_profile, analyze_audio_file
from .config import SUPPORTED_LANGUAGES, ensure_app_dirs, ensure_within, safe_stem
from .engine import ChatterboxEngine
from .errors import AppError
from .media import extract_model_reference, extract_reference
from .qwen_training_export import build_qwen_training_bundle
from .speaker_identity import EcapaSpeakerEvaluator
from .storage import Storage
from .text_processing import validate_script
from .transcription import FasterWhisperTranscriber
from .voxcpm_engine import VoxCPM05Engine, VoxCPM2Engine


class VoiceStudioService:
    def __init__(self, storage: Storage, logger: logging.Logger) -> None:
        self.storage = storage
        self.logger = logger
        self.paths = ensure_app_dirs()
        self.engine = ChatterboxEngine(logger)
        self.voxcpm = VoxCPM2Engine(logger)
        self.voxcpm05 = VoxCPM05Engine(logger)
        self.speaker_evaluator = EcapaSpeakerEvaluator(logger)
        self.transcriber = FasterWhisperTranscriber(self.paths["cache"] / "faster-whisper", logger)
        self._cleanup_quarantined_profiles()
        self.last_model = "chatterbox"
        self.last_device = "not loaded"

    def create_profile(self, name: str, language: str, source: Path, start_seconds: float,
                       duration_seconds: float, consent_ack: bool, denoise: bool,
                       progress=None) -> dict:
        """Legacy single-reference profile creation remains supported."""
        clean_name = safe_stem(name, "Voice_Profile")
        if not consent_ack:
            raise AppError("Confirm that you own this voice or have explicit permission from the speaker before creating a profile.", "CONSENT_REQUIRED")
        if not language:
            raise AppError("Select the language spoken in the reference recording.", "LANGUAGE_REQUIRED")
        profile_id = uuid.uuid4().hex
        profile_dir = self.paths["profiles"] / profile_id
        profile_dir.mkdir(parents=True, exist_ok=False)
        reference = profile_dir / "reference.wav"
        try:
            extract_reference(source, reference, start_seconds, duration_seconds, denoise, progress)
            record = {"id": profile_id, "name": clean_name, "language": language,
                      "reference_path": str(reference), "source_name": source.name, "consent_ack": True}
            self.storage.add_profile(record)
            return record
        except Exception:
            shutil.rmtree(profile_dir, ignore_errors=True)
            raise

    def enroll_profile(self, name: str, language: str, sources: list[Path], source_names: list[str],
                       transcripts: list[str], consent_ack: bool, accent_notes: str = "",
                       pronunciation_notes: str = "", progress=None) -> dict[str, Any]:
        if not consent_ack:
            raise AppError("Confirm that you own this voice or have explicit permission from the speaker.", "CONSENT_REQUIRED")
        if not 1 <= len(sources) <= 10:
            raise AppError("Upload between 1 and 10 recordings per enrolment batch.", "ENROLLMENT_FILE_COUNT")
        if len(source_names) != len(sources):
            raise AppError("The upload metadata does not match the selected recordings.", "ENROLLMENT_METADATA_INVALID")
        clean_name = safe_stem(name, "Voice_Profile")
        profile_id = uuid.uuid4().hex
        profile_dir = self.paths["profiles"] / profile_id
        samples_dir = profile_dir / "samples"
        refs_dir = profile_dir / "references"
        samples_dir.mkdir(parents=True, exist_ok=False)
        records: list[dict[str, Any]] = []
        try:
            for index, (source, source_name) in enumerate(zip(sources, source_names), start=1):
                if progress:
                    progress(f"Analysing recording {index} of {len(sources)}…")
                analysis = analyze_audio_file(source)
                sample_id = uuid.uuid4().hex
                suffix = source.suffix.lower() or ".audio"
                original_path = samples_dir / f"{sample_id}_original{suffix}"
                reference_path = refs_dir / f"{sample_id}_reference.wav"
                shutil.copy2(source, original_path)
                duration = float(analysis["duration_seconds"])
                reference_duration = min(30.0, max(5.0, duration))
                # Start at a central segment for long recordings, avoiding common
                # opening/closing noise while retaining original audio untouched.
                start = max(0.0, (duration - reference_duration) / 2.0)
                extract_model_reference(original_path, reference_path, start, reference_duration, progress)
                transcript = (transcripts[index - 1] if index - 1 < len(transcripts) else "").strip()
                records.append({
                    "id": sample_id, "profile_id": profile_id,
                    "original_path": str(original_path),
                    "model_reference_path": str(reference_path),
                    "source_name": Path(source_name).name[:180],
                    "transcript": transcript[:8000], "transcript_reviewed": bool(transcript),
                    "analysis": analysis, "is_anchor": False,
                })
            best = max(records, key=lambda item: float(item["analysis"].get("quality_score", 0)))
            best["is_anchor"] = True
            ref = Path(best["model_reference_path"])
            profile = {
                "id": profile_id, "name": clean_name, "language": language,
                "reference_path": str(ref),
                "source_name": f"{len(records)} enrolment recordings",
                "consent_ack": True,
            }
            self.storage.add_profile(profile)
            self.storage.add_voice_samples(records)
            analysis = aggregate_profile([item["analysis"] for item in records], accent_notes, pronunciation_notes, sum(bool(item["transcript"]) for item in records))
            self.storage.save_profile_analysis(profile_id, accent_notes.strip()[:2000], pronunciation_notes.strip()[:2000], analysis)
            self.logger.info("Enrolled voice profile %s with %s recordings", profile_id, len(records))
            return {**profile, "sample_count": len(records), "analysis": analysis}
        except Exception:
            try:
                self.storage.delete_profile(profile_id)
            except Exception:
                pass
            shutil.rmtree(profile_dir, ignore_errors=True)
            raise

    def add_samples(self, profile_id: str, sources: list[Path], source_names: list[str],
                    transcripts: list[str] | None = None, progress=None) -> dict[str, Any]:
        profile = self.storage.get_profile(profile_id)
        if not profile:
            raise AppError("That voice profile no longer exists.", "PROFILE_NOT_FOUND")
        existing = self.storage.list_voice_samples(profile_id)
        if len(source_names) != len(sources):
            raise AppError("The upload metadata does not match the selected recordings.", "ENROLLMENT_METADATA_INVALID")
        if not sources or len(sources) > 10 or len(existing) + len(sources) > 10:
            raise AppError(f"This profile can contain up to 10 recordings. It currently has {len(existing)}.", "ENROLLMENT_LIMIT")
        profile_dir = ensure_within(self.paths["profiles"], self.paths["profiles"] / profile_id)
        samples_dir = profile_dir / "samples"
        refs_dir = profile_dir / "references"
        samples_dir.mkdir(parents=True, exist_ok=True)
        refs_dir.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, Any]] = []
        old_reference_path = str(profile["reference_path"])
        old_anchor = next((item for item in existing if item.get("is_anchor")), None)
        samples_persisted = False
        try:
            for index, (source, source_name) in enumerate(zip(sources, source_names), start=1):
                if progress:
                    progress(f"Analysing additional recording {index} of {len(sources)}…")
                analysis = analyze_audio_file(source)
                sample_id = uuid.uuid4().hex
                original_path = samples_dir / f"{sample_id}_original{source.suffix.lower()}"
                reference_path = refs_dir / f"{sample_id}_reference.wav"
                shutil.copy2(source, original_path)
                duration = float(analysis["duration_seconds"])
                ref_duration = min(30.0, max(5.0, duration))
                extract_model_reference(original_path, reference_path, max(0.0, (duration - ref_duration) / 2.0), ref_duration, progress)
                transcript = (transcripts[index - 1] if transcripts and index - 1 < len(transcripts) else "").strip()
                records.append({"id": sample_id, "profile_id": profile_id, "original_path": str(original_path),
                                "model_reference_path": str(reference_path), "source_name": Path(source_name).name[:180],
                                "transcript": transcript[:8000], "transcript_reviewed": bool(transcript),
                                "analysis": analysis, "is_anchor": False})
            combined = existing + records
            anchor = max(combined, key=lambda item: float(item["analysis"].get("quality_score", 0)))
            records_to_store = records
            if anchor in records:
                for sample in records_to_store:
                    sample["is_anchor"] = sample["id"] == anchor["id"]
                self.storage.add_voice_samples(records_to_store)
                samples_persisted = True
                self.storage.set_profile_anchor(profile_id, anchor["id"])
                self.storage.set_profile_reference(profile_id, anchor["model_reference_path"])
            else:
                self.storage.add_voice_samples(records_to_store)
                samples_persisted = True
            all_samples = self.storage.list_voice_samples(profile_id)
            old_meta = self.storage.get_profile_analysis(profile_id) or {}
            accent = str(old_meta.get("accent_notes", ""))
            pronunciation = str(old_meta.get("pronunciation_notes", ""))
            aggregate = aggregate_profile([item["analysis"] for item in all_samples], accent, pronunciation, sum(bool(item["transcript"]) for item in all_samples))
            self.storage.save_profile_analysis(profile_id, accent, pronunciation, aggregate)
            return {"sample_count": len(all_samples), "analysis": aggregate}
        except Exception:
            if samples_persisted:
                try:
                    self.storage.delete_voice_samples(profile_id, [item["id"] for item in records])
                    if old_anchor:
                        self.storage.set_profile_anchor(profile_id, old_anchor["id"])
                    self.storage.set_profile_reference(profile_id, old_reference_path)
                except Exception:
                    self.logger.exception("Could not roll back partially-added voice samples for %s", profile_id)
            for record in records:
                Path(record["original_path"]).unlink(missing_ok=True)
                Path(record["model_reference_path"]).unlink(missing_ok=True)
            raise

    def profile_detail(self, profile_id: str) -> dict[str, Any]:
        profile = self.storage.get_profile(profile_id)
        if not profile:
            raise AppError("That voice profile no longer exists.", "PROFILE_NOT_FOUND")
        samples = self.storage.list_voice_samples(profile_id)
        meta = self.storage.get_profile_analysis(profile_id)
        return {
            "profile": {"id": profile["id"], "name": profile["name"], "language": profile["language"],
                        "source_name": profile["source_name"], "created_at": profile["created_at"]},
            "samples": [{"id": item["id"], "source_name": item["source_name"], "transcript": item["transcript"],
                         "is_anchor": bool(item["is_anchor"]),
                         "transcript_reviewed": bool(item.get("transcript_reviewed", False)),
                         "created_at": item["created_at"], **item["analysis"]}
                        for item in samples],
            "analysis": meta["analysis"] if meta else None,
            "pronunciations": self.storage.list_pronunciations(profile_id),
        }

    def update_sample_transcript(self, profile_id: str, sample_id: str, transcript: str) -> None:
        if not self.storage.get_profile(profile_id):
            raise AppError("That voice profile no longer exists.", "PROFILE_NOT_FOUND")
        text = transcript.strip()
        if not text or len(text) > 20000:
            raise AppError("Provide the full transcript for this recording (1–20,000 characters).", "TRANSCRIPT_INVALID")
        try:
            self.storage.update_voice_sample_transcript(profile_id, sample_id, text, reviewed=True)
        except ValueError as exc:
            raise AppError("The selected recording does not belong to this voice profile.", "SAMPLE_NOT_FOUND") from exc
        samples = self.storage.list_voice_samples(profile_id)
        meta = self.storage.get_profile_analysis(profile_id) or {}
        aggregate = aggregate_profile(
            [item["analysis"] for item in samples],
            str(meta.get("accent_notes", "")),
            str(meta.get("pronunciation_notes", "")),
            sum(bool(item.get("transcript_reviewed")) for item in samples),
        )
        self.storage.save_profile_analysis(
            profile_id, str(meta.get("accent_notes", "")),
            str(meta.get("pronunciation_notes", "")), aggregate,
        )

    def transcribe_sample(self, profile_id: str, sample_id: str) -> dict[str, Any]:
        profile = self.storage.get_profile(profile_id)
        sample = self.storage.get_voice_sample(sample_id, profile_id)
        if not profile or not sample:
            raise AppError("The selected voice recording was not found.", "SAMPLE_NOT_FOUND")
        profile_dir = ensure_within(self.paths["profiles"], self.paths["profiles"] / profile_id)
        audio_path = ensure_within(profile_dir, Path(sample["original_path"]))
        language = SUPPORTED_LANGUAGES.get(str(profile.get("language", "")), None)
        result = self.transcriber.transcribe(audio_path, language)
        self.storage.update_voice_sample_transcript(profile_id, sample_id, result["transcript"], reviewed=False)
        samples = self.storage.list_voice_samples(profile_id)
        meta = self.storage.get_profile_analysis(profile_id) or {}
        aggregate = aggregate_profile(
            [item["analysis"] for item in samples],
            str(meta.get("accent_notes", "")),
            str(meta.get("pronunciation_notes", "")),
            sum(bool(item.get("transcript_reviewed")) for item in samples),
        )
        self.storage.save_profile_analysis(
            profile_id, str(meta.get("accent_notes", "")),
            str(meta.get("pronunciation_notes", "")), aggregate,
        )
        return result

    def qwen_training_bundle(self, profile_id: str) -> bytes:
        if not self.storage.get_profile(profile_id):
            raise AppError("That voice profile no longer exists.", "PROFILE_NOT_FOUND")
        samples = self.storage.list_voice_samples(profile_id)
        return build_qwen_training_bundle(profile_id, samples, self.paths["profiles"])

    def speaker_identity_comparison(self, history_id: str) -> dict[str, Any]:
        item = next((row for row in self.storage.list_history(500) if row["id"] == history_id), None)
        if not item or not item.get("profile_id"):
            raise AppError("Choose a completed generation linked to an enrolled voice profile.", "BENCHMARK_HISTORY_NOT_FOUND")
        profile_id = item["profile_id"]
        samples = self.storage.list_voice_samples(profile_id)
        if len(samples) < 2:
            raise AppError("ECAPA comparison requires at least two reference recordings.", "ECAPA_NEEDS_MULTIPLE_REFERENCES")
        output_path = ensure_within(self.paths["outputs"], Path(item["output_path"]))
        if not output_path.is_file():
            raise AppError("The generated audio file is no longer available.", "BENCHMARK_AUDIO_MISSING")
        return self.speaker_evaluator.compare(profile_id, samples, output_path, self.paths["profiles"])

    def set_anchor(self, profile_id: str, sample_id: str) -> None:
        sample = self.storage.get_voice_sample(sample_id, profile_id)
        if not sample:
            raise AppError("The selected recording does not belong to this voice profile.", "SAMPLE_NOT_FOUND")
        self.storage.set_profile_anchor(profile_id, sample_id)
        self.storage.set_profile_reference(profile_id, sample["model_reference_path"])

    def _cleanup_quarantined_profiles(self) -> None:
        """Retry removal of profile folders quarantined by an earlier deletion."""
        quarantine_root = self.paths["temp"]
        for candidate in quarantine_root.glob("profile-delete-*"):
            try:
                safe_candidate = ensure_within(quarantine_root, candidate)
                if safe_candidate.is_dir():
                    shutil.rmtree(safe_candidate)
                elif safe_candidate.exists():
                    safe_candidate.unlink()
            except Exception:
                self.logger.warning("A previously deleted voice profile still has files awaiting cleanup", exc_info=True)

    def delete_profile(self, profile_id: str) -> bool:
        """Delete one profile and all ArkByte-managed source/reference assets.

        Returns False only when the DB/profile is removed but Windows prevents
        final deletion of the quarantined files. The next service start retries.
        Generated narrations, projects, model caches and user-exported ZIPs are
        deliberately not part of a voice profile folder and are preserved.
        """
        if not re.fullmatch(r"[a-f0-9]{32}", profile_id or ""):
            raise AppError("The selected voice profile identifier is invalid.", "PROFILE_ID_INVALID")
        profile = self.storage.get_profile(profile_id)
        if not profile:
            raise AppError("That voice profile no longer exists.", "PROFILE_NOT_FOUND")

        profiles_root = self.paths["profiles"].resolve()
        profile_dir = ensure_within(profiles_root, profiles_root / profile_id)
        # Verify every database-recorded voice asset is physically inside this
        # profile's own directory. Never follow a malformed path into user data.
        recorded_paths = [profile.get("reference_path", "")]
        for sample in self.storage.list_voice_samples(profile_id):
            recorded_paths.extend([sample.get("original_path", ""), sample.get("model_reference_path", "")])
        for raw_path in recorded_paths:
            if raw_path:
                try:
                    ensure_within(profile_dir, Path(raw_path))
                except (ValueError, OSError) as exc:
                    raise AppError("This voice profile contains a reference path outside its managed folder. Nothing was deleted.", "PROFILE_PATH_UNSAFE") from exc

        quarantine_root = self.paths["temp"].resolve()
        quarantine_root.mkdir(parents=True, exist_ok=True)
        quarantine_dir = ensure_within(quarantine_root, quarantine_root / f"profile-delete-{profile_id}-{uuid.uuid4().hex}")
        moved = False
        if profile_dir.exists():
            if not profile_dir.is_dir():
                raise AppError("The voice profile storage path is not a directory. Nothing was deleted.", "PROFILE_STORAGE_INVALID")
            try:
                profile_dir.rename(quarantine_dir)
                moved = True
            except OSError as exc:
                raise AppError("Windows could not safely move this voice profile for deletion. Close any program using its recordings and retry.", "PROFILE_STORAGE_BUSY") from exc

        try:
            self.storage.delete_profile(profile_id)
        except Exception:
            if moved and quarantine_dir.exists() and not profile_dir.exists():
                quarantine_dir.rename(profile_dir)
            raise

        cleanup_complete = True
        if moved:
            try:
                shutil.rmtree(quarantine_dir)
            except Exception:
                cleanup_complete = False
                self.logger.error("Voice profile %s was removed from the library, but quarantined files need cleanup", profile_id, exc_info=True)
        self.logger.info("Deleted voice profile %s; file_cleanup_complete=%s", profile_id, cleanup_complete)
        return cleanup_complete

    def add_pronunciation(self, profile_id: str, term: str, say_as: str, notes: str = "") -> dict[str, Any]:
        if not self.storage.get_profile(profile_id):
            raise AppError("That voice profile no longer exists.", "PROFILE_NOT_FOUND")
        term = " ".join(term.split()).strip()
        say_as = " ".join(say_as.split()).strip()
        if not term or not say_as or len(term) > 100 or len(say_as) > 200:
            raise AppError("Provide a term (1–100 characters) and its spoken form (1–200 characters).", "PRONUNCIATION_INVALID")
        return self.storage.upsert_pronunciation({"id": uuid.uuid4().hex, "profile_id": profile_id,
                                                  "term": term, "say_as": say_as, "notes": notes[:500]})

    def _apply_pronunciations(self, profile_id: str, script: str) -> str:
        entries = self.storage.list_pronunciations(profile_id)
        for entry in sorted(entries, key=lambda item: len(item["term"]), reverse=True):
            pattern = re.compile(rf"(?<!\w){re.escape(entry['term'])}(?!\w)", re.IGNORECASE)
            script = pattern.sub(entry["say_as"], script)
        return script

    def generate(self, profile_id: str, script: str, language_id: str, output_name: str,
                 exaggeration: float = 0.5, cfg_weight: float = 0.5,
                 temperature: float = 0.8, progress=None, model_id: str = "chatterbox") -> Path:
        script = validate_script(script)
        if not re.fullmatch(r"[a-f0-9]{32}", profile_id or ""):
            raise AppError("The selected voice profile identifier is invalid.", "PROFILE_ID_INVALID")
        profile = self.storage.get_profile(profile_id)
        if not profile:
            raise AppError("Select an existing voice profile before generating audio.", "PROFILE_NOT_FOUND")
        profile_dir = ensure_within(self.paths["profiles"], self.paths["profiles"] / profile_id)
        reference = ensure_within(profile_dir, Path(profile["reference_path"]))
        if not reference.is_file():
            raise AppError("The voice profile audio is missing. Delete and recreate this profile.", "PROFILE_AUDIO_MISSING")
        spoken_script = self._apply_pronunciations(profile_id, script)
        filename = safe_stem(output_name, "narration") + ".wav"
        output = self.paths["outputs"] / f"{uuid.uuid4().hex[:8]}_{filename}"
        if model_id == "chatterbox":
            self.voxcpm.unload()
            self.voxcpm05.unload()
            result = self.engine.generate(spoken_script, reference, language_id, output,
                                          exaggeration, cfg_weight, temperature, progress)
            self.last_model = "chatterbox"
            self.last_device = self.engine.device
        elif model_id in {"voxcpm05", "voxcpm2"}:
            if model_id == "voxcpm05" and language_id.split("-", 1)[0].lower() not in {"en", "zh"}:
                raise AppError(
                    "VoxCPM 0.5B currently supports English and Chinese only. Select English or Chinese, or use Chatterbox for other languages.",
                    "VOXCPM05_LANGUAGE_UNSUPPORTED",
                )
            self.engine.unload()
            if model_id == "voxcpm05":
                self.voxcpm.unload()
            else:
                self.voxcpm05.unload()
            samples = self.storage.list_voice_samples(profile_id)
            anchor = next((sample for sample in samples if sample.get("is_anchor")), None)
            prompt_text = ""
            if anchor:
                try:
                    source_duration = float(anchor["analysis"].get("duration_seconds", 0))
                except (TypeError, ValueError):
                    source_duration = 0
                transcript_is_reviewed = bool(anchor.get("transcript_reviewed"))
                # Continuation cloning uses the exact transcript of the selected
                # reference. Long originals are centrally cropped to 30 seconds,
                # so their full-recording transcript is not a valid prompt.
                if source_duration <= 30 and transcript_is_reviewed and anchor.get("transcript"):
                    prompt_text = str(anchor["transcript"])
            if model_id == "voxcpm05":
                if not anchor or source_duration > 30 or not prompt_text:
                    raise AppError(
                        "VoxCPM 0.5B needs an anchor recording of 30 seconds or less and an exact, reviewed transcript for that complete clip. Select a suitable anchor and save its transcript in Voice Lab.",
                        "VOXCPM05_TRANSCRIPT_REQUIRED",
                    )
                result = self.voxcpm05.generate(spoken_script, reference, output, prompt_text, progress)
                self.last_model = "voxcpm05"
                self.last_device = self.voxcpm05.device
            else:
                result = self.voxcpm.generate(spoken_script, reference, output, prompt_text, progress)
                self.last_model = "voxcpm2"
                self.last_device = self.voxcpm.device
        else:
            raise AppError("Select a supported local generation model.", "MODEL_UNSUPPORTED")
        self.storage.add_history({
            "id": uuid.uuid4().hex, "profile_id": profile_id, "profile_name": profile["name"],
            "script_preview": script[:180], "language": language_id,
            "output_path": str(result), "status": "complete",
        })
        return result

    def benchmark_history(self, history_id: str) -> dict[str, Any]:
        item = next((row for row in self.storage.list_history(500) if row["id"] == history_id), None)
        if not item or not item.get("profile_id"):
            raise AppError("Choose a completed generation linked to a voice profile.", "BENCHMARK_HISTORY_NOT_FOUND")
        profile_id = item["profile_id"]
        samples = self.storage.list_voice_samples(profile_id)
        if not samples:
            raise AppError("This profile has no multi-recording enrolment dataset. Add recordings in Voice Lab first.", "BENCHMARK_DATASET_REQUIRED")
        output_path = ensure_within(self.paths["outputs"], Path(item["output_path"]))
        if not output_path.is_file():
            raise AppError("The generated audio file is no longer available.", "BENCHMARK_AUDIO_MISSING")
        generated = analyze_audio_file(output_path)

        def ref_median(key: str):
            values = [float(sample["analysis"][key]) for sample in samples if sample["analysis"].get(key) is not None]
            if not values:
                return None
            values.sort()
            return values[len(values) // 2] if len(values) % 2 else (values[len(values)//2 - 1] + values[len(values)//2]) / 2

        comparisons = []
        weighted: list[tuple[float, float]] = []
        for key, label, weight, tolerance, unit in [
            ("pitch_median_hz", "Median pitch", 0.35, 45.0, "Hz"),
            ("rms_dbfs", "Average recording level", 0.25, 12.0, "dBFS"),
            ("spectral_centroid_hz", "Spectral brightness", 0.25, 1200.0, "Hz"),
            ("active_speech_ratio", "Speech occupancy", 0.15, 0.25, "ratio"),
        ]:
            target = ref_median(key)
            actual = generated.get(key)
            # The source uses a median across separate samples, not an identity embedding.
            if target is None or actual is None:
                comparisons.append({"label": label, "available": False, "note": "Not enough valid signal data."})
                continue
            delta = abs(float(actual) - float(target))
            score = max(0.0, 1.0 - delta / tolerance) * 100.0
            weighted.append((score, weight))
            comparisons.append({"label": label, "available": True, "reference_median": round(float(target), 2),
                                "generated": round(float(actual), 2), "difference": round(delta, 2),
                                "unit": unit, "proxy_score": round(score, 1)})
        proxy_score = round(sum(score * weight for score, weight in weighted) / sum(weight for _, weight in weighted), 1) if weighted else None
        return {
            "history_id": history_id, "profile_id": profile_id, "profile_name": item["profile_name"],
            "generated_quality": generated,
            "acoustic_proxy_score": proxy_score,
            "comparisons": comparisons,
            "interpretation": "This is a coarse acoustic-profile comparison, not speaker verification, accent accuracy, or perceptual similarity. Microphone, room, emotion, script and recording level can change these values.",
            "next_step": "Use blind listening and, when installed, a validated speaker-embedding model plus phonetic/accent evaluation before claiming identity similarity.",
        }
