from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from arkbyte_voice_studio.storage import Storage


class VoiceIntelligenceStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self.temp.name) / "studio.db")
        self.profile_id = "a" * 32
        self.storage.add_profile({
            "id": self.profile_id, "name": "Test voice", "language": "en",
            "reference_path": "/tmp/reference.wav", "source_name": "test.wav", "consent_ack": True,
        })

    def tearDown(self):
        self.temp.cleanup()

    def test_voice_samples_anchor_and_transcript_persist(self):
        samples = []
        for index in range(2):
            samples.append({
                "id": f"{index + 1:032x}", "profile_id": self.profile_id,
                "original_path": f"/tmp/{index}.wav", "model_reference_path": f"/tmp/ref{index}.wav",
                "source_name": f"sample{index}.wav", "transcript": f"Speech sample {index}",
                "transcript_reviewed": True, "analysis": {"duration_seconds": 12.5, "quality_score": 80 + index},
                "is_anchor": index == 0,
            })
        self.storage.add_voice_samples(samples)
        self.storage.update_voice_sample_transcript(self.profile_id, samples[1]["id"], "Correct full transcript.")
        self.storage.set_profile_anchor(self.profile_id, samples[1]["id"])
        saved = self.storage.list_voice_samples(self.profile_id)
        self.assertEqual(len(saved), 2)
        self.assertEqual([item["id"] for item in saved if item["is_anchor"]], [samples[1]["id"]])
        saved_sample = self.storage.get_voice_sample(samples[1]["id"], self.profile_id)
        self.assertEqual(saved_sample["transcript"], "Correct full transcript.")
        self.assertEqual(saved_sample["transcript_reviewed"], 1)
        self.storage.update_voice_sample_transcript(self.profile_id, samples[1]["id"], "ASR draft.", reviewed=False)
        self.assertEqual(self.storage.get_voice_sample(samples[1]["id"], self.profile_id)["transcript_reviewed"], 0)

    def test_profile_analysis_and_pronunciation_upsert(self):
        self.storage.save_profile_analysis(self.profile_id, "Regional English", "Some names", {"sample_count": 2})
        analysis = self.storage.get_profile_analysis(self.profile_id)
        self.assertEqual(analysis["accent_notes"], "Regional English")
        first = self.storage.upsert_pronunciation({"id": "1" * 32, "profile_id": self.profile_id, "term": "ArkByte", "say_as": "Ark Byte"})
        updated = self.storage.upsert_pronunciation({"id": "2" * 32, "profile_id": self.profile_id, "term": "ArkByte", "say_as": "Ark-Bite"})
        self.assertEqual(first["id"], updated["id"])
        self.assertEqual(updated["say_as"], "Ark-Bite")
        self.storage.delete_pronunciation(self.profile_id, updated["id"])
        self.assertEqual(self.storage.list_pronunciations(self.profile_id), [])

    def test_project_model_id_persists(self):
        project = self.storage.save_project({
            "id": "b" * 32, "title": "Test", "script": "Hello.", "profile_id": self.profile_id,
            "language_id": "en", "output_name": "test", "exaggeration": 0.5,
            "cfg_weight": 0.5, "temperature": 0.8, "model_id": "voxcpm2",
        })
        self.assertEqual(project["model_id"], "voxcpm2")
        self.assertEqual(self.storage.get_project("b" * 32)["model_id"], "voxcpm2")


if __name__ == "__main__":
    unittest.main()
