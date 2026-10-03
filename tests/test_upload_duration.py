from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np

from speechcontrast.analyze import analyze_files
from speechcontrast.audio import write_wav


class UploadDurationTests(unittest.TestCase):
    def test_overlong_audio_is_rejected_not_silently_truncated(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'long.wav'
            write_wav(path, np.zeros(31 * 16000, dtype=np.float32))
            with patch('speechcontrast.analyze.TranscriptVerifier') as verifier:
                with self.assertRaisesRegex(ValueError, 'at most 30 seconds'):
                    analyze_files(path, path, 'SAME WORDS')
                verifier.assert_not_called()
