"""A variant of this checkout's flow, built in a folder, for an A/B run of the bench (`bench.py ab --b <folder>`).

The variant is applied at build time to a copy, so it never drifts from the definitions it changes and the checkout
is never touched. Each variant names exactly what it removes; a definition that no longer has it is an error, so a
variant never builds half-applied.

    python3 bench/variant.py NAME DST

Variants:
  implementer-no-standards   the implementer without the coding standards: no rules in its prompt
                             (constants.implementer_rules false), no "# Before writing" section, and a rule 4
                             that only asks for section 7 and the existing style.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parent.parent
SPEC = Path(".claude/workflows/pipeline-spec.json")
IMPLEMENTER = Path(".claude/agents/implementer.md")
SECTION_RE = re.compile(r"^# Before writing\n.*?(?=^# )", re.M | re.S)
CONVENTIONS_RE = re.compile(r"^\d+\. \*\*Conventions\.\*\*.*$", re.M)
CONVENTIONS = "4. **Conventions.** Follow section 7 and the style of the existing code."
USAGE = "Uso: variant.py NAME DST"


def implementer_no_standards(dst):
    spec_path = dst / SPEC
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["constants"]["implementer_rules"] = False
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    path = dst / IMPLEMENTER
    text = path.read_text(encoding="utf-8")
    if not SECTION_RE.search(text) or len(CONVENTIONS_RE.findall(text)) != 1:
        raise ValueError(f"{IMPLEMENTER} has no '# Before writing' section or no single Conventions rule")
    text = CONVENTIONS_RE.sub(lambda m: CONVENTIONS, SECTION_RE.sub("", text, count=1), count=1)
    path.write_text(text, encoding="utf-8")


VARIANTS = {"implementer-no-standards": implementer_no_standards}


def listed_files(src):
    """The files git would keep: tracked or new, never ignored (so .claude/state/ stays out)."""
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=src,
                         capture_output=True, check=True).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p and (Path(src) / p).is_file()]


def build(name, dst, src=CHECKOUT):
    """Copies src's files to dst (which must not exist), applies the variant and returns dst."""
    if name not in VARIANTS:
        raise ValueError(f"unknown variant: {name} (known: {', '.join(sorted(VARIANTS))})")
    dst, src = Path(dst), Path(src)
    if dst.exists():
        raise ValueError(f"{dst} already exists")
    for rel in listed_files(src):
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, target)
    VARIANTS[name](dst)
    return dst


def main(argv):
    if len(argv) != 2:
        print(USAGE, file=sys.stderr)
        return 1
    try:
        print(build(argv[0], argv[1]))
    except ValueError as e:
        print(f"{USAGE}\n{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
