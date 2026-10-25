import unittest

from arkbyte_voice_studio.errors import AppError
from arkbyte_voice_studio.text_processing import pause_after_chunk_seconds, split_script, validate_script


class TextProcessingTests(unittest.TestCase):
    def test_empty_script_rejected(self):
        with self.assertRaises(AppError):
            validate_script("   ")

    def test_script_limit_enforced(self):
        with self.assertRaises(AppError):
            validate_script("a" * 50001)

    def test_split_long_text_respects_chunk_limit_for_normal_words(self):
        text = "This is a sentence. " * 60
        chunks = split_script(text, max_chars=160)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 160 for chunk in chunks))

    def test_split_preserves_words(self):
        text = "First paragraph has words.\n\nSecond paragraph also has words."
        chunks = split_script(text, max_chars=120)
        combined = " ".join(chunks)
        for word in ["First", "paragraph", "words", "Second", "also"]:
            self.assertIn(word, combined)

    def test_chunk_pause_follows_punctuation(self):
        self.assertLess(pause_after_chunk_seconds("A phrase,"), pause_after_chunk_seconds("A statement."))
        self.assertGreater(pause_after_chunk_seconds("A question?"), pause_after_chunk_seconds("A phrase;"))

    def test_invalid_chunk_bound_is_clamped(self):
        chunks = split_script("A short sentence.", max_chars=1)
        self.assertEqual(chunks, ["A short sentence."])


if __name__ == "__main__":
    unittest.main()
