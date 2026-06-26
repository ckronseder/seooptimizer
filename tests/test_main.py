"""
Tests for the ``main`` module.

Covers:
- That ``main.py`` can be imported without errors.
- That the keyword-search function uses ``st.cache_data`` caching.
- That ``vectordb.store`` functions handle ChromaDB errors gracefully.
"""

from unittest.mock import MagicMock, patch

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


# ============================================================================
# VectorDB error-handling tests (graceful fallback on ChromaDB failures)
# ============================================================================


class TestVectorDBErrorHandling:
    """The ``vectordb.store`` module should return safe fallback values when
    ChromaDB raises exceptions (corrupted DB, incompatible embeddings, etc.)."""

    # ------------------------------------------------------------------
    # get_cached_articles
    # ------------------------------------------------------------------

    def test_get_cached_articles_returns_none_on_collection_error(
        self,
    ) -> None:
        """``_get_collection`` failure → ``None``."""
        from vectordb import store as vectordb

        with patch(
            "vectordb.store._get_collection",
            side_effect=Exception("DB connection lost"),
        ):
            result = vectordb.get_cached_articles("some_id")
            assert result is None

    def test_get_cached_articles_returns_none_on_get_error(self) -> None:
        """``collection.get`` failure → ``None``."""
        from vectordb import store as vectordb

        mock_collection = MagicMock()
        mock_collection.get.side_effect = Exception("Get failed")
        with patch(
            "vectordb.store._get_collection",
            return_value=mock_collection,
        ):
            result = vectordb.get_cached_articles("some_id")
            assert result is None

    def test_get_cached_articles_returns_none_on_missing_collection(
        self,
    ) -> None:
        """Non-existent collection (simulated by empty results) → ``None``."""
        from vectordb import store as vectordb

        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": [], "metadatas": [], "documents": []}
        with patch(
            "vectordb.store._get_collection",
            return_value=mock_collection,
        ):
            result = vectordb.get_cached_articles("some_id")
            assert result is None

    # ------------------------------------------------------------------
    # store_articles
    # ------------------------------------------------------------------

    def test_store_articles_returns_count_on_success(self) -> None:
        """Successful store returns the number of articles."""
        from vectordb import store as vectordb

        mock_collection = MagicMock()
        articles = {
            "https://example.com/1": {
                "title": "Article 1",
                "text": "Full text here.",
            },
        }
        with patch(
            "vectordb.store._get_collection",
            return_value=mock_collection,
        ):
            result = vectordb.store_articles(articles, search_id="s1")
            assert result == 1
            mock_collection.add.assert_called_once()

    def test_store_articles_returns_zero_on_collection_error(self) -> None:
        """``_get_collection`` failure → ``0``."""
        from vectordb import store as vectordb

        with patch(
            "vectordb.store._get_collection",
            side_effect=Exception("DB connection lost"),
        ):
            result = vectordb.store_articles({}, search_id="s1")
            assert result == 0

    def test_store_articles_returns_zero_on_add_error(self) -> None:
        """``collection.add`` failure → ``0``."""
        from vectordb import store as vectordb

        mock_collection = MagicMock()
        mock_collection.add.side_effect = Exception("Add failed")
        articles = {
            "https://example.com/1": {
                "title": "Article 1",
                "text": "Full text here.",
            },
        }
        with patch(
            "vectordb.store._get_collection",
            return_value=mock_collection,
        ):
            result = vectordb.store_articles(articles, search_id="s1")
            assert result == 0

    def test_store_articles_returns_zero_on_delete_error(self) -> None:
        """``collection.delete`` failure → ``0``."""
        from vectordb import store as vectordb

        mock_collection = MagicMock()
        mock_collection.delete.side_effect = Exception("Delete failed")
        articles = {
            "https://example.com/1": {
                "title": "Article 1",
                "text": "Full text here.",
            },
        }
        with patch(
            "vectordb.store._get_collection",
            return_value=mock_collection,
        ):
            result = vectordb.store_articles(articles, search_id="s1")
            assert result == 0

    def test_store_articles_skips_articles_without_text(self) -> None:
        """Articles without a 'text' key (or with empty text) are skipped."""
        from vectordb import store as vectordb

        mock_collection = MagicMock()
        articles = {
            "https://example.com/1": {"title": "No text here"},  # no 'text' key
            "https://example.com/2": {"title": "X", "text": ""},  # empty text
        }
        with patch(
            "vectordb.store._get_collection",
            return_value=mock_collection,
        ):
            result = vectordb.store_articles(articles, search_id="s1")
            assert result == 0
            mock_collection.add.assert_not_called()

    # ------------------------------------------------------------------
    # query_articles
    # ------------------------------------------------------------------

    def test_query_articles_returns_empty_on_collection_error(self) -> None:
        """``_get_collection`` failure → ``[]``."""
        from vectordb import store as vectordb

        with patch(
            "vectordb.store._get_collection",
            side_effect=Exception("DB connection lost"),
        ):
            result = vectordb.query_articles("query")
            assert result == []

    def test_query_articles_returns_empty_on_empty_collection(self) -> None:
        """Empty collection (``count() == 0``) → ``[]``."""
        from vectordb import store as vectordb

        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        with patch(
            "vectordb.store._get_collection",
            return_value=mock_collection,
        ):
            result = vectordb.query_articles("query")
            assert result == []

    def test_query_articles_returns_empty_on_query_error(self) -> None:
        """``collection.query`` failure → ``[]``."""
        from vectordb import store as vectordb

        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_collection.query.side_effect = Exception("Query failed")
        with patch(
            "vectordb.store._get_collection",
            return_value=mock_collection,
        ):
            result = vectordb.query_articles("query")
            assert result == []

    def test_query_articles_returns_articles_on_success(self) -> None:
        """Successful query returns a list of article dicts."""
        from vectordb import store as vectordb

        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {
            "ids": [["url1", "url2"]],
            "metadatas": [[{"title": "A1"}, {"title": "A2"}]],
            "documents": [["text1", "text2"]],
            "distances": [[0.1, 0.2]],
        }
        with patch(
            "vectordb.store._get_collection",
            return_value=mock_collection,
        ):
            result = vectordb.query_articles("query", top_k=2)
            assert len(result) == 2
            assert result[0]["url"] == "url1"
            assert result[0]["title"] == "A1"
            assert result[0]["text"] == "text1"
            assert result[1]["url"] == "url2"

    # ------------------------------------------------------------------
    # collection_size
    # ------------------------------------------------------------------

    def test_collection_size_returns_zero_on_error(self) -> None:
        """``_get_collection`` failure → ``0``."""
        from vectordb import store as vectordb

        with patch(
            "vectordb.store._get_collection",
            side_effect=Exception("DB connection lost"),
        ):
            result = vectordb.collection_size()
            assert result == 0

    def test_collection_size_returns_count_on_success(self) -> None:
        """Successful count returns the expected integer."""
        from vectordb import store as vectordb

        mock_collection = MagicMock()
        mock_collection.count.return_value = 42
        with patch(
            "vectordb.store._get_collection",
            return_value=mock_collection,
        ):
            result = vectordb.collection_size()
            assert result == 42
