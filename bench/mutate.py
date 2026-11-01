"""Mutation score for the bench: single-point mutants of Python sources, run against test commands.

Standard library only. `candidates` and `sample` are pure; `score` writes each mutant over the real file, runs the
suites and always restores the original bytes."""
from __future__ import annotations

import ast
import copy
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / ".claude" / "bin"))
import compat  # noqa: E402

OPERATORS = ("compare", "arith", "boolop", "not", "const")
MUTANTS_MAX = 40
MUTANT_TIMEOUT_S = 120
COMPARE_SWAPS = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq,
                 ast.NotEq: ast.Eq}
ARITH_SWAPS = {ast.Add: ast.Sub, ast.Sub: ast.Add}
BOOLOP_SWAPS = {ast.And: ast.Or, ast.Or: ast.And}
SYMBOLS = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=", ast.Add: "+",
           ast.Sub: "-", ast.And: "and", ast.Or: "or"}
BYTECODE_OFF = {"PYTHONDONTWRITEBYTECODE": "1"}
DOC_OWNERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


class MutationError(Exception):
    """A production file could not be read or written back."""


class Mutant(NamedTuple):
    # a NamedTuple, not a dataclass: the bench loads this module by path without registering it in sys.modules
    file: str
    line: int
    operator: str
    description: str


def _skipped_constants(tree: ast.AST) -> set:
    """ids of the nodes whose int literals must not be mutated: docstrings and annotations."""
    skipped = set()
    for node in ast.walk(tree):
        if isinstance(node, DOC_OWNERS) and node.body and isinstance(node.body[0], ast.Expr):
            skipped.update(id(n) for n in ast.walk(node.body[0]))
        annotations = []
        if isinstance(node, ast.arg):
            annotations.append(node.annotation)
        elif isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotations.append(node.returns)
        for annotation in annotations:
            if annotation is not None:
                skipped.update(id(n) for n in ast.walk(annotation))
    return skipped


def _found(node: ast.AST, skipped: set) -> list[tuple[int, str, str]]:
    """The (operator index, operator, description) mutations that apply to this node."""
    if isinstance(node, ast.Compare) and type(node.ops[0]) in COMPARE_SWAPS:
        old = type(node.ops[0])
        return [(0, "compare", f"{SYMBOLS[old]} -> {SYMBOLS[COMPARE_SWAPS[old]]}")]
    if isinstance(node, ast.BinOp) and type(node.op) in ARITH_SWAPS:
        old = type(node.op)
        return [(1, "arith", f"{SYMBOLS[old]} -> {SYMBOLS[ARITH_SWAPS[old]]}")]
    if isinstance(node, ast.BoolOp):
        old = type(node.op)
        return [(2, "boolop", f"{SYMBOLS[old]} -> {SYMBOLS[BOOLOP_SWAPS[old]]}")]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return [(3, "not", "drop not")]
    is_int = isinstance(node, ast.Constant) and type(node.value) is int
    if is_int and id(node) not in skipped:
        return [(4, "const", f"{node.value} -> {node.value + 1}")]
    return []


def _replace_child(nodes: list, target: ast.AST, new: ast.AST) -> None:
    for parent in nodes:
        for field, value in ast.iter_fields(parent):
            if value is target:
                setattr(parent, field, new)
                return
            if isinstance(value, list) and any(item is target for item in value):
                value[:] = [new if item is target else item for item in value]
                return


def _apply(tree: ast.AST, index: int, operator: str) -> str:
    """Source of a copy of the tree with only the node at walk position `index` mutated."""
    clone = copy.deepcopy(tree)
    nodes = list(ast.walk(clone))
    target = nodes[index]
    if operator == "compare":
        target.ops[0] = COMPARE_SWAPS[type(target.ops[0])]()
    elif operator == "arith":
        target.op = ARITH_SWAPS[type(target.op)]()
    elif operator == "boolop":
        target.op = BOOLOP_SWAPS[type(target.op)]()
    elif operator == "not":
        _replace_child(nodes, target, target.operand)
    else:
        target.value += 1
    return ast.unparse(ast.fix_missing_locations(clone))


def candidates(source: str, file: str) -> list[tuple[Mutant, str]]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    skipped = _skipped_constants(tree)
    found = []
    for index, node in enumerate(ast.walk(tree)):
        for order, operator, description in _found(node, skipped):
            found.append((node.lineno, node.col_offset, order, index, operator, description))
    found.sort(key=lambda item: item[:4])
    return [(Mutant(file, line, operator, description), _apply(tree, index, operator))
            for line, _col, _order, index, operator, description in found]


def sample(items: list, cap: int) -> list:
    if len(items) <= cap:
        return list(items)
    return [items[i * len(items) // cap] for i in range(cap)]


def _run_suite(commands: list[list[str]], project: Path, env: dict, timeout_s: float) -> tuple[bool, bool]:
    """(passed, timed_out): passed only when every command exits 0."""
    for argv in commands:
        try:
            proc = subprocess.Popen(compat.resolve(argv), cwd=project, env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **compat.group_kwargs())
        except OSError:
            return False, False
        try:
            proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            compat.kill_tree(proc.pid)
            proc.communicate()
            return False, True
        if proc.returncode != 0:
            return False, False
    return True, False


def _drop_bytecode(path: Path) -> None:
    for pyc in (path.parent / "__pycache__").glob(f"{path.stem}.*.pyc"):
        try:
            pyc.unlink()
        except OSError:
            pass


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as err:
        raise MutationError(f"cannot read {path.name}: {err}") from err


def _all_mutants(project: Path, files: list[str]) -> list[tuple[Mutant, str]]:
    found = []
    for file in files:
        try:
            source = _read(project / file).decode("utf-8")
        except UnicodeDecodeError as err:
            raise MutationError(f"cannot decode {file}: {err}") from err
        found.extend(candidates(source, file))
    return found


def _try_mutant(project: Path, mutant: Mutant, mutated: str, original: bytes) -> None:
    """Writes the mutant over its file; the caller runs the suites and calls _restore."""
    path = project / mutant.file
    _drop_bytecode(path)
    try:
        path.write_text(mutated, encoding="utf-8")
    except OSError as err:
        raise MutationError(f"cannot write {mutant.file}: {err}") from err


def _restore(path: Path, original: bytes) -> None:
    try:
        path.write_bytes(original)
    except OSError as err:
        raise MutationError(f"cannot restore {path.name}: {err}") from err
    finally:
        _drop_bytecode(path)


def score(project: Path, files: list[str], suites: dict[str, list[list[str]]], cap: int = MUTANTS_MAX,
          timeout_s: float = MUTANT_TIMEOUT_S, env: dict | None = None) -> dict | None:
    project = Path(project)
    run_env = {**(os.environ if env is None else env), **BYTECODE_OFF}
    chosen = sample(_all_mutants(project, files), cap)
    if not chosen:
        return None
    # A suite with no commands measures nothing; a suite that is red before any mutant measures nothing either.
    live = {name: commands for name, commands in suites.items()
            if commands and _run_suite(commands, project, run_env, timeout_s)[0]}
    killed = {name: 0 for name in live}
    survived = []
    timeouts = 0
    for mutant, mutated in chosen:
        path = project / mutant.file
        original = _read(path)
        try:
            _try_mutant(project, mutant, mutated, original)
            results = {name: _run_suite(commands, project, run_env, timeout_s) for name, commands in live.items()}
        finally:
            _restore(path, original)
        timeouts += any(timed_out for _passed, timed_out in results.values())
        for name, (passed, _timed_out) in results.items():
            killed[name] += not passed
        if "agents" in results and results["agents"][0]:
            survived.append(mutant._asdict())
    return {"total": len(chosen), "killed": killed.get("agents"), "oracle_killed": killed.get("oracle"),
            "timeouts": timeouts, "survived": survived}
