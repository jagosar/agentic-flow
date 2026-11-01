"""Unit tests of mutate.py: candidate generation, sampling and the scorer with stub test commands."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

MUTATE_PY = Path(__file__).resolve().parent / "mutate.py"
spec = importlib.util.spec_from_file_location("mutate_module", MUTATE_PY)
mutate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mutate)

PASS = [sys.executable, "-c", "import sys; sys.exit(0)"]
FAIL = [sys.executable, "-c", "import sys; sys.exit(1)"]


def operators_of(source):
    return [mutant.operator for mutant, _ in mutate.candidates(source, "m.py")]


class CandidateTests(unittest.TestCase):
    def test_compare_swaps_less_than_for_less_or_equal(self):
        (mutant, source), = mutate.candidates("x = a < b", "m.py")
        self.assertEqual((mutant.operator, mutant.description), ("compare", "< -> <="))
        self.assertIn("a <= b", source)

    def test_compare_with_two_ops_mutates_only_the_first(self):
        (_, source), = mutate.candidates("x = a < b < c", "m.py")
        self.assertIn("a <= b < c", source)

    def test_compare_of_identity_has_no_mutant(self):
        self.assertEqual(operators_of("x = a is b"), [])

    def test_arith_ignores_augmented_assignment(self):
        self.assertEqual(operators_of("x += 2.5"), [])
        self.assertEqual(operators_of("x = a - b"), ["arith"])

    def test_boolop_swaps_and_for_or(self):
        (_, source), = mutate.candidates("x = a and b", "m.py")
        self.assertIn("a or b", source)

    def test_not_is_dropped(self):
        (mutant, source), = mutate.candidates("x = not a", "m.py")
        self.assertEqual(mutant.description, "drop not")
        self.assertEqual(source, "x = a")

    def test_const_adds_one_to_ints_only(self):
        self.assertEqual(operators_of("x = 3"), ["const"])
        self.assertEqual(operators_of("x = True\ny = 2.5\nz = 'a'"), [])

    def test_const_skips_docstrings_and_annotations(self):
        source = 'def f(a: "x"[0] = 1) -> 5:\n    """doc 7"""\n    return a\n'
        self.assertEqual([m.description for m, _ in mutate.candidates(source, "m.py")], ["1 -> 2"])

    def test_unparseable_source_yields_nothing(self):
        self.assertEqual(mutate.candidates("def (", "x.py"), [])

    def test_each_mutant_changes_exactly_one_line(self):
        source = "def f(a, b):\n    if a < b and not a:\n        return a + 3\n    return b\n"
        import ast
        base = ast.unparse(ast.parse(source)).splitlines()
        for _, mutated in mutate.candidates(source, "m.py"):
            lines = mutated.splitlines()
            self.assertEqual(len(lines), len(base))
            self.assertEqual(sum(a != b for a, b in zip(lines, base)), 1)


class SampleTests(unittest.TestCase):
    def test_returns_everything_under_the_cap(self):
        self.assertEqual(mutate.sample([1, 2], 2), [1, 2])
        self.assertEqual(mutate.sample([], 5), [])

    def test_caps_with_even_spacing(self):
        picked = mutate.sample(list(range(10)), 5)
        self.assertEqual(picked, [0, 2, 4, 6, 8])


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="mutate-unit-"))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        (self.project / "mod.py").write_text("x = 1\n", encoding="utf-8")

    def check(self, value):
        code = f"import mod, sys; sys.exit(0 if mod.x == {value} else 1)"
        return [sys.executable, "-c", code]

    def env(self):
        return {**os.environ, "PYTHONPATH": str(self.project)}

    def score(self, suites, **kwargs):
        return mutate.score(self.project, ["mod.py"], suites, env=self.env(), **kwargs)

    def test_failing_suite_kills_and_passing_suite_survives(self):
        strong = self.score({"agents": [self.check(1)]})
        weak = self.score({"agents": [PASS]})
        self.assertEqual((strong["killed"], strong["survived"]), (1, []))
        self.assertEqual((weak["killed"], len(weak["survived"])), (0, 1))

    def test_same_size_mutant_is_reloaded_not_served_from_bytecode(self):
        (self.project / "mod.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
        result = self.score({"agents": [self.check(1)]})
        self.assertEqual((result["total"], result["killed"]), (2, 1))

    def test_red_baseline_counts_nothing(self):
        result = self.score({"agents": [FAIL]})
        self.assertIsNone(result["killed"])
        self.assertEqual((result["total"], result["survived"]), (1, []))

    def test_missing_suite_gives_none_oracle_count(self):
        self.assertIsNone(self.score({"agents": [PASS]})["oracle_killed"])

    def test_missing_command_is_red_at_baseline(self):
        result = self.score({"agents": [["no-such-command-xyz"]]})
        self.assertIsNone(result["killed"])

    def test_oracle_count_is_separate(self):
        result = self.score({"agents": [PASS], "oracle": [self.check(1)]})
        self.assertEqual((result["killed"], result["oracle_killed"]), (0, 1))

    def test_original_bytes_are_restored(self):
        original = (self.project / "mod.py").read_bytes()
        self.score({"agents": [self.check(1)]})
        self.assertEqual((self.project / "mod.py").read_bytes(), original)

    def test_file_is_restored_when_a_run_raises(self):
        original = (self.project / "mod.py").read_bytes()
        boom = unittest.mock.patch.object(mutate, "_run_suite", side_effect=[(True, False), RuntimeError("x")])
        with boom, self.assertRaises(RuntimeError):
            self.score({"agents": [PASS]})
        self.assertEqual((self.project / "mod.py").read_bytes(), original)

    def test_timeout_kills_and_is_counted(self):
        sleeper = [sys.executable, "-c", "import mod, time; time.sleep(0 if mod.x == 1 else 30)"]
        result = self.score({"agents": [sleeper]}, timeout_s=2)
        self.assertEqual((result["killed"], result["timeouts"]), (1, 1))

    def test_no_candidates_is_none(self):
        (self.project / "mod.py").write_text("x = 'a'\n", encoding="utf-8")
        self.assertIsNone(self.score({"agents": [PASS]}))

    def test_missing_file_raises_mutation_error(self):
        with self.assertRaises(mutate.MutationError):
            mutate.score(self.project, ["gone.py"], {"agents": [PASS]}, env=self.env())

    def test_non_utf8_source_raises_mutation_error(self):
        (self.project / "mod.py").write_bytes(b"x = '\xff'\n")
        with self.assertRaises(mutate.MutationError):
            self.score({"agents": [PASS]})

    def test_cap_limits_the_mutants_run(self):
        (self.project / "mod.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
        self.assertEqual(self.score({"agents": [PASS]}, cap=2)["total"], 2)


if __name__ == "__main__":
    unittest.main()
