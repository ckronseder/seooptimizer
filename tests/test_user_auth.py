"""Tests for the ``auth.user_auth`` module.

Covers password hashing, user registration, authentication, and password
reset — all backed by a temporary TinyDB file injected via monkeypatching.
"""

import pytest
from tinydb import TinyDB

from auth import user_auth


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _temp_db(monkeypatch, tmp_path):
    """Replace the production TinyDB with a temporary file for every test."""
    test_db_path = tmp_path / "test_users.json"
    test_db = TinyDB(str(test_db_path))

    # Inject the test DB into the module so all functions use it.
    monkeypatch.setattr(user_auth, "_get_db", lambda: test_db)

    yield  # run the test

    test_db.close()


# ============================================================================
# hash_password & verify_password
# ============================================================================


class TestPasswordHashing:
    """``hash_password`` and ``verify_password`` contract."""

    def test_hash_returns_salt_hash_format(self) -> None:
        """The returned string must contain a single ``$`` separator."""
        hashed = user_auth.hash_password("secret123")
        assert "$" in hashed
        parts = hashed.split("$")
        assert len(parts) == 2
        # salt is 32 hex characters (16 bytes → 32 hex chars)
        assert len(parts[0]) == 32
        # hash is 64 hex characters (SHA-256)
        assert len(parts[1]) == 64

    def test_verify_correct_password(self) -> None:
        """``verify_password`` must return ``True`` for the matching password."""
        hashed = user_auth.hash_password("my_password")
        assert user_auth.verify_password("my_password", hashed) is True

    def test_verify_wrong_password(self) -> None:
        """``verify_password`` must return ``False`` for an incorrect password."""
        hashed = user_auth.hash_password("correct_pw")
        assert user_auth.verify_password("wrong_pw", hashed) is False

    def test_verify_invalid_format(self) -> None:
        """``verify_password`` returns ``False`` for a malformed stored string."""
        assert user_auth.verify_password("pw", "not-a-valid-format") is False

    def test_different_salts(self) -> None:
        """Two hashes of the same password must differ (different salts)."""
        h1 = user_auth.hash_password("same_password")
        h2 = user_auth.hash_password("same_password")
        assert h1 != h2


# ============================================================================
# register_user
# ============================================================================


class TestRegisterUser:
    """``register_user`` validation and storage."""

    def test_register_valid_user(self) -> None:
        """A valid username and password must succeed."""
        ok, msg = user_auth.register_user("alice", "secure123")
        assert ok is True
        assert msg == "Success"

    def test_register_duplicate_username(self) -> None:
        """Registering the same username twice must fail."""
        user_auth.register_user("bob", "password1")
        ok, msg = user_auth.register_user("bob", "password2")
        assert ok is False
        assert "already exists" in msg.lower()

    def test_register_empty_username(self) -> None:
        """Empty or whitespace-only username must be rejected."""
        ok, msg = user_auth.register_user("", "password123")
        assert ok is False
        assert "empty" in msg.lower()

        ok, msg = user_auth.register_user("   ", "password123")
        assert ok is False
        assert "empty" in msg.lower()

    def test_register_short_username(self) -> None:
        """Username shorter than 3 characters must be rejected."""
        ok, msg = user_auth.register_user("ab", "password123")
        assert ok is False
        assert "at least 3" in msg.lower()

    def test_register_empty_password(self) -> None:
        """Empty password must be rejected."""
        ok, msg = user_auth.register_user("charlie", "")
        assert ok is False
        assert "empty" in msg.lower()

    def test_register_short_password(self) -> None:
        """Password shorter than 6 characters must be rejected."""
        ok, msg = user_auth.register_user("charlie", "12345")
        assert ok is False
        assert "at least 6" in msg.lower()

    def test_register_strips_username(self) -> None:
        """Registration must strip leading/trailing whitespace from username."""
        ok, msg = user_auth.register_user("  dave  ", "password123")
        assert ok is True
        assert msg == "Success"

        # Should now authenticate with the stripped username
        assert user_auth.authenticate_user("dave", "password123") is True


# ============================================================================
# authenticate_user
# ============================================================================


class TestAuthenticateUser:
    """``authenticate_user`` credential verification."""

    def test_authenticate_correct_credentials(self) -> None:
        """Valid credentials must return ``True``."""
        user_auth.register_user("eve", "my_password")
        assert user_auth.authenticate_user("eve", "my_password") is True

    def test_authenticate_wrong_password(self) -> None:
        """Wrong password must return ``False``."""
        user_auth.register_user("frank", "correct_pw")
        assert user_auth.authenticate_user("frank", "wrong_pw") is False

    def test_authenticate_nonexistent_user(self) -> None:
        """A username that was never registered must return ``False``."""
        assert user_auth.authenticate_user("nonexistent", "irrelevant") is False

    def test_authenticate_empty_input(self) -> None:
        """Empty username or password must return ``False``."""
        assert user_auth.authenticate_user("", "password") is False
        assert user_auth.authenticate_user("user", "") is False

    def test_authenticate_hardcoded_user_ck(self) -> None:
        """Hardcoded user 'ck' with password 'ck1234' must authenticate."""
        assert user_auth.authenticate_user("ck", "ck1234") is True

    def test_authenticate_hardcoded_user_seo(self) -> None:
        """Hardcoded user 'seo' with password 'seo1234' must authenticate."""
        assert user_auth.authenticate_user("seo", "seo1234") is True

    def test_authenticate_hardcoded_user_wrong_password(self) -> None:
        """Hardcoded user with wrong password must return ``False``."""
        assert user_auth.authenticate_user("ck", "wrong_password") is False

    def test_authenticate_hardcoded_user_case_sensitive(self) -> None:
        """Hardcoded username must be case-sensitive."""
        assert user_auth.authenticate_user("Ck", "ck1234") is False


# ============================================================================
# reset_password
# ============================================================================


class TestResetPassword:
    """``reset_password`` behaviour."""

    def test_reset_with_correct_old_password(self) -> None:
        """Resetting with the correct old password must succeed."""
        user_auth.register_user("grace", "old_pass1")
        ok, msg = user_auth.reset_password("grace", "old_pass1", "new_pass1")
        assert ok is True
        assert msg == "Success"

        # Old password should no longer work
        assert user_auth.authenticate_user("grace", "old_pass1") is False
        # New password should work
        assert user_auth.authenticate_user("grace", "new_pass1") is True

    def test_reset_with_wrong_old_password(self) -> None:
        """Resetting with an incorrect old password must fail."""
        user_auth.register_user("heidi", "real_pass")
        ok, msg = user_auth.reset_password("heidi", "wrong_pass", "new_pass1")
        assert ok is False
        assert "invalid" in msg.lower()

        # Original password must still work
        assert user_auth.authenticate_user("heidi", "real_pass") is True

    def test_reset_nonexistent_user(self) -> None:
        """Resetting for a user that doesn't exist must fail."""
        ok, msg = user_auth.reset_password("nobody", "any_pass", "new_pass1")
        assert ok is False
        assert "invalid" in msg.lower()

    def test_reset_short_new_password(self) -> None:
        """A new password shorter than 6 characters must be rejected."""
        user_auth.register_user("ivan", "valid_pass")
        ok, msg = user_auth.reset_password("ivan", "valid_pass", "short")
        assert ok is False
        assert "at least 6" in msg.lower()
