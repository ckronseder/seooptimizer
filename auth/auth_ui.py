"""Streamlit UI for user authentication (Login / Register / Password Reset).

Uses ``st.session_state.auth_page`` (default ``"login"``) to switch between
the three forms.  The :func:`show_login_page` function is designed to be
called from the main app entry point and returns the authenticated username
on success, or ``None`` otherwise.
"""

from typing import Optional

import streamlit as st

from auth.user_auth import authenticate_user, register_user, reset_password

# ---------------------------------------------------------------------------
# Page-switching helper
# ---------------------------------------------------------------------------


def _set_auth_page(page: str) -> None:
    """Switch the active auth page stored in session state."""
    st.session_state.auth_page = page


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def show_login_page() -> Optional[str]:
    """Render the authentication UI.

    The page shown is controlled by ``st.session_state.auth_page``:

    - ``"login"``    → :func:`_render_login`
    - ``"register"`` → :func:`_render_register`
    - ``"reset"``    → :func:`_render_reset`

    Returns:
        The authenticated *username* on successful login or registration,
        ``None`` otherwise.
    """
    # Ensure defaults
    if "auth_page" not in st.session_state:
        st.session_state.auth_page = "login"

    # Lightweight centred container styling (does not interfere with app CSS)
    st.markdown(
        """
        <style>
        .auth-container {
            max-width: 420px;
            margin: 2rem auto;
            padding: 2rem;
            border-radius: 12px;
            background: #1e1e1e;
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }
        .auth-title {
            text-align: center;
            font-size: 1.6rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            color: #f0f0f0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    page = st.session_state.auth_page
    if page == "login":
        return _render_login()
    if page == "register":
        return _render_register()
    if page == "reset":
        return _render_reset()
    return None


# ---------------------------------------------------------------------------
# Private form renderers
# ---------------------------------------------------------------------------


def _render_login() -> Optional[str]:
    """Render the **Login** form."""
    st.markdown(
        '<div class="auth-container">'
        '<div class="auth-title">🔐 SEO Optimizer</div>',
        unsafe_allow_html=True,
    )

    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", type="primary", use_container_width=True):
        if not username or not password:
            st.error("Please enter both username and password.")
        elif authenticate_user(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username.strip()
            st.rerun()
            return username.strip()
        else:
            st.error("Invalid username or password.")

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Register", use_container_width=True):
            _set_auth_page("register")
            st.rerun()
    with col2:
        if st.button("Forgot Password?", use_container_width=True):
            _set_auth_page("reset")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    return None


def _render_register() -> Optional[str]:
    """Render the **Register** form.

    On success the user is automatically logged in (``authenticated=True``,
    ``username`` set, page switches to ``"login"``).
    """
    st.markdown(
        '<div class="auth-container">'
        '<div class="auth-title">📝 Create Account</div>',
        unsafe_allow_html=True,
    )

    username = st.text_input("Username", key="register_username")
    password = st.text_input("Password", type="password", key="register_password")
    confirm = st.text_input(
        "Confirm Password", type="password", key="register_confirm"
    )

    if st.button("Register", type="primary", use_container_width=True):
        if not username or not password or not confirm:
            st.error("Please fill in all fields.")
        elif password != confirm:
            st.error("Passwords do not match.")
        else:
            success, message = register_user(username, password)
            if success:
                st.success("Account created successfully!")
                st.session_state.authenticated = True
                st.session_state.username = username.strip()
                st.session_state.auth_page = "login"
                st.rerun()
                return username.strip()
            else:
                st.error(message)

    if st.button("← Back to Login", use_container_width=True):
        _set_auth_page("login")
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    return None


def _render_reset() -> Optional[str]:
    """Render the **Password Reset** form.

    On success the user is redirected to the login page with a confirmation
    message (no automatic login).
    """
    st.markdown(
        '<div class="auth-container">'
        '<div class="auth-title">🔑 Reset Password</div>',
        unsafe_allow_html=True,
    )

    username = st.text_input("Username", key="reset_username")
    old_password = st.text_input(
        "Old Password", type="password", key="reset_old"
    )
    new_password = st.text_input(
        "New Password", type="password", key="reset_new"
    )
    confirm = st.text_input(
        "Confirm New Password", type="password", key="reset_confirm"
    )

    if st.button("Reset Password", type="primary", use_container_width=True):
        if not username or not old_password or not new_password or not confirm:
            st.error("Please fill in all fields.")
        elif new_password != confirm:
            st.error("New passwords do not match.")
        else:
            success, message = reset_password(username, old_password, new_password)
            if success:
                st.success(
                    "Password reset successfully! "
                    "Please log in with your new password."
                )
                st.session_state.auth_page = "login"
                st.rerun()
            else:
                st.error(message)

    if st.button("← Back to Login", use_container_width=True):
        _set_auth_page("login")
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    return None
