from __future__ import annotations

import os
import tempfile
import unittest
import math
import shutil
import struct
import wave
import io
import zipfile
import json
from pathlib import Path

_TMP = tempfile.TemporaryDirectory(prefix="arkbyte-web-test-")
os.environ["ARKBYTE_VOICE_HOME"] = str(Path(_TMP.name) / "creator-data")
os.environ["ARKBYTE_BRIDGE_TOKEN"] = "test-only-token-not-for-production"

from fastapi.testclient import TestClient  # noqa: E402
import main as main_module  # noqa: E402
from main import app  # noqa: E402


class LocalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.headers = {"X-ArkByte-Token": os.environ["ARKBYTE_BRIDGE_TOKEN"]}

    def test_health_requires_token(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["ok"])

    def test_health_is_local_and_reports_components(self):
        response = self.client.get("/api/v1/health", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["localOnly"])
        self.assertIn("engine", payload)
        self.assertIn("media", payload)
        self.assertIn("database", payload)

    def test_model_registry_exposes_optional_adapters_without_claiming_qwen_inference(self):
        response = self.client.get("/api/v1/models", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("speaker_identity", payload)
        self.assertIn("transcription", payload)
        self.assertIn("chatterbox", {item["id"] for item in payload["models"]})
        qwen = next(item for item in payload["models"] if item["id"] == "qwen3_tts")
        self.assertFalse(qwen["integrated"])

    def test_transcript_update_and_qwen_training_export_routes(self):
        profile_id = "d" * 32
        sample_id = "e" * 32
        profile_dir = main_module.DATA_PATHS["profiles"] / profile_id
        sample_dir = profile_dir / "samples"
        reference_dir = profile_dir / "references"
        sample_dir.mkdir(parents=True, exist_ok=True)
        reference_dir.mkdir(parents=True, exist_ok=True)
        original = sample_dir / "original.wav"
        reference = reference_dir / "reference.wav"
        for path in (original, reference):
            with wave.open(str(path), "wb") as stream:
                stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(24000)
                frames = bytearray()
                for index in range(24000 * 6):
                    frames.extend(struct.pack("<h", int(5000 * math.sin(2 * math.pi * 180 * index / 24000))))
                stream.writeframes(frames)
        main_module.STORAGE.add_profile({
            "id": profile_id, "name": "API test speaker", "language": "en",
            "reference_path": str(reference), "source_name": "test", "consent_ack": True,
        })
        main_module.STORAGE.add_voice_samples([{
            "id": sample_id, "profile_id": profile_id, "original_path": str(original),
            "model_reference_path": str(reference), "source_name": "original.wav",
            "transcript": "", "analysis": {"duration_seconds": 6, "quality_score": 80}, "is_anchor": True,
        }])
        try:
            updated = self.client.put(
                f"/api/v1/profiles/{profile_id}/samples/{sample_id}/transcript",
                headers=self.headers, json={"transcript": "This is the exact test transcript."},
            )
            self.assertEqual(updated.status_code, 200)
            profile_detail = self.client.get(f"/api/v1/profiles/{profile_id}/detail", headers=self.headers)
            self.assertEqual(profile_detail.status_code, 200)
            transcript_stage = next(stage for stage in profile_detail.json()["analysis"]["pipeline_stages"] if stage["id"] == "transcription")
            self.assertEqual(transcript_stage["status"], "complete")
            exported = self.client.get(f"/api/v1/profiles/{profile_id}/training-export/qwen3", headers=self.headers)
            self.assertEqual(exported.status_code, 200, exported.text)
            self.assertEqual(exported.headers.get("content-type"), "application/zip")
            with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
                rows = [json.loads(line) for line in archive.read("train_raw.jsonl").decode().splitlines()]
                self.assertEqual(rows[0]["text"], "This is the exact test transcript.")
        finally:
            main_module.STORAGE.delete_profile(profile_id)
            shutil.rmtree(profile_dir, ignore_errors=True)

    def test_auto_transcription_route_returns_review_required_draft(self):
        profile_id = "f" * 32
        sample_id = "a" * 32
        expected = {"transcript": "Draft speech text.", "detected_language": "en",
                    "language_probability": 0.98, "model": "small", "review_required": True}
        from unittest.mock import patch
        with patch.object(main_module.STUDIO, "transcribe_sample", return_value=expected):
            response = self.client.post(
                f"/api/v1/profiles/{profile_id}/samples/{sample_id}/transcribe",
                headers=self.headers,
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["transcript"], "Draft speech text.")
        self.assertTrue(response.json()["review_required"])

    def test_profile_list_does_not_leak_paths(self):
        response = self.client.get("/api/v1/profiles", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profiles"], [])



    def test_projects_require_token(self):
        response = self.client.get("/api/v1/projects")
        self.assertEqual(response.status_code, 401)

    def test_project_crud_and_validation(self):
        payload = {
            "title": "  Interview Demo  ",
            "script": "A practical local-first voice studio.",
            "profile_id": None,
            "language_id": "en",
            "output_name": "interview-demo",
            "exaggeration": 0.6,
            "cfg_weight": 0.4,
            "temperature": 0.9,
        }
        created = self.client.post("/api/v1/projects", headers=self.headers, json=payload)
        self.assertEqual(created.status_code, 200)
        project = created.json()["project"]
        self.assertEqual(project["title"], "Interview Demo")
        self.assertNotIn("output_path", project)
        listed = self.client.get("/api/v1/projects", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["projects"]), 1)
        summary = listed.json()["projects"][0]
        self.assertNotIn("script", summary)
        self.assertEqual(summary["character_count"], len(payload["script"]))
        self.assertEqual(summary["script_preview"], payload["script"])
        detail = self.client.get(f"/api/v1/projects/{project['id']}", headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["project"]["script"], payload["script"])
        payload["id"] = project["id"]
        payload["title"] = "Interview Demo Updated"
        updated = self.client.post("/api/v1/projects", headers=self.headers, json=payload)
        self.assertEqual(updated.json()["project"]["title"], "Interview Demo Updated")
        deleted = self.client.delete(f"/api/v1/projects/{project['id']}", headers=self.headers)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/projects", headers=self.headers).json()["projects"], [])

    def test_project_id_path_validation(self):
        response = self.client.delete("/api/v1/projects/not-a-valid-id", headers=self.headers)
        self.assertEqual(response.status_code, 404)
        detail = self.client.get("/api/v1/projects/not-a-valid-id", headers=self.headers)
        self.assertEqual(detail.status_code, 404)

    def test_missing_project_detail_returns_404(self):
        response = self.client.get("/api/v1/projects/" + ("a" * 32), headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_generation_validation_errors_are_normalized(self):
        response = self.client.post("/api/v1/generations", headers=self.headers, json={"profile_id": "bad"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_invalid_history_id_is_not_exposed(self):
        response = self.client.get("/api/v1/audio/../../secret", headers=self.headers)
        self.assertIn(response.status_code, (404, 400))


if __name__ == "__main__":
    unittest.main()
