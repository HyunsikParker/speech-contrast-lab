import unittest

import numpy as np

from speechcontrast.alignment import align_emissions, normalize_transcript


class CTCAlignmentTests(unittest.TestCase):
    def test_hand_labeled_repeated_character_and_word_boundaries(self):
        vocab = {"<pad>": 0, "A": 1, "L": 2, "|": 3, "B": 4}
        # The two L tokens require an intervening blank; adjacent repeat frames collapse.
        labels = [0, 1, 1, 0, 2, 2, 0, 2, 2, 0, 3, 0, 4, 4, 0]
        probabilities = np.full((len(labels), len(vocab)), 0.0025)
        probabilities[np.arange(len(labels)), labels] = 0.99
        result = align_emissions(np.log(probabilities), "ALL B", vocab, frame_hop=0.1, frame_width=0.1)
        self.assertEqual([(x["word"], x["start"], x["end"]) for x in result],
                         [("ALL", 0.1, 0.9), ("B", 1.2, 1.4)])
        self.assertGreater(result[0]["confidence"], 0.98)

    def test_known_silence_offset(self):
        vocab = {"<pad>": 0, "A": 1}
        base = np.log(np.array([[0.99, 0.01], [0.01, 0.99], [0.01, 0.99], [0.99, 0.01]]))
        shifted = np.vstack([np.tile(base[0], (8, 1)), base])
        original = align_emissions(base, "A", vocab)[0]
        moved = align_emissions(shifted, "A", vocab)[0]
        self.assertAlmostEqual(moved["start"] - original["start"], 0.16)
        self.assertAlmostEqual(moved["end"] - original["end"], 0.16)

    def test_impossible_repeated_character_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "too short"):
            align_emissions(np.log([[0.1, 0.9], [0.1, 0.9]]), "AA", {"<pad>": 0, "A": 1})

    def test_transcript_constraints(self):
        self.assertEqual(normalize_transcript("We've, made progress!"), "WE'VE MADE PROGRESS")
        for text in ["", "42 jobs", "한국어", "word " * 181]:
            with self.subTest(text=text[:15]), self.assertRaises(ValueError):
                normalize_transcript(text)

    def test_non_finite_and_unknown_tokens_are_rejected(self):
        for emissions, text in [(np.array([[np.nan, -1.0]]), "A"),
                                (np.log([[0.1, 0.9]]), "Z")]:
            with self.assertRaises(ValueError):
                align_emissions(emissions, text, {"<pad>": 0, "A": 1})


if __name__ == "__main__":
    unittest.main()

