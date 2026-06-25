"""User authentication module backed by TinyDB.

Provides password hashing (SHA-256 with random salt), user registration,
authentication, and password reset — all stored in a local TinyDB file at
``auth/users.json``.
"""

import hashlib
import os
from pathlib import Path
from typing import Tuple

from tinydb import TinyDB, Query

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

_DB_PATH = Path(__file__).resolve().parent / "users.json"
_db_instance = None  # singleton TinyDB instance


def _get_db() -> TinyDB:
    """Return a singleton :class:`TinyDB` instance, creating it if needed."""
    global _db_instance
    if _db_instance is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _db_instance = TinyDB(str(_DB_PATH))
    return _db_instance


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash *password* with a random 16-byte hex salt using SHA-256.

    Returns a ``"salt$hash"`` string suitable for :func:`verify_password`.
    """
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password: str, stored: str) -> bool:
    """Verify *password* against a ``"salt$hash"`` string from :func:`hash_password`.

    Returns ``True`` if the password matches, ``False`` otherwise.
    """
    if "$" not in stored:
        return False
    salt, expected = stored.split("$", 1)
    actual = hashlib.sha256((salt + password).encode()).hexdigest()
    return actual == expected


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------


def register_user(username: str, password: str) -> Tuple[bool, str]:
    """Register a new user.

    Args:
        username: Desired username (min 3 characters after stripping).
        password: Desired password (min 6 characters).

    Returns:
        ``(True, "Success")`` on success, or ``(False, "Error message")`` on
        failure (empty/short username, short password, duplicate user).
    """
    # --- username validation ---
    if not username or not username.strip():
        return False, "Username cannot be empty."
    username = username.strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters long."

    # --- password validation ---
    if not password:
        return False, "Password cannot be empty."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."

    # --- duplicate check ---
    db = _get_db()
    User = Query()
    if db.search(User.username == username):
        return False, "Username already exists."

    # --- store ---
    pw_hash = hash_password(password)
    db.insert({"username": username, "password_hash": pw_hash})
    return True, "Success"


def authenticate_user(username: str, password: str) -> bool:
    """Authenticate *username* with *password*.

    Checks TinyDB first (registered users).  Falls back to
    ``AUTH_USERNAME`` / ``AUTH_PASSWORD`` environment variables
    (for Heroku deployment where the filesystem is ephemeral).

    Returns ``True`` if the credentials are valid, ``False`` otherwise.
    """
    if not username or not password:
        return False
    username = username.strip()

    # 1. Check TinyDB (users registered during the session)
    db = _get_db()
    User = Query()
    results = db.search(User.username == username)
    if results:
        return verify_password(password, results[0]["password_hash"])

    # 2. Fallback to env vars (for Heroku deployment)
    env_user = os.environ.get("AUTH_USERNAME", "").strip()
    env_pass = os.environ.get("AUTH_PASSWORD", "")
    if env_user and env_pass:
        return username == env_user and password == env_pass

    return False


def reset_password(
    username: str,
    old_password: str,
    new_password: str,
) -> Tuple[bool, str]:
    """Reset the password for *username*.

    Verifies *old_password* first, then sets *new_password*.

    Returns:
        ``(True, "Success")`` on success, or ``(False, "Error message")`` on
        failure (wrong old password, short new password).
    """
    # --- validate new password ---
    if not new_password or len(new_password) < 6:
        return False, "New password must be at least 6 characters long."

    # --- verify old credentials ---
    if not authenticate_user(username, old_password):
        return False, "Invalid username or password."

    # --- update ---
    username = username.strip()
    db = _get_db()
    User = Query()
    new_hash = hash_password(new_password)
    db.update({"password_hash": new_hash}, User.username == username)
    return True, "Success"
