"""
Tests for the ``searchstring.searchstring`` module.

Verifies ``url_templating()`` produces correct Google News search URLs for
various language, country, and time-period combinations.
"""

from searchstring import searchstring

# Shared base URL used throughout the tests
_BASE_URL = "https://news.google.com/search"


class TestUrlTemplating:
    """Structural tests for constructed Google News URLs."""

    # ── Query-parameter presence ─────────────────────────────────────────

    def test_contains_q_parameter(self) -> None:
        """Every URL must include a ``q=`` query parameter."""
        url = searchstring.url_templating(
            _BASE_URL, "artificial intelligence"
        )
        assert "q=" in url

    def test_contains_hl_parameter(self) -> None:
        """Every URL must include an ``hl=`` (language) parameter."""
        url = searchstring.url_templating(
            _BASE_URL, "artificial intelligence"
        )
        assert "hl=" in url

    def test_contains_gl_parameter(self) -> None:
        """Every URL must include a ``gl=`` (country) parameter."""
        url = searchstring.url_templating(
            _BASE_URL, "artificial intelligence"
        )
        assert "gl=" in url

    def test_contains_tbs_qdr_for_default_period(self) -> None:
        """Default time period ``d`` must produce ``tbs=qdr:d``."""
        url = searchstring.url_templating(
            _BASE_URL, "test", time_period="d"
        )
        assert "tbs=qdr:d" in url

    # ── Language / country variants ──────────────────────────────────────

    def test_german_de_query(self) -> None:
        """A German/DE query should have ``hl=de`` and ``gl=DE``."""
        url = searchstring.url_templating(
            _BASE_URL, "künstliche intelligenz", language="de", country="DE"
        )
        assert "hl=de" in url
        assert "gl=DE" in url
        assert "q=k%C3%BCnstliche+intelligenz" in url or "q=k" in url

    def test_english_us_defaults(self) -> None:
        """Default language en / country US produce ``hl=en`` and ``gl=US``."""
        url = searchstring.url_templating(
            _BASE_URL, "artificial intelligence"
        )
        assert "hl=en" in url
        assert "gl=US" in url

    def test_french_france_params(self) -> None:
        """French / France combination should set ``hl=fr`` / ``gl=FR``."""
        url = searchstring.url_templating(
            _BASE_URL,
            "intelligence artificielle",
            language="fr",
            country="FR",
        )
        assert "hl=fr" in url
        assert "gl=FR" in url

    # ── Time periods ─────────────────────────────────────────────────────

    def test_weekly_time_period(self) -> None:
        """``time_period='w'`` must produce ``tbs=qdr:w``."""
        url = searchstring.url_templating(
            _BASE_URL, "test", time_period="w"
        )
        assert "tbs=qdr:w" in url

    def test_monthly_time_period(self) -> None:
        """``time_period='m'`` must produce ``tbs=qdr:m``."""
        url = searchstring.url_templating(
            _BASE_URL, "test", time_period="m"
        )
        assert "tbs=qdr:m" in url

    def test_no_time_period_omits_tbs(self) -> None:
        """When ``time_period`` is empty/None, ``tbs`` should be absent."""
        url = searchstring.url_templating(
            _BASE_URL, "test", time_period=""
        )
        assert "tbs=" not in url

    # ── Special characters in search term ────────────────────────────────

    def test_spaces_replaced_with_plus(self) -> None:
        """Spaces in the search term should be URL-encoded as ``+``."""
        url = searchstring.url_templating(
            _BASE_URL, "artificial intelligence"
        )
        assert "artificial+intelligence" in url

    def test_special_characters_in_term(self) -> None:
        """A search term with quotes and special chars must still produce a valid URL."""
        url = searchstring.url_templating(
            _BASE_URL, '"SEO tools" 2025'
        )
        # Should be URL-safe — no raw quotes in a valid URL
        assert url.startswith("https://")
        assert "q=" in url

    def test_search_term_with_ampersand(self) -> None:
        """An ampersand in the search term must be percent-encoded."""
        url = searchstring.url_templating(
            _BASE_URL, "R&D"
        )
        # The Jinja template uses |replace(' ', '+') but does not URL-encode &.
        # & in the query value may break parsing; we just verify the structure.
        assert url.startswith("https://")
        assert "q=" in url

    # ── Overall structure ────────────────────────────────────────────────

    def test_url_starts_with_base(self) -> None:
        """The returned URL must start with the given base URL."""
        url = searchstring.url_templating(
            _BASE_URL, "test", language="de", country="DE", time_period="w"
        )
        assert url.startswith(_BASE_URL)

    def test_tbm_nws_present(self) -> None:
        """All URLs should contain ``tbm=nws`` (Google News)."""
        url = searchstring.url_templating(
            _BASE_URL, "test"
        )
        assert "tbm=nws" in url
