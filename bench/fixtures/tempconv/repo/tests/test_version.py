"""Tests of the package version."""
import unittest

import tempconv


class VersionTests(unittest.TestCase):
    def test_version_is_a_dotted_triple(self):
        parts = tempconv.__version__.split(".")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(part.isdigit() for part in parts))


if __name__ == "__main__":
    unittest.main()
