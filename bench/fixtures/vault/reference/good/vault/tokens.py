"""Download tokens."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac


class InvalidToken(Exception):
    """The token is expired, foreign or malformed."""


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(text: str) -> bytes:
    if not text.isascii() or not text.replace("-", "").replace("_", "").isalnum():
        raise InvalidToken("bad encoding")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError) as error:
        raise InvalidToken("bad encoding") from error


def _mac(secret: bytes, payload: bytes) -> bytes:
    return hmac.new(secret, payload, hashlib.sha256).digest()


def issue(secret: bytes, file_id: str, expires_at: int) -> str:
    """A token that carries `file_id` and `expires_at`."""
    if not secret:
        raise ValueError("empty secret")
    if not file_id or not file_id.isascii() or any(c.isspace() for c in file_id):
        raise ValueError("invalid file id")
    payload = f"{file_id}:{expires_at}".encode("ascii")
    return f"{_encode(payload)}.{_encode(_mac(secret, payload))}"


def verify(secret: bytes, token: str, now: int) -> str:
    """The file id of a valid, unexpired token; InvalidToken otherwise."""
    parts = token.split(".")
    if len(parts) != 2:
        raise InvalidToken("bad layout")
    payload = _decode(parts[0])
    if not hmac.compare_digest(_decode(parts[1]), _mac(secret, payload)):
        raise InvalidToken("bad proof")
    file_id, _, expires = payload.decode("ascii", "replace").rpartition(":")
    try:
        expires_at = int(expires)
    except ValueError as error:
        raise InvalidToken("bad expiry") from error
    if now >= expires_at:
        raise InvalidToken("expired")
    return file_id
