"""Read and decrypt the claude.ai sessionKey from the Claude desktop app.

The Claude desktop app is Electron/Chromium based, so its cookies live in a
SQLite store and the values are AES-128-CBC encrypted with a key kept in the
macOS Keychain (the same scheme Chrome uses). We never write to the store; it is
opened read-only.

This is unofficial: it relies on Chromium's on-disk format and on you being
logged into the Claude desktop app. If Anthropic changes either, this module is
the one to fix.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .errors import AppError, ErrorKind

COOKIE_DB = os.path.expanduser("~/Library/Application Support/Claude/Cookies")
KEYCHAIN_SERVICE = "Claude Safe Storage"

# Chromium's fixed PBKDF2 parameters for macOS cookie encryption.
_SALT = b"saltysalt"
_ITERATIONS = 1003
_KEY_LENGTH = 16
_IV = b" " * 16
_ENC_PREFIX = b"v10"
# Newer Chromium prepends a 32-byte SHA-256 domain hash to the decrypted value.
_DOMAIN_HASH_LENGTH = 32


def _keychain_password() -> bytes:
    """Fetch the 'Claude Safe Storage' key from the macOS Keychain.

    The first time an unsigned binary reads this, macOS shows an auth prompt;
    clicking "Always Allow" makes it silent afterwards.
    """
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-w", "-s", KEYCHAIN_SERVICE],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as e:
        raise AppError(ErrorKind.COOKIE_UNAVAILABLE, f"keychain read failed: {e}") from e
    password = result.stdout.strip()
    if not password:
        raise AppError(ErrorKind.COOKIE_UNAVAILABLE, "keychain item 'Claude Safe Storage' not found")
    return password.encode()


def _derive_key(password: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, _SALT, _ITERATIONS, dklen=_KEY_LENGTH)


def _decrypt(encrypted: bytes, key: bytes) -> str:
    """Decrypt one Chromium cookie value (expects the 'v10' prefix)."""
    if encrypted[: len(_ENC_PREFIX)] != _ENC_PREFIX:
        raise AppError(ErrorKind.DECRYPT_FAILED, f"unexpected prefix {encrypted[:3]!r}")
    decryptor = Cipher(algorithms.AES(key), modes.CBC(_IV)).decryptor()
    plain = decryptor.update(encrypted[len(_ENC_PREFIX):]) + decryptor.finalize()
    plain = plain[: -plain[-1]]  # strip PKCS#7 padding
    try:
        return plain.decode()
    except UnicodeDecodeError:
        return plain[_DOMAIN_HASH_LENGTH:].decode()


def _read_encrypted_session_key() -> bytes:
    if not os.path.exists(COOKIE_DB):
        raise AppError(ErrorKind.COOKIE_UNAVAILABLE, f"cookie store not found at {COOKIE_DB}")
    try:
        con = sqlite3.connect(f"file:{COOKIE_DB}?mode=ro", uri=True)
    except sqlite3.Error as e:
        raise AppError(ErrorKind.COOKIE_UNAVAILABLE, f"cannot open cookie store: {e}") from e
    try:
        row = con.execute(
            "SELECT encrypted_value FROM cookies "
            "WHERE host_key LIKE '%claude.ai%' AND name = 'sessionKey'"
        ).fetchone()
    finally:
        con.close()
    if not row:
        raise AppError(ErrorKind.SESSION_EXPIRED, "no claude.ai sessionKey cookie")
    return row[0]


def get_session_key() -> str:
    """Return the decrypted claude.ai sessionKey, or raise :class:`AppError`."""
    encrypted = _read_encrypted_session_key()
    key = _derive_key(_keychain_password())
    return _decrypt(encrypted, key)
