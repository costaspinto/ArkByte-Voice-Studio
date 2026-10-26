import tempfile
import unittest
from pathlib import Path

from arkbyte_voice_studio.storage import Storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_integrity(self):
        self.assertEqual(self.storage.integrity_check(), "ok")

    def test_profile_crud_and_history_reference(self):
        profile = {
            "id": "profile-1", "name": "My Voice", "language": "en",
            "reference_path": "/tmp/reference.wav", "source_name": "source.mp4", "consent_ack": True,
        }
        self.storage.add_profile(profile)
        self.assertEqual(self.storage.get_profile("profile-1")["name"], "My Voice")
        self.storage.add_history({
            "id": "history-1", "profile_id": "profile-1", "profile_name": "My Voice",
            "script_preview": "Hello world", "language": "en", "output_path": "/tmp/out.wav",
        })
        self.assertEqual(len(self.storage.list_history()), 1)
        self.storage.delete_profile("profile-1")
        self.assertIsNone(self.storage.get_profile("profile-1"))
        self.assertIsNone(self.storage.list_history()[0]["profile_id"])


    def test_history_lookup_delete_and_all_history(self):
        rows = [
            {"id": "history-a", "profile_id": None, "profile_name": "Voice A", "script_preview": "A", "language": "en", "output_path": "/tmp/a.wav"},
            {"id": "history-b", "profile_id": None, "profile_name": "Voice B", "script_preview": "B", "language": "en", "output_path": "/tmp/b.wav"},
        ]
        for row in rows:
            self.storage.add_history(row)
        self.assertEqual(self.storage.get_history("history-a")["script_preview"], "A")
        self.assertEqual(len(self.storage.list_all_history()), 2)
        self.assertTrue(self.storage.delete_history("history-a"))
        self.assertFalse(self.storage.delete_history("history-a"))
        self.assertIsNone(self.storage.get_history("history-a"))
        self.assertEqual([item["id"] for item in self.storage.list_all_history()], ["history-b"])

    def test_project_create_update_delete(self):
        created = self.storage.save_project({
            "id": "a" * 32,
            "title": "Episode One",
            "script": "A story about building useful software.",
            "profile_id": None,
            "language_id": "en",
            "output_name": "episode-one",
            "exaggeration": 0.5,
            "cfg_weight": 0.4,
            "temperature": 0.8,
        })
        self.assertEqual(created["title"], "Episode One")
        updated = self.storage.save_project({
            "id": "a" * 32,
            "title": "Episode One Revised",
            "script": "Updated narration script.",
            "profile_id": None,
            "language_id": "hi",
            "output_name": "episode-one-revised",
            "exaggeration": 0.7,
            "cfg_weight": 0.5,
            "temperature": 0.9,
        })
        self.assertEqual(updated["title"], "Episode One Revised")
        self.assertEqual(updated["created_at"], created["created_at"])
        self.assertEqual(self.storage.get_project("a" * 32)["language_id"], "hi")
        self.assertEqual(len(self.storage.list_projects()), 1)
        self.storage.delete_project("a" * 32)
        self.assertIsNone(self.storage.get_project("a" * 32))

    def test_project_survives_voice_profile_deletion(self):
        profile = {
            "id": "b" * 32, "name": "My Voice", "language": "en",
            "reference_path": "/tmp/reference.wav", "source_name": "source.wav", "consent_ack": True,
        }
        self.storage.add_profile(profile)
        self.storage.save_project({
            "id": "c" * 32, "title": "Linked project", "script": "Hello world.",
            "profile_id": profile["id"], "language_id": "en", "output_name": "hello",
            "exaggeration": 0.5, "cfg_weight": 0.5, "temperature": 0.8,
        })
        self.storage.delete_profile(profile["id"])
        self.assertIsNone(self.storage.get_project("c" * 32)["profile_id"])

    def test_parameterized_lookup_safe_for_quotes(self):
        profile = {
            "id": "safe-id", "name": "Creator's voice", "language": "en",
            "reference_path": "/tmp/ref.wav", "source_name": "creator's video.mp4", "consent_ack": True,
        }
        self.storage.add_profile(profile)
        self.assertEqual(self.storage.get_profile("safe-id")["name"], "Creator's voice")


if __name__ == "__main__":
    unittest.main()
