"""
Integration tests for DataForSEO and Gemini API credentials.

These tests make **real** API calls (not mocked) to verify that the
credentials stored in ``.env`` actually work against live endpoints.

.. warning::

   These tests are **skipped by default**.  Set the environment variable
   ``SKIP_INTEGRATION=0`` (or unset it) to run them::

       SKIP_INTEGRATION=0 python -m pytest tests/test_credentials_integration.py -v
"""

import os

import pytest
import requests
from base64 import b64encode

from config import config

# ---------------------------------------------------------------------------
# Module-level skip: integration tests are opt-in only
# ---------------------------------------------------------------------------
_SKIP = os.getenv("SKIP_INTEGRATION", "1") != "0"

pytestmark = pytest.mark.skipif(
    _SKIP,
    reason="Integration tests disabled by default. "
    "Set SKIP_INTEGRATION=0 to run them.",
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _build_basic_auth_header(username: str, password: str) -> dict:
    """Return an ``Authorization`` header dict for HTTP Basic Auth."""
    raw = f"{username}:{password}".encode("ascii")
    encoded = b64encode(raw).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


# ---------------------------------------------------------------------------
# DataForSEO
# ---------------------------------------------------------------------------
class TestDataForSeoCredentials:
    """Verify that the DataForSEO username/password authenticate successfully."""

    def test_dataforseo_credentials(self) -> None:
        """
        Send a GET request to the DataForSEO API with Basic Auth.

        The test passes if:
        * The response status code is **not** 401 or 403 (credentials valid).
        * A ``RequestException`` is raised but does **not** carry a 401/403
          status (e.g. a connection error or timeout – not a credential issue).

        The test **fails** only when the server explicitly rejects the
        credentials with ``HTTP 401 Unauthorized`` or ``HTTP 403 Forbidden``.
        """
        username = config.SEO_USERNAME
        password = config.SEO_PASSWORD
        auth_headers = _build_basic_auth_header(username, password)
        # Also add the content-type header the RestClient would normally send
        auth_headers["Content-Type"] = "application/json"

        try:
            response = requests.get(
                "https://api.dataforseo.com",
                headers=auth_headers,
                timeout=10,
            )
            # If we got a response, ensure it is not an auth rejection
            assert response.status_code not in (
                401,
                403,
            ), (
                f"DataForSEO credentials were rejected: "
                f"HTTP {response.status_code}"
            )

        except requests.exceptions.RequestException as exc:
            # A connection-level error (DNS, timeout, etc.) is not a
            # credential problem – let the test pass (but explain why).
            if exc.response is not None and exc.response.status_code in (
                401,
                403,
            ):
                pytest.fail(
                    f"DataForSEO credentials were rejected: "
                    f"HTTP {exc.response.status_code}"
                )
            # Any other networking issue → skip rather than fail
            pytest.skip(
                f"Could not reach DataForSEO API (not a credential issue): "
                f"{exc}"
            )


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
class TestGeminiCredentials:
    """Verify that the Gemini API key authenticates and can generate text."""

    def test_gemini_credentials(self) -> None:
        """
        Configure the ``google.generativeai`` client with the project's
        ``GEM_API`` key and send a short generation request.

        The test passes if the model returns a non-empty response.
        """
        import google.generativeai as genai

        genai.configure(api_key=config.GEM_API)

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            "Say 'ok'",
            request_options={"timeout": 10},
        )

        assert response is not None
        assert response.text is not None
        assert len(response.text.strip()) > 0, (
            "Gemini returned an empty response"
        )
