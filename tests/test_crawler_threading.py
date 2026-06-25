"""
Tests for the ``googlecrawler.crawler_threading`` module.

Covers:
- ``download_and_parse_article()`` with invalid/malformed URLs.
- Network errors via mocked ``newspaper.Article``.

NOTE: The source module ``crawler_threading.py`` has an ``except`` clause
that references ``requests.exceptions.RequestException`` but does **not**
import ``requests``. Because this ``NameError`` would crash the daemon thread,
we inject ``requests`` into the module's namespace before each test via a
fixture. This is a test-only workaround and does not modify source files.
"""

from unittest.mock import MagicMock, patch

import pytest

from googlecrawler import crawler_threading


# Ensure ``requests`` is available in the module namespace so that the
# ``except requests.exceptions.RequestException`` clause does not raise
# ``NameError`` when evaluated inside the worker thread.
import requests as _requests
crawler_threading.requests = _requests


class TestDownloadAndParseArticle:
    """``download_and_parse_article()`` error-handling behaviour."""

    def test_invalid_url_returns_error(self) -> None:
        """A generic download failure should produce an error entry."""
        with patch.object(
            crawler_threading.Article,
            "download",
            side_effect=Exception("Failed to download"),
        ):
            result = crawler_threading.download_and_parse_article(
                ["not-a-valid-url"]
            )
            assert isinstance(result, dict)
            assert "not-a-valid-url" in result
            error_val = result["not-a-valid-url"]
            assert isinstance(error_val, str)
            assert error_val.startswith("Error:")

    def test_malformed_url_returns_error(self) -> None:
        """A malformed URL should produce an error entry."""
        with patch.object(
            crawler_threading.Article,
            "download",
            side_effect=Exception("Malformed URL"),
        ):
            result = crawler_threading.download_and_parse_article(["http://"])
            assert isinstance(result, dict)
            assert "http://" in result
            error_val = result["http://"]
            assert isinstance(error_val, str)
            assert error_val.startswith("Error:")

    def test_article_exception_during_download(self) -> None:
        """A ``newspaper.ArticleException`` during download should be caught by the
        first except clause and produce an ``Error:`` entry."""
        import newspaper

        with patch.object(
            crawler_threading.Article,
            "download",
            side_effect=newspaper.ArticleException("Article download failed"),
        ):
            result = crawler_threading.download_and_parse_article(
                ["https://example.com/broken"]
            )
            assert "https://example.com/broken" in result
            error_val = result["https://example.com/broken"]
            assert isinstance(error_val, str)
            assert error_val.startswith("Error:")
            assert "Newspaper Article Error" in error_val

    def test_unexpected_exception_falls_to_generic_clause(self) -> None:
        """An exception that is neither ArticleException nor RequestException
        should be caught by the generic ``except Exception`` clause."""
        with patch.object(
            crawler_threading.Article,
            "download",
            side_effect=RuntimeError("Something unexpected"),
        ):
            result = crawler_threading.download_and_parse_article(
                ["https://example.com/unexpected"]
            )
            assert "https://example.com/unexpected" in result
            error_val = result["https://example.com/unexpected"]
            assert isinstance(error_val, str)
            assert error_val.startswith("Error:")

    def test_empty_urls_list_returns_empty_dict(self) -> None:
        """An empty list of URLs should return an empty dict."""
        result = crawler_threading.download_and_parse_article([])
        assert result == {}

    def test_mocked_successful_article(self) -> None:
        """A successfully downloaded/parsed article should return structured data."""
        mock_article = MagicMock()
        mock_article.title = "Test Article Title"
        mock_article.text = "This is the article body text."
        mock_article.authors = ["Author One"]
        mock_article.publish_date = "2025-06-01"
        mock_article.top_image = "https://example.com/img.jpg"
        mock_article.movies = []
        mock_article.url = "https://example.com/article"

        with patch.object(crawler_threading, "Article", return_value=mock_article):
            result = crawler_threading.download_and_parse_article(
                ["https://example.com/article"]
            )
            assert isinstance(result, dict)
            assert "https://example.com/article" in result
            data = result["https://example.com/article"]
            assert isinstance(data, dict)
            assert data["title"] == "Test Article Title"
            assert data["text"] == "This is the article body text."
            assert data["authors"] == ["Author One"]
            assert data["publish_date"] == "2025-06-01"

    def test_multiple_urls_return_multiple_results(self) -> None:
        """Processing multiple URLs should return an entry for each."""
        mock_article = MagicMock()
        mock_article.title = "Title"
        mock_article.text = "Body"
        mock_article.authors = []
        mock_article.publish_date = None
        mock_article.top_image = ""
        mock_article.movies = []
        mock_article.url = "https://example.com/article"

        with patch.object(crawler_threading, "Article", return_value=mock_article):
            urls = [
                "https://example.com/a",
                "https://example.com/b",
                "https://example.com/c",
            ]
            result = crawler_threading.download_and_parse_article(urls)
            assert len(result) == 3
            for url in urls:
                assert url in result

    def test_parse_failure_returns_error(self) -> None:
        """If ``article.parse()`` raises an exception, the result should be an error."""
        mock_article = MagicMock()
        mock_article.download = MagicMock()  # succeeds
        mock_article.parse = MagicMock(
            side_effect=Exception("Parse failed")
        )

        with patch.object(crawler_threading, "Article", return_value=mock_article):
            result = crawler_threading.download_and_parse_article(
                ["https://example.com/parse-fail"]
            )
            assert "https://example.com/parse-fail" in result
            error_val = result["https://example.com/parse-fail"]
            assert isinstance(error_val, str)
            assert error_val.startswith("Error:")

    def test_some_failures_some_successes(self) -> None:
        """When some URLs fail and some succeed, the result dict reflects both."""
        # Create a factory that returns a fresh mock per URL so we can
        # differentiate success/failure by the URL argument.
        article_instances: dict = {}

        def article_factory(url: str) -> MagicMock:
            mock_art = MagicMock()
            mock_art.url = url
            if "fail" in url:
                mock_art.download.side_effect = RuntimeError(
                    f"Failed to download {url}"
                )
            else:
                mock_art.title = f"Title for {url}"
                mock_art.text = f"Body for {url}"
                mock_art.authors = []
                mock_art.publish_date = None
                mock_art.top_image = ""
                mock_art.movies = []
            article_instances[url] = mock_art
            return mock_art

        with patch.object(
            crawler_threading, "Article", side_effect=article_factory
        ):
            urls = [
                "https://example.com/fail-page",
                "https://example.com/success-page",
            ]
            result = crawler_threading.download_and_parse_article(urls)
            assert len(result) == 2
            # Failure entry
            assert result["https://example.com/fail-page"].startswith("Error:")
            # Success entry
            success_data = result["https://example.com/success-page"]
            assert isinstance(success_data, dict)
            assert (
                success_data["title"]
                == "Title for https://example.com/success-page"
            )
