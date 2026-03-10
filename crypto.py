"""
crypto.py — Fernet field encryption with Windows DPAPI key protection.

On first run a random Fernet key is generated and protected with Windows DPAPI
(tied to the current Windows user account). The encrypted key blob is stored in
`patchreport.key` alongside the database. On subsequent runs the blob is loaded
and DPAPI-decrypted to recover the key.

On non-Windows platforms (Linux dev environment) encryption is skipped and
plaintext is returned unchanged — so the app runs normally during development.

Decryption gracefully handles plaintext values (pre-encryption legacy data):
if Fernet raises InvalidToken the original string is returned as-is, so
existing databases continue to work and fields are silently re-encrypted on
next write.
"""

import os
from pathlib import Path

from constants import DB_FILE

_KEY_FILE = str(Path(DB_FILE).with_suffix(".key"))
_fernet = None   # initialised once by _init()
_ready  = False  # True once _init() has run (even if unavailable)


def _init():
    global _fernet, _ready
    if _ready:
        return
    _ready = True

    try:
        from cryptography.fernet import Fernet
        import win32crypt  # type: ignore
    except ImportError:
        # Non-Windows dev environment or missing cryptography package —
        # encryption unavailable; app continues with plaintext.
        return

    try:
        if os.path.exists(_KEY_FILE):
            with open(_KEY_FILE, "rb") as f:
                protected = f.read()
            raw_key = win32crypt.CryptUnprotectData(
                protected, None, None, None, 0
            )[1]
        else:
            from cryptography.fernet import Fernet
            raw_key  = Fernet.generate_key()
            protected = win32crypt.CryptProtectData(
                raw_key, "PatchReporter DB Key", None, None, None, 0
            )
            with open(_KEY_FILE, "wb") as f:
                f.write(protected)

        from cryptography.fernet import Fernet
        _fernet = Fernet(raw_key)
    except Exception as exc:
        # If anything goes wrong (e.g. DPAPI unavailable, corrupt key file)
        # log a warning and continue without encryption rather than crashing.
        import sys
        print(f"[crypto] WARNING: encryption unavailable — {exc}", file=sys.stderr)


def encrypt(text: str) -> str:
    """Return the Fernet-encrypted form of `text`, or `text` unchanged if
    encryption is unavailable (dev environment / missing dependency)."""
    _init()
    if _fernet is None or not text:
        return text
    return _fernet.encrypt(text.encode()).decode()


def decrypt(text: str) -> str:
    """Return the decrypted form of `text`.  If `text` is legacy plaintext
    (pre-encryption data) the InvalidToken exception is caught and the
    original string is returned so existing records continue to work."""
    _init()
    if _fernet is None or not text:
        return text
    try:
        return _fernet.decrypt(text.encode()).decode()
    except Exception:
        return text  # Legacy plaintext — pass through unchanged
