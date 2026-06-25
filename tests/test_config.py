"""
Tests for the ``config.config`` module.

Verifies that:
- The module loads without error.
- All configuration values are strings.
- Environment variables correctly override hardcoded defaults via monkeypatch.
- Credentials in the ``.env`` file are present and not placeholders.
- The ``.env`` file itself exists and is readable.
"""

import os
from pathlib import Path

from dotenv import dotenv_values

from config import config


class TestConfigLoads:
    """The config module must import without raising."""

    def test_module_imported_successfully(self) -> None:
        """Config module is already imported at the top of this file."""
        assert config is not None


class TestConfigValuesAreStrings:
    """All configuration values should be of type ``str``."""

    # List of attribute names that must be present on the config module
    _CONFIG_ATTRS = [
        "API_KEY",
        "GEM_API",
        "SEO_USERNAME",
        "SEO_PASSWORD",
        "BASE_URL",
        "SEO_post_path",
    ]

    def test_all_config_values_are_strings(self) -> None:
        """Every expected config attribute must be a string."""
        for attr in self._CONFIG_ATTRS:
            value = getattr(config, attr, None)
            assert value is not None, f"config.{attr} is not defined"
            assert isinstance(value, str), (
                f"config.{attr} should be a str, got {type(value)}"
            )


class TestEnvironmentVariableOverride:
    """Environment variables must take precedence over hardcoded defaults."""

    def test_gem_api_overridden(self, monkeypatch) -> None:
        """Setting GEM_API as env var should override the dev fallback."""
        monkeypatch.setenv("GEM_API", "test-override-gem-api")
        # Re-import the module to pick up the new env var
        import importlib
        import config.config as cfg_mod
        importlib.reload(cfg_mod)
        assert cfg_mod.GEM_API == "test-override-gem-api"
        # Reload again to restore state for subsequent tests
        importlib.reload(cfg_mod)

    def test_seo_username_overridden(self, monkeypatch) -> None:
        """Setting SEO_USERNAME as env var should override the dev fallback."""
        monkeypatch.setenv("SEO_USERNAME", "test-user@example.com")
        import importlib
        import config.config as cfg_mod
        importlib.reload(cfg_mod)
        assert cfg_mod.SEO_USERNAME == "test-user@example.com"
        importlib.reload(cfg_mod)

    def test_seo_password_overridden(self, monkeypatch) -> None:
        """Setting SEO_PASSWORD as env var should override the dev fallback."""
        monkeypatch.setenv("SEO_PASSWORD", "test-pass-123")
        import importlib
        import config.config as cfg_mod
        importlib.reload(cfg_mod)
        assert cfg_mod.SEO_PASSWORD == "test-pass-123"
        importlib.reload(cfg_mod)

    def test_api_key_overridden(self, monkeypatch) -> None:
        """Setting API_KEY as env var should override the dev fallback."""
        monkeypatch.setenv("API_KEY", "test-api-key")
        import importlib
        import config.config as cfg_mod
        importlib.reload(cfg_mod)
        assert cfg_mod.API_KEY == "test-api-key"
        importlib.reload(cfg_mod)


# ── Credential validation ────────────────────────────────────────────────────


def _project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return Path(__file__).resolve().parent.parent


def test_credentials_are_not_placeholders() -> None:
    """
    Verify that the ``.env`` file contains real credential values.

    Asserts that ``GEM_API``, ``SEO_USERNAME``, and ``SEO_PASSWORD`` are
    present, non-empty, and not set to any known placeholder string.
    """
    env_path = _project_root() / ".env"
    env = dotenv_values(env_path)

    # ── GEM_API ────────────────────────────────────────────────────────────
    gem_api = env.get("GEM_API")
    assert gem_api is not None, "GEM_API is missing from .env"
    assert gem_api != "", "GEM_API is empty in .env"
    assert gem_api != "your_gemini_api_key_here", (
        "GEM_API is still set to placeholder 'your_gemini_api_key_here'"
    )
    assert gem_api != "your_api_key_here", (
        "GEM_API is still set to the generic placeholder 'your_api_key_here'"
    )

    # ── SEO_USERNAME ───────────────────────────────────────────────────────
    username = env.get("SEO_USERNAME")
    assert username is not None, "SEO_USERNAME is missing from .env"
    assert username != "", "SEO_USERNAME is empty in .env"
    assert username != "your_dataforseo_username_here", (
        "SEO_USERNAME is still set to placeholder "
        "'your_dataforseo_username_here'"
    )

    # ── SEO_PASSWORD ───────────────────────────────────────────────────────
    password = env.get("SEO_PASSWORD")
    assert password is not None, "SEO_PASSWORD is missing from .env"
    assert password != "", "SEO_PASSWORD is empty in .env"
    assert password != "your_dataforseo_password_here", (
        "SEO_PASSWORD is still set to placeholder "
        "'your_dataforseo_password_here'"
    )


def test_env_file_exists() -> None:
    """Assert that the ``.env`` file exists at the project root and is readable."""
    env_path = _project_root() / ".env"
    assert env_path.exists(), f".env file not found at {env_path}"
    assert env_path.is_file(), f"{env_path} is not a regular file"
    assert os.access(str(env_path), os.R_OK), (
        f".env file at {env_path} is not readable"
    )
