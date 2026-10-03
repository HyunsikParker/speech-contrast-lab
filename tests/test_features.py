import unittest
import numpy as np

from speechcontrast.features import extract_features
from speechcontrast.comparison import compare


class FeatureTests(unittest.TestCase):
    def test_pitch_and_biological_normalization(self):
        t = np.arange(16000) / 16000
        low = extract_features(0.3 * np.sin(2 * np.pi * 125 * t))
        high = extract_features(0.15 * np.sin(2 * np.pi * 250 * t))
        self.assertAlmostEqual(float(np.median(low['f0_hz'][low['voiced']])), 125, delta=2)
        self.assertAlmostEqual(float(np.median(high['f0_hz'][high['voiced']])), 250, delta=2)
        self.assertLess(float(np.max(abs(low['pitch_semitones']))), 0.1)
        self.assertLess(float(np.max(abs(high['pitch_semitones']))), 0.1)

    def test_global_gain_does_not_change_relative_energy_score(self):
        t = np.arange(32000) / 16000
        x = (0.3 + 0.05 * np.sin(t)) * np.sin(2 * np.pi * 150 * t)
        words = [{'word': 'SAME', 'start': 0.05, 'end': 0.85, 'confidence': 1},
                 {'word': 'TEXT', 'start': 1.05, 'end': 1.85, 'confidence': 1}]
        result = compare(x, x * 0.4, words, words)
        self.assertEqual(result['regions'], [])
        self.assertEqual(result['score'], 100)

    def test_local_energy_dip_has_a_grounded_region(self):
        t = np.arange(32000) / 16000
        x = 0.3 * np.sin(2 * np.pi * 150 * t)
        y = x.copy()
        y[16000:] *= 0.2
        words = [{'word': 'ONE', 'start': 0.05, 'end': 0.85, 'confidence': 1},
                 {'word': 'TWO', 'start': 1.05, 'end': 1.85, 'confidence': 1}]
        result = compare(x, y, words, words)
        volume = [r for r in result['regions'] if r['kind'] == 'volume']
        self.assertTrue(volume)
        self.assertLess(result['score'], 100)
        self.assertTrue(any('TWO' in r['words'] for r in volume))

    def test_silence_and_nonfinite_inputs(self):
        result = extract_features(np.zeros(16000))
        self.assertFalse(result['voiced'].any())
        self.assertTrue(np.isfinite(result['mfcc']).all())
        with self.assertRaises(ValueError):
            extract_features(np.array([np.nan] * 500))


if __name__ == '__main__':
    unittest.main()
