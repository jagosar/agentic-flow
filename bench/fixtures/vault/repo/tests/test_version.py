"""Tests of the package version."""
import unittest

import vault


class VersionTests(unittest.TestCase):
    def test_version_is_semver(self):
        self.assertRegex(vault.__version__, r"^\d+\.\d+\.\d+$")

    def test_version_is_initial(self):
        self.assertEqual(vault.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
