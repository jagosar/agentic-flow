"""Where an upload is kept."""
from __future__ import annotations

import os


def upload_path(base: str, name: str) -> str:
    """Absolute path of the upload `name` inside `base`; ValueError if it would not be strictly inside."""
    if not name.strip():
        raise ValueError("empty name")
    if "\0" in name:
        raise ValueError("NUL byte in name")
    text = name.replace("\\", "/")
    if text.startswith("/"):
        raise ValueError("absolute name")
    parts = [part for part in text.split("/") if part]
    if not parts or any(part in (".", "..") for part in parts):
        raise ValueError("name leaves its folder")
    root = os.path.abspath(base)
    path = os.path.join(root, *parts)
    if not _is_strictly_inside(root, path):
        raise ValueError("name leaves the base directory")
    return path


def _is_strictly_inside(root: str, path: str) -> bool:
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(path)
    try:
        common = os.path.commonpath([real_root, real_path])
    except ValueError:
        return False
    return common == real_root and real_path != real_root
