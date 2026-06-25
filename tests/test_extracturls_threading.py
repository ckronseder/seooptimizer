"""
Tests for the ``googlecrawler.extracturls_threading`` module.

Covers:
- ``extract_urls()`` with text containing real-looking article URLs.
- Filtering of Google/image/internal URLs.
- Empty and edge-case inputs.

NOTE: ``extract_urls()`` operates on raw text (not HTML). It splits by ``,``
and uses a regex to capture ``https://`` URLs, then filters out URLs
containing image extensions, google, gstatic, etc. The input simulates what
Google News search-result pages return.
"""

from unittest.mock import patch

import pytest

from googlecrawler import extracturls_threading


class TestExtractUrls:
    """``extract_urls()`` extracts and filters article URLs from downloaded text."""

    def test_extracts_article_urls(self) -> None:
        """Text with valid article URLs (comma-separated) should return those URLs."""
        # The extract_urls function splits by comma and finds https:// URLs
        raw_text = (
            'https://www.bbc.com/news/tech-123,'
            'https://www.reuters.com/article/ai-2025,'
            'some trailing text'
        )
        news_feed = {"https://news.google.com/url1": raw_text}
        result = extracturls_threading.extract_urls(news_feed)
        assert isinstance(result, list)
        assert "https://www.bbc.com/news/tech-123" in result
        assert "https://www.reuters.com/article/ai-2025" in result

    def test_filters_google_urls(self) -> None:
        """URLs containing 'google' must be filtered out."""
        raw_text = (
            'https://www.google.com/search?q=test,'
            'https://www.example.com/article'
        )
        news_feed = {"url1": raw_text}
        result = extracturls_threading.extract_urls(news_feed)
        assert "https://www.google.com/search?q=test" not in result
        assert "https://www.example.com/article" in result

    def test_filters_image_urls(self) -> None:
        """URLs containing image extensions (jpg, png, svg) must be filtered out."""
        raw_text = (
            'https://example.com/photo.jpg,'
            'https://example.com/image.png,'
            'https://example.com/article'
        )
        news_feed = {"url1": raw_text}
        result = extracturls_threading.extract_urls(news_feed)
        assert "https://example.com/photo.jpg" not in result
        assert "https://example.com/image.png" not in result
        assert "https://example.com/article" in result

    def test_filters_gstatic_urls(self) -> None:
        """URLs containing 'gstatic' must be filtered out."""
        raw_text = (
            'https://www.gstatic.com/images/logo.png,'
            'https://www.example.com/news'
        )
        news_feed = {"url1": raw_text}
        result = extracturls_threading.extract_urls(news_feed)
        assert "https://www.gstatic.com" not in str(result)
        assert "https://www.example.com/news" in result

    def test_empty_string_returns_empty_list(self) -> None:
        """Empty string should produce an empty list."""
        news_feed = {"url1": ""}
        result = extracturls_threading.extract_urls(news_feed)
        assert result == []

    def test_text_with_no_valid_urls(self) -> None:
        """Text with no HTTPS links (or only filtered ones) should return empty list."""
        raw_text = 'No URLs here, just some text, https://example.com/img.jpg'
        news_feed = {"url1": raw_text}
        result = extracturls_threading.extract_urls(news_feed)
        assert result == []

    def test_deduplicates_urls(self) -> None:
        """The same URL appearing in multiple feed entries must appear only once."""
        raw_text = 'https://www.example.com/dup'
        news_feed = {"url1": raw_text, "url2": raw_text}
        result = extracturls_threading.extract_urls(news_feed)
        occurrences = sum(
            1 for url in result if url == "https://www.example.com/dup"
        )
        assert occurrences == 1

    def test_extract_from_multiple_keys(self) -> None:
        """Multiple keys in the news_feed dict are all processed."""
        news_feed = {
            "url1": 'https://www.bbc.com/news/1',
            "url2": 'https://www.bbc.com/news/2',
        }
        result = extracturls_threading.extract_urls(news_feed)
        assert "https://www.bbc.com/news/1" in result
        assert "https://www.bbc.com/news/2" in result

    def test_url_with_special_characters(self) -> None:
        """URLs with special characters (unicode escapes) should be handled."""
        raw_text = 'https://example.com/article?q=SEO+Tools&lang=de'
        news_feed = {"url1": raw_text}
        result = extracturls_threading.extract_urls(news_feed)
        assert "https://example.com/article?q=SEO+Tools&lang=de" in result

    def test_filter_yimg_urls(self) -> None:
        """URLs containing 'yimg' (Yahoo images) must be filtered out."""
        raw_text = (
            'https://example.com/article,'
            'https://news.yimg.com/asset/image.jpg'
        )
        news_feed = {"url1": raw_text}
        result = extracturls_threading.extract_urls(news_feed)
        assert "https://example.com/article" in result
        assert "https://news.yimg.com" not in str(result)

    def test_handles_binary_content_gracefully(self) -> None:
        """Binary-ish content should not cause a crash."""
        raw_text = '\x00\x01\x02https://example.com/article\xff\xfe'
        news_feed = {"url1": raw_text}
        try:
            result = extracturls_threading.extract_urls(news_feed)
            assert isinstance(result, list)
        except Exception:
            pytest.fail("extract_urls raised unexpectedly on binary content")


# ============================================================================
# download_google_news_threaded (mocked)
# ============================================================================


class TestDownloadGoogleNewsThreaded:
    """``download_google_news_threaded()`` with mocked HTTP calls."""

    def test_returns_dict_with_urls_as_keys(self) -> None:
        """The returned dict must have the input URLs as keys."""
        with patch("googlecrawler.extracturls_threading.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.text = "<html>mock content</html>"

            urls = ["https://news.google.com/test1"]
            result = extracturls_threading.download_google_news_threaded(urls)

            assert isinstance(result, dict)
            assert "https://news.google.com/test1" in result

    def test_stores_content_on_success(self) -> None:
        """Successful downloads should store the response text."""
        with patch("googlecrawler.extracturls_threading.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.text = "<html>success</html>"

            urls = ["https://news.google.com/success"]
            result = extracturls_threading.download_google_news_threaded(urls)

            assert result["https://news.google.com/success"] == "<html>success</html>"

    def test_stores_error_on_failure(self) -> None:
        """Failed downloads should store an error message starting with 'Error:'."""
        with patch("googlecrawler.extracturls_threading.requests.get") as mock_get:
            mock_get.side_effect = ConnectionError("Network error")

            urls = ["https://news.google.com/fail"]
            result = extracturls_threading.download_google_news_threaded(urls)

            assert result["https://news.google.com/fail"].startswith("Error:")

    def test_empty_urls_list(self) -> None:
        """An empty list of URLs should produce an empty dict."""
        result = extracturls_threading.download_google_news_threaded([])
        assert result == {}

    def test_timeout_error_stored_as_error(self) -> None:
        """A requests Timeout should be stored as an Error: entry."""
        from requests.exceptions import Timeout

        with patch(
            "googlecrawler.extracturls_threading.requests.get",
            side_effect=Timeout("Connection timed out"),
        ):
            urls = ["https://news.google.com/timeout"]
            result = extracturls_threading.download_google_news_threaded(urls)

            assert result["https://news.google.com/timeout"].startswith("Error:")
            assert "Timeout" in result["https://news.google.com/timeout"]

    def test_request_exception_stored_as_error(self) -> None:
        """A generic RequestException should be stored as an Error: entry."""
        from requests.exceptions import RequestException

        with patch(
            "googlecrawler.extracturls_threading.requests.get",
            side_effect=RequestException("Bad request"),
        ):
            urls = ["https://news.google.com/bad"]
            result = extracturls_threading.download_google_news_threaded(urls)

            assert result["https://news.google.com/bad"].startswith("Error:")

    def test_unexpected_exception_stored_as_error(self) -> None:
        """Any unexpected exception should be stored as an Error: entry."""
        with patch(
            "googlecrawler.extracturls_threading.requests.get",
            side_effect=RuntimeError("Something unexpected"),
        ):
            urls = ["https://news.google.com/crash"]
            result = extracturls_threading.download_google_news_threaded(urls)

            assert result["https://news.google.com/crash"].startswith("Error:")
