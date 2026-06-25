"""Authentication module for SEOOptimizer.

Provides user registration, login, and password-reset functionality
backed by a TinyDB store, along with a Streamlit-based UI.
"""

from auth.user_auth import (
    authenticate_user,
    hash_password,
    register_user,
    reset_password,
    verify_password,
)

__all__ = [
    "authenticate_user",
    "hash_password",
    "register_user",
    "reset_password",
    "verify_password",
]
