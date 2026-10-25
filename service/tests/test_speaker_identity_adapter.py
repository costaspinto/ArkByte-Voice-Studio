from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

from arkbyte_voice_studio.speaker_identity import EcapaSpeakerEvaluator


class SpeakerIdentityAdapterTests(unittest.TestCase):
    def test_status_is_lazy_and_does_not_download_weights(self):
        with patch.object(EcapaSpeakerEvaluator, "is_installed", return_value=False):
            evaluator = EcapaSpeakerEvaluator(logging.getLogger("test"))
            status = evaluator.status()
        self.assertFalse(status["installed"])
        self.assertFalse(status["weights_cached"])
        self.assertEqual(status["status"], "optional_dependency_missing")
        self.assertTrue(status["first_use_download"])

    def test_optional_dependency_missing_returns_clear_error(self):
        with patch.object(EcapaSpeakerEvaluator, "is_installed", return_value=False):
            evaluator = EcapaSpeakerEvaluator(logging.getLogger("test"))
            with self.assertRaises(Exception) as caught:
                evaluator._load()
        self.assertEqual(getattr(caught.exception, "code", None), "ECAPA_NOT_INSTALLED")


if __name__ == "__main__":
    unittest.main()
