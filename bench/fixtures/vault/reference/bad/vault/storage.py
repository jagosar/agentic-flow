"""Where an upload is kept."""
from __future__ import annotations

import os


def upload_path(base: str, name: str) -> str:
    """Absolute path of the upload `name` inside `base`."""
    if not name.strip():
        raise ValueError("empty name")
    return os.path.abspath(os.path.join(base, name))
