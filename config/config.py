"""
Configuration module for SEOOptimizer.

Secrets are loaded exclusively from environment variables (via a .env file
or the shell environment).  No hardcoded fallback values are provided — all
secrets MUST be set before the application starts.

See the project .env.example file for the required variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Secrets (load from environment ONLY) ────────────────────────────────────
# WARNING: Every secret below loads *only* from os.getenv() with no fallback.
# If the environment variable is unset the value will be None, and the
# validation block at the bottom of this module will raise a clear error.

API_KEY = os.getenv("API_KEY")

GEM_API = os.getenv("GEM_API")

SEO_USERNAME = os.getenv("SEO_USERNAME")

SEO_PASSWORD = os.getenv("SEO_PASSWORD")

AUTH_USERNAME = os.getenv("AUTH_USERNAME")

AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")

# ── Non-sensitive configuration ─────────────────────────────────────────────
BASE_URL = "https://news.google.com/search"
SEO_post_path = "/v3/dataforseo_labs/google/keyword_suggestions/live"

# ── Secrets validation ──────────────────────────────────────────────────────
# Ensure required secrets are present.  This check runs at import time so the
# application fails fast when credentials are missing.

_REQUIRED_SECRETS: dict[str, str | None] = {
    "GEM_API": GEM_API,
    "SEO_USERNAME": SEO_USERNAME,
    "SEO_PASSWORD": SEO_PASSWORD,
}

_missing = [name for name, value in _REQUIRED_SECRETS.items() if value is None]
if _missing:
    raise ValueError(
        "The following required secret(s) are not set: "
        f"{', '.join(_missing)}. "
        "Please define them in a .env file or export them as environment "
        "variables before starting the application."
    )