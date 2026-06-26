"""Streamlit login form.

The :func:`show_login_page` function is designed to be called from the main
app entry point and returns the authenticated username on success.
"""

from typing import Optional

import streamlit as st

from auth.user_auth import authenticate_user


def show_login_page() -> Optional[str]:
    """Render the login form.

    Returns:
        The authenticated *username* on success, ``None`` otherwise.
    """
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

    return _render_login()


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

    st.markdown("</div>", unsafe_allow_html=True)
    return None
