"""Shared error model.

Backend modules raise :class:`AppError` with a machine-readable :class:`ErrorKind`
instead of a human string, so the UI layer is free to render the message in any
language. The optional ``detail`` carries technical context (an HTTP status, an
exception message) that is useful in logs and appended to user-facing text for
the "something unexpected" kinds.
"""

from __future__ import annotations

from enum import Enum


class ErrorKind(Enum):
    """A localizable category of failure."""

    COOKIE_UNAVAILABLE = "cookie_unavailable"  # desktop app / cookie / keychain missing
    DECRYPT_FAILED = "decrypt_failed"  # cookie found but could not be decrypted
    SESSION_EXPIRED = "session_expired"  # cookie present but rejected (HTTP 401)
    NO_SUBSCRIPTION = "no_subscription"  # account has no Claude subscription org
    NETWORK = "network"  # could not reach claude.ai
    SERVER = "server"  # unexpected HTTP status or malformed response
    UNKNOWN = "unknown"  # anything not anticipated


class AppError(Exception):
    """An error with a localizable :class:`ErrorKind` and optional detail."""

    def __init__(self, kind: ErrorKind, detail: str = "") -> None:
        super().__init__(detail or kind.value)
        self.kind = kind
        self.detail = detail
