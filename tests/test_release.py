import unittest

from scripts.check_release import inspect_text


class ReleaseTests(unittest.TestCase):
    def test_synthetic_patterns_and_ordinary_source(self):
        samples = ["ghp_" + "A" * 36, "AKIA" + "A" * 16, "-----BEGIN " + "PRIVATE KEY-----",
                   "sk-" + "A" * 32, "https://" + "name:secret@example.invalid",
                   "/" + "Users/example/private/", "api_key = '" + "A" * 20 + "'"]
        for index, sample in enumerate(samples):
            with self.subTest(index=index):
                self.assertTrue(inspect_text(sample))
        self.assertEqual(inspect_text("def add(a, b): return a + b"), [])
