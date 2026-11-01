"""QA tests for bench/mutate.py and the mutation wiring in bench/bench.py.
Run: python3 -m unittest discover -s qa -p "test_qa_quality.py"
Tests named test_dN_ reproduce defect N and stay red until it is fixed."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".claude" / "bin"))


def load(name):
    spec = importlib.util.spec_from_file_location(name + "_qa", ROOT / "bench" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mutate = load("mutate")
bench = load("bench")


def tmp(case):
    d = tempfile.TemporaryDirectory()
    case.addCleanup(d.cleanup)
    return Path(d.name)


class CandidateEdges(unittest.TestCase):
    def test_bool_is_not_mutated(self):
        self.assertEqual(mutate.candidates("x = True\ny = False\n", "m.py"), [])

    def test_docstring_and_annotation_not_mutated(self):
        src = 'def f(a: "x" = 1) -> int:\n    """doc 5"""\n    return a\n'
        self.assertEqual([m.operator for m, _ in mutate.candidates(src, "m.py")], ["const"])

    def test_chained_compare_one_mutant(self):
        self.assertEqual(len(mutate.candidates("y = a < b < c\n", "m.py")), 1)

    def test_augassign_not_arith(self):
        self.assertEqual(mutate.candidates("x += y\n", "m.py"), [])

    def test_sample_cap_zero(self):
        self.assertEqual(mutate.sample([1, 2], 0), [])

    def test_null_bytes_source(self):
        self.assertEqual(mutate.candidates("x = 1\x00", "m.py"), [])


class ScoreEdges(unittest.TestCase):
    def _project(self, code="x = 1\n"):
        d = tmp(self)
        (d / "src").mkdir()
        (d / "src" / "a.py").write_text(code, encoding="utf-8")
        return d

    def test_crlf_file_restored_byte_identical(self):
        d = self._project()
        raw = b"def f():\r\n    return 1 + 2\r\n"
        (d / "src" / "a.py").write_bytes(raw)
        cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]
        mutate.score(d, ["src/a.py"], {"agents": [cmd]})
        self.assertEqual((d / "src" / "a.py").read_bytes(), raw)

    def test_missing_file_raises_mutation_error(self):
        d = self._project()
        with self.assertRaises(mutate.MutationError):
            mutate.score(d, ["src/nope.py"], {"agents": [[sys.executable, "-c", "pass"]]})

    def test_non_utf8_file_raises_mutation_error(self):
        d = self._project()
        (d / "src" / "a.py").write_bytes(b"x = '\xff'\n")
        with self.assertRaises(mutate.MutationError):
            mutate.score(d, ["src/a.py"], {"agents": [[sys.executable, "-c", "pass"]]})

    def test_missing_executable_is_red_baseline(self):
        d = self._project()
        r = mutate.score(d, ["src/a.py"], {"agents": [["/no/such/binary"]]})
        self.assertIsNone(r["killed"])
        self.assertEqual(r["survived"], [])

    def test_all_commands_must_pass_second_failing_kills(self):
        d = self._project()
        ok = [sys.executable, "-c", "pass"]
        check = [sys.executable, "-c", "import sys; sys.path.insert(0,'src'); import a; sys.exit(a.x != 1)"]
        r = mutate.score(d, ["src/a.py"], {"agents": [ok, check]}, env={})
        self.assertEqual((r["total"], r["killed"]), (1, 1))

    def test_d1_empty_command_list_is_not_a_measurement(self):
        # a suite with no commands trivially "passes": every mutant survives and the score reads 0.0
        d = self._project()
        r = mutate.score(d, ["src/a.py"], {"agents": []})
        self.assertIsNone(r["killed"])


class WiringEdges(unittest.TestCase):
    def test_production_files_excludes_tests_acceptance_qa(self):
        d = tmp(self)
        for rel in ("src/a.py", "src/test_a.py", "tests/t.py", "acceptance/x.py", "qa/q.py", "pkg/__init__.py"):
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text("x = 1\n", encoding="utf-8")
        manifest = {"work_packages": [{"files": ["src", "tests", "qa", "pkg", "ghost.py"]}],
                    "acceptance": {"files": ["acceptance/"]}}
        self.assertEqual(bench.production_files(d, manifest), ["pkg/__init__.py", "src/a.py"])

    def test_d2_production_files_must_stay_inside_project(self):
        d = tmp(self)
        project = d / "p"
        project.mkdir()
        (d / "outside.py").write_text("x = 1\n", encoding="utf-8")
        manifest = {"work_packages": [{"files": ["../outside.py"]}]}
        self.assertEqual(bench.production_files(project, manifest), [])

    def test_d3_unbalanced_quote_in_command_does_not_raise(self):
        # the manifest lives in a file the agents can edit; a run is never lost to its instrument
        d = tmp(self)
        (d / "a.py").write_text("x = 1\n", encoding="utf-8")
        (d / "architecture.md").write_text(
            '```json wp-manifest\n{"work_packages": [{"files": ["a.py"]}], "verify": {"tests": "python3 -c \'x"}}\n```\n',
            encoding="utf-8")
        fx = tmp(self)
        (fx / "oracle").mkdir()
        try:
            bench._mutation(fx, d, {})
        except ValueError as e:
            self.fail(f"_mutation raised {e!r}")

    def test_no_manifest_gives_no_block(self):
        d = tmp(self)
        fx = tmp(self)
        self.assertIsNone(bench._mutation(fx, d, {}))


if __name__ == "__main__":
    unittest.main()
