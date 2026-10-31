"""Tests of the package version."""
import unittest

import inventory


class VersionTests(unittest.TestCase):
    def test_version_is_semver(self):
        self.assertRegex(inventory.__version__, r"^\d+\.\d+\.\d+$")

    def test_version_is_initial(self):
        self.assertEqual(inventory.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
