"""Helpers for the flow's tests that must work on every system: fake executables and the fake `claude` command.

Used by test_agentic.py, test_pipeline.py, test_acceptance*.py. On Windows a script with a shebang cannot be run
directly, so a fake program is a `.py` file with a `.cmd` beside it; on POSIX it is an executable script.
"""
import shlex
import sys
from pathlib import Path

import compat


def fake_exe(directory, name: str, python_source: str) -> Path:
    """An executable `name` that can be found on PATH (with `directory` on it) and runs python_source with this
    interpreter. Returns the path of the program to run. For project commands in tests, not for `claude`."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if compat.IS_WINDOWS:
        (directory / f"{name}.py").write_text(python_source, encoding="utf-8")
        cmd = directory / f"{name}.cmd"
        cmd.write_text(f'@"{sys.executable}" "%~dp0{name}.py" %*\r\n', encoding="utf-8")
        return cmd
    script = directory / name
    script.write_text(f"#!{sys.executable}\n{python_source}", encoding="utf-8")
    script.chmod(0o755)
    return script


def claude_command(fake_py) -> str:
    """The AGENTIC_CLAUDE value that runs the Python file fake_py with this interpreter."""
    return shlex.join([Path(sys.executable).as_posix(), Path(fake_py).as_posix()])
