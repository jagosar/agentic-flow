"""Hidden checks of the vault fixture. Each test imports inside, so a missing module fails one test."""
import os
import sqlite3
import tempfile
import unittest

SECRET = b"s3cret"
OTHER_SECRET = b"another"
EXPIRES = 2000
NOW = 1000
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_."


def make_catalogue(*pairs):
    from vault.catalogue import Catalogue

    catalogue = Catalogue(sqlite3.connect(":memory:"))
    for owner, name in pairs:
        catalogue.add(owner, name)
    return catalogue


class StorageTests(unittest.TestCase):
    def test_plain_name_is_kept_in_base(self):
        from vault.storage import upload_path

        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "store")
            path = upload_path(base, "a.txt")
            self.assertTrue(os.path.isabs(path))
            self.assertEqual(os.path.realpath(path), os.path.join(os.path.realpath(base), "a.txt"))

    def test_name_with_folders(self):
        from vault.storage import upload_path

        with tempfile.TemporaryDirectory() as tmp:
            path = upload_path(tmp, "reports/2026/q1.csv")
            expected = os.path.join(os.path.realpath(tmp), "reports", "2026", "q1.csv")
            self.assertEqual(os.path.realpath(path), expected)

    def test_empty_or_blank_name_is_rejected(self):
        from vault.storage import upload_path

        for name in ("", "   ", "\t"):
            with self.assertRaises(ValueError):
                upload_path("base", name)

    def test_base_need_not_exist(self):
        from vault.storage import upload_path

        with tempfile.TemporaryDirectory() as tmp:
            path = upload_path(os.path.join(tmp, "missing", "deeper"), "a.txt")
            self.assertTrue(path.endswith("a.txt"))


class AdversarialPathTests(unittest.TestCase):
    def assert_stays_inside(self, name):
        from vault.storage import upload_path

        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "store")
            try:
                result = upload_path(base, name)
            except ValueError:
                return
            try:
                real_base = os.path.realpath(base)
                real_result = os.path.realpath(result)
                common = os.path.commonpath([real_base, real_result])
            except ValueError:
                self.fail("%r gave an unusable path %r" % (name, result))
            self.assertEqual(common, real_base, "%r left the base: %r" % (name, result))
            self.assertNotEqual(real_result, real_base, "%r gave the base itself" % (name,))

    def test_adv_parent_segments(self):
        for name in ("../x", "a/../../x", "./../x", ".."):
            self.assert_stays_inside(name)

    def test_adv_absolute_name(self):
        self.assert_stays_inside("/etc/passwd")

    def test_adv_current_and_self_segments(self):
        for name in (".", "a/.."):
            self.assert_stays_inside(name)

    def test_adv_backslash_parent(self):
        self.assert_stays_inside("..\\x")

    def test_adv_nul_byte(self):
        self.assert_stays_inside("a\0b")


class TokenTests(unittest.TestCase):
    def test_round_trip(self):
        from vault.tokens import issue, verify

        token = issue(SECRET, "file-42", EXPIRES)
        self.assertEqual(verify(SECRET, token, NOW), "file-42")

    def test_token_is_url_safe(self):
        from vault.tokens import issue

        token = issue(SECRET, "file-42", EXPIRES)
        self.assertRegex(token, r"^[A-Za-z0-9_.\-]+$")

    def test_last_valid_second(self):
        from vault.tokens import issue, verify

        token = issue(SECRET, "f", EXPIRES)
        self.assertEqual(verify(SECRET, token, EXPIRES - 1), "f")

    def test_expired_token_is_invalid(self):
        from vault.tokens import InvalidToken, issue, verify

        token = issue(SECRET, "f", EXPIRES)
        for now in (EXPIRES, EXPIRES + 1, EXPIRES + 10000):
            with self.assertRaises(InvalidToken):
                verify(SECRET, token, now)

    def test_garbage_is_invalid(self):
        from vault.tokens import InvalidToken, verify

        for token in ("", "abc", "a.b.c", "....", "not a token"):
            with self.assertRaises(InvalidToken):
                verify(SECRET, token, NOW)

    def test_issue_rejects_bad_arguments(self):
        from vault.tokens import issue

        for secret, file_id in ((b"", "f"), (SECRET, ""), (SECRET, "a b"), (SECRET, "café")):
            with self.assertRaises(ValueError):
                issue(secret, file_id, EXPIRES)

    def test_adv_other_secret(self):
        from vault.tokens import InvalidToken, issue, verify

        token = issue(SECRET, "f", EXPIRES)
        with self.assertRaises(InvalidToken):
            verify(OTHER_SECRET, token, NOW)

    def test_adv_flipped_characters(self):
        from vault.tokens import InvalidToken, issue, verify

        # every other character of the token alphabet at every position: a change that still verifies must not
        # alter the file id, nor keep the token alive past its expiry
        token = issue(SECRET, "file-42", EXPIRES)
        for index, char in enumerate(token):
            for other in ALPHABET:
                if other == char:
                    continue
                candidate = token[:index] + other + token[index + 1:]
                try:
                    result = verify(SECRET, candidate, NOW)
                except InvalidToken:
                    continue
                self.assertEqual(result, "file-42", "changing character %d changed the file id" % index)
                with self.assertRaises(InvalidToken, msg="changing character %d extended the expiry" % index):
                    verify(SECRET, candidate, EXPIRES)

    def test_adv_spliced_tokens(self):
        from vault.tokens import InvalidToken, issue, verify

        first = issue(SECRET, "file-1", EXPIRES)
        second = issue(SECRET, "file-2", EXPIRES)
        allowed = {"file-1", "file-2"}
        for left, right in ((first, second), (second, first)):
            for cut in range(len(left) + 1):
                try:
                    result = verify(SECRET, left[:cut] + right[cut:], NOW)
                except InvalidToken:
                    continue
                self.assertIn(result, allowed)


class CatalogueTests(unittest.TestCase):
    def test_add_returns_new_ids(self):
        catalogue = make_catalogue()
        first = catalogue.add("ann", "a.txt")
        second = catalogue.add("ann", "b.txt")
        self.assertNotEqual(first, second)

    def test_constructor_keeps_existing_rows(self):
        from vault.catalogue import Catalogue

        conn = sqlite3.connect(":memory:")
        Catalogue(conn).add("ann", "a.txt")
        self.assertEqual(Catalogue(conn).find("ann", ""), ["a.txt"])

    def test_find_is_literal_case_insensitive_and_sorted(self):
        catalogue = make_catalogue(("ann", "Report-B.txt"), ("ann", "report-a.txt"), ("ann", "notes.txt"))
        self.assertEqual(catalogue.find("ann", "REPORT"), ["Report-B.txt", "report-a.txt"])

    def test_empty_text_returns_every_file_of_owner(self):
        catalogue = make_catalogue(("ann", "b"), ("ann", "a"), ("bob", "c"))
        self.assertEqual(catalogue.find("ann", ""), ["a", "b"])

    def test_find_only_returns_files_of_owner(self):
        catalogue = make_catalogue(("ann", "x.txt"), ("bob", "x.txt"), ("bob", "y.txt"))
        self.assertEqual(catalogue.find("bob", "x."), ["x.txt"])
        self.assertEqual(catalogue.find("zed", ""), [])

    def test_no_match_is_empty(self):
        self.assertEqual(make_catalogue(("ann", "a.txt")).find("ann", "zzz"), [])

    def test_blank_owner_or_name_is_rejected(self):
        catalogue = make_catalogue()
        for owner, name in (("", "a"), ("  ", "a"), ("ann", ""), ("ann", "   ")):
            with self.assertRaises(ValueError):
                catalogue.add(owner, name)
        self.assertEqual(catalogue.find("ann", ""), [])

    def test_adv_injected_text(self):
        catalogue = make_catalogue(("ann", "a.txt"), ("bob", "secret.txt"))
        for text in ("' OR '1'='1", "x' OR 1=1 --", '"'):
            self.assertEqual(catalogue.find("ann", text), [], text)

    def test_adv_injected_owner(self):
        catalogue = make_catalogue(("ann", "a.txt"), ("bob", "secret.txt"))
        for owner in ("' OR '1'='1", "x' OR 1=1 --", '"'):
            self.assertEqual(catalogue.find(owner, ""), [], owner)

    def test_adv_quote_in_text_matches_literally(self):
        catalogue = make_catalogue(("ann", 'say "hi".txt'), ("ann", "plain.txt"))
        self.assertEqual(catalogue.find("ann", '"'), ['say "hi".txt'])

    def test_adv_literal_percent(self):
        catalogue = make_catalogue(("ann", "50%.txt"), ("ann", "plain.txt"))
        self.assertEqual(catalogue.find("ann", "%"), ["50%.txt"])

    def test_adv_literal_underscore(self):
        catalogue = make_catalogue(("ann", "a_b.txt"), ("ann", "axb.txt"))
        self.assertEqual(catalogue.find("ann", "_"), ["a_b.txt"])


if __name__ == "__main__":
    unittest.main()
