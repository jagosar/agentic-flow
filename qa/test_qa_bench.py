"""QA edge-case tests for bench/bench.py. Run: python3 -m unittest discover -s qa -p "test_qa_*.py"
Tests named test_dN_ reproduce defect N found by QA; the review tests cover two findings of the code review."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench" / "bench.py"
spec = importlib.util.spec_from_file_location("bench_module", BENCH)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def tmp(case):
    d = tempfile.TemporaryDirectory()
    case.addCleanup(d.cleanup)
    return Path(d.name)


class OracleSpoofTests(unittest.TestCase):
    def _count(self, body):
        d = tmp(self)
        (d / "proj").mkdir()
        (d / "oracle").mkdir()
        (d / "oracle" / "test_x.py").write_text(body, encoding="utf-8")
        return bench.oracle_counts(d / "proj", d / "oracle")

    def test_plain_counts(self):
        body = "import unittest\nclass T(unittest.TestCase):\n def test_a(self): pass\n def test_b(self): self.fail()\n"
        self.assertEqual(self._count(body), (1, 2))

    def test_d1_stderr_spoof_of_summary(self):
        body = ("import sys, unittest\nsys.stderr.write('Ran 100 tests\\nOK\\n')\n"
                "class T(unittest.TestCase):\n def test_b(self): self.fail()\n")
        self.assertEqual(self._count(body), (0, 1))

    def test_import_error_is_one_error(self):
        self.assertEqual(self._count("import nonexistent_mod_zz\n"), (0, 1))


class MalformedResultTests(unittest.TestCase):
    def test_d2_malformed_usage_does_not_raise(self):
        for bad in ({"usage": "x"}, {"usage": {"total": 5}}, {"usage": {"by_agent": 3}}, {"test_audit": 5}):
            try:
                bench._record(Path("f"), 1, "OK", bad, 1.0, {"passed": 0, "total": 0})
            except (AttributeError, TypeError) as e:
                self.fail(f"_record raised {e!r} for {bad}")


class ReportTests(unittest.TestCase):
    def _doc(self, **kw):
        doc = {"schema": 1, "flow_version": "1.0", "flow_commit": "abc1234", "dirty": False,
               "started": "2026-01-02T03:04:05",
               "summary": {"b": {"runs": 1, "ok": 1, "oracle_rate_median": 1.0, "oracle_rate_min": 1.0,
                                 "oracle_rate_max": 1.0, "fix_cycles_median": None, "cost_usd_median": 3.1,
                                 "output_median": 4.0, "minutes_median": 13.5}}}
        doc.update(kw)
        return doc

    def test_format_nulls_and_order(self):
        d = tmp(self)
        (d / "r").mkdir()
        (d / "r" / "a.json").write_text(json.dumps(self._doc(dirty=True)), encoding="utf-8")
        (d / "r" / "b.json").write_text(json.dumps(self._doc(started="2027-01-01T00:00:00")), encoding="utf-8")
        (d / "r" / "c.json").write_text("[1]", encoding="utf-8")
        bench.report(d / "r", d / "R.md")
        rows = [x for x in (d / "R.md").read_text(encoding="utf-8").splitlines() if x.startswith("| 1.0")]
        self.assertEqual(len(rows), 2)
        self.assertIn("2027-01-01", rows[0])
        self.assertIn("abc1234-dirty", rows[1])
        self.assertIn("| ? | 3.10 | 4 | 13.5 |", rows[0])

    def test_d3_missing_dir_and_broken_summary(self):
        d = tmp(self)
        bench.report(d / "nope", d / "R.md")
        self.assertIn("No results yet.", (d / "R.md").read_text(encoding="utf-8"))
        (d / "r").mkdir()
        (d / "r" / "a.json").write_text(json.dumps(self._doc(summary={"x": 5})), encoding="utf-8")
        bench.report(d / "r", d / "R.md")


class CliTests(unittest.TestCase):
    def _cli(self, *args):
        return subprocess.run([sys.executable, str(BENCH), *args], capture_output=True, text=True,
                              encoding="utf-8", cwd=tmp(self))

    def test_bad_args_exit_1_no_traceback(self):
        for args in (["run", "--repeat", "abc"], ["run", "--timeout-min", "x"], ["bogus"], []):
            p = self._cli(*args)
            self.assertEqual(p.returncode, 1, args)
            self.assertNotIn("Traceback", p.stderr)

    def test_missing_fixture_parts(self):
        d = tmp(self)
        (d / "fx").mkdir()
        with self.assertRaises(bench.BenchError):
            bench.run([d / "fx"], ROOT, 1, d / "o")
        self.assertFalse((d / "o").exists())



class ReviewFindingTests(unittest.TestCase):
    def _source(self):
        d = tmp(self)
        src = d / "src"
        (src / ".claude" / "bin").mkdir(parents=True)
        (src / ".claude" / "bin" / "agentic.py").write_text("", encoding="utf-8")
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
        subprocess.run(["git", "init", "-q"], cwd=src, check=True)
        subprocess.run(git + ["add", "-A"], cwd=src, check=True)
        subprocess.run(git + ["commit", "-qm", "i"], cwd=src, check=True)
        return src

    def test_bench_output_does_not_make_the_source_dirty(self):
        src = self._source()
        (src / "bench" / "results").mkdir(parents=True)
        (src / "bench" / "results" / "1.0-x.json").write_text("{}", encoding="utf-8")
        (src / "bench" / "RESULTS.md").write_text("# Bench results\n", encoding="utf-8")
        self.assertFalse(bench._is_dirty(src))
        (src / "other.py").write_text("x = 1\n", encoding="utf-8")
        self.assertTrue(bench._is_dirty(src))

    def test_timeout_must_be_positive(self):
        for value in ("0", "-5"):
            p = subprocess.run([sys.executable, str(BENCH), "run", "--timeout-min", value, "--out", str(tmp(self))],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(p.returncode, 1, value)
            self.assertIn("timeout", p.stderr)

if __name__ == "__main__":
    unittest.main()
