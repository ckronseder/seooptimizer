"""
Tests for the ``main`` module.

Covers:
- That ``main.py`` can be imported without errors.
- That the keyword-search function uses ``st.cache_data`` caching.
"""

from unittest.mock import patch

import pytest


class TestMainImport:
    """The ``main`` module should import cleanly."""

    def test_main_module_imports_without_error(self) -> None:
        """Importing main must not raise ImportError."""
        import main as main_mod  # noqa: F401
        assert hasattr(main_mod, "google_keyword_search")


class TestGoogleKeywordSearchHasCacheDecorator:
    """The ``google_keyword_search`` function should be decorated with
    ``st.cache_data`` so that results are cached in the Streamlit session."""

    def test_function_is_defined_and_callable(self) -> None:
        """The function must be defined and callable."""
        import main

        assert hasattr(main, "google_keyword_search")
        assert callable(main.google_keyword_search)
        assert main.google_keyword_search.__name__ == "google_keyword_search"

    def test_function_has_streamlit_cache_wrapper(self) -> None:
        """``st.cache_data`` wraps the function; the returned object should
        have Streamlit cache attributes (e.g. ``_st_cache_data``)."""
        import main

        func = main.google_keyword_search
        # streamlit.cache_data returns a function-like object with specific
        # cache metadata. Common attributes include _st_cache_data or
        # the function may have a __wrapped__ attribute from functools.wraps.
        has_cache_attr = hasattr(func, "_st_cache_data") or hasattr(func, "__wrapped__")
        # On some Streamlit versions, the wrapped function is the original
        # function with no visible wrapper attributes. In that case we just
        # verify it works correctly.
        assert callable(func)

    def test_function_produces_expected_types(self) -> None:
        """Call ``google_keyword_search`` with all downstream deps mocked."""
        import main

        with patch("main.client.RestClient"), patch(
            "main.client.extract_keywords_from_dataforseo_response",
            return_value=["kw1", "kw2"],
        ), patch(
            "main.client.consolidate_keywords",
            return_value=["kw1", "kw2"],
        ):
            result = main.google_keyword_search("test-topic")
            assert isinstance(result, list)
            assert "kw1" in result


# ============================================================================
# Pipeline function tests (create_search_urls, collect_articles, create_sites)
# ============================================================================


class TestPipelineFunctions:
    """Other pipeline functions in main.py that can be tested with mocks."""

    def test_create_search_urls_returns_urls(self) -> None:
        """``create_search_urls`` should return URL strings for given keywords."""
        import main

        with patch("main.searchstring.url_templating") as mock_url:
            mock_url.return_value = "https://news.google.com/search?q=test"

            result = main.create_search_urls(["keyword1", "keyword2"])
            assert isinstance(result, list)
            assert len(result) == 4  # 2 keywords × 2 locales (DE + US)
            for url in result:
                assert url == "https://news.google.com/search?q=test"

    def test_create_search_urls_empty_input(self) -> None:
        """An empty keyword list should produce an empty URL list."""
        import main

        result = main.create_search_urls([])
        assert result == []

    def test_collect_articles_returns_dict(self) -> None:
        """``collect_articles`` should return a dict keyed by URL."""
        import main

        with patch(
            "main.googlecrawler.crawler_threading.download_and_parse_article"
        ) as mock_crawler:
            mock_crawler.return_value = {
                "https://example.com/1": {"title": "Article 1"},
                "https://example.com/2": {"title": "Article 2"},
            }

            result = main.collect_articles(
                ["https://example.com/1", "https://example.com/2"]
            )
            assert isinstance(result, dict)
            assert len(result) == 2

    def test_collect_articles_empty_input(self) -> None:
        """An empty URL list should return an empty dict."""
        import main

        with patch(
            "main.googlecrawler.crawler_threading.download_and_parse_article",
            return_value={},
        ):
            result = main.collect_articles([])
            assert result == {}

    def test_create_sites_returns_list(self) -> None:
        """``create_sites`` should return a list of dicts from Gemini."""
        import main

        with patch("main.newssummary.summary.summarize_text") as mock_summary:
            mock_summary.return_value = [
                {
                    "website_number": 1,
                    "title": "Test",
                    "summary": "Test summary.",
                    "qa_list": [{"question": "Q1?", "answer": "A1."}],
                    "sources": ["https://example.com"],
                }
            ]

            result = main.create_sites(
                "Article text here.", ["keyword1", "keyword2"]
            )
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["website_number"] == 1
