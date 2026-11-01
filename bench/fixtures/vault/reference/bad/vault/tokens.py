"""Download tokens."""
from __future__ import annotations

import base64
import binascii


class InvalidToken(Exception):
    """The token is expired or malformed."""


def issue(secret: bytes, file_id: str, expires_at: int) -> str:
    """A token that carries `file_id` and `expires_at`."""
    if not secret:
        raise ValueError("empty secret")
    if not file_id or not file_id.isascii() or any(c.isspace() for c in file_id):
        raise ValueError("invalid file id")
    return base64.urlsafe_b64encode(f"{file_id}:{expires_at}".encode("ascii")).decode("ascii").rstrip("=")


def verify(secret: bytes, token: str, now: int) -> str:
    """The file id of a valid, unexpired token; InvalidToken otherwise."""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("ascii")
        file_id, _, expires = raw.rpartition(":")
        expires_at = int(expires)
    except (binascii.Error, ValueError) as error:
        raise InvalidToken("bad token") from error
    if now >= expires_at:
        raise InvalidToken("expired")
    return file_id
