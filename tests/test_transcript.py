import unittest

from speechcontrast.transcript import word_agreement


class TranscriptSupportTests(unittest.TestCase):
    def test_different_text_is_not_supported(self):
        self.assertEqual(word_agreement("ONE CLEAR SENTENCE", "OTHER WORDS HERE"), 0)

    def test_exact_and_insertion_errors(self):
        self.assertEqual(word_agreement("We've made progress.", "We've made progress!"), 1)
        self.assertAlmostEqual(word_agreement("ONE CLEAR SENTENCE", "ONE VERY CLEAR SENTENCE"), 2/3)

    def test_prefix_is_explicit_and_not_default(self):
        self.assertEqual(word_agreement("ONE CLEAR SENTENCE", "ONE CLEAR SENTENCE AND MORE", prefix=True), 1)
        self.assertLess(word_agreement("ONE CLEAR SENTENCE", "ONE CLEAR SENTENCE AND MORE"), 1)

    def test_recognizer_digit_outside_prefix_does_not_abort(self):
        self.assertEqual(word_agreement("ONE CLEAR SENTENCE", "One clear sentence at G8.", prefix=True), 1)


if __name__ == "__main__":
    unittest.main()
