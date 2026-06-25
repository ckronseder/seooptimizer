"""
Tests for the ``DataForSEO.client`` module.

Covers:
- ``consolidate_keywords()`` with duplicate, punctuated, mixed-case, empty input.
- ``extract_keywords_from_dataforseo_response()`` with a mock JSON response.
- Mocking ``RestClient`` to avoid real API calls.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from DataForSEO import client


# ============================================================================
# consolidate_keywords
# ============================================================================


class TestConsolidateKeywords:
    """Normalisation and deduplication of keyword lists."""

    def test_duplicate_keywords_across_case_variants(self) -> None:
        """'SEO', 'seo', 'Seo' should all consolidate to the same entry."""
        result = client.consolidate_keywords(["SEO", "seo", "Seo"])
        # After lowercasing and lemmatization they should collapse to one unique token
        assert isinstance(result, list)
        assert len(result) == 1

    def test_keywords_with_punctuation_and_hyphens(self) -> None:
        """'SEO-Tools' and 'seo tools' should consolidate to the same entry."""
        result = client.consolidate_keywords(["SEO-Tools", "seo tools"])
        assert isinstance(result, list)
        assert len(result) == 1

    def test_mixed_case_whitespace_special_chars(self) -> None:
        """Extra whitespace and special characters are stripped during normalisation."""
        result = client.consolidate_keywords(
            ["  SEO! ", "#marketing", "Suchmaschinenoptimierung  "]
        )
        assert isinstance(result, list)
        # All entries should be non-empty strings
        for entry in result:
            assert isinstance(entry, str)
            assert len(entry) > 0

    def test_empty_list_returns_empty_list(self) -> None:
        """An empty input list must produce an empty output list."""
        result = client.consolidate_keywords([])
        assert result == []

    def test_consolidated_keywords_are_sorted(self) -> None:
        """The returned list should be alphabetically sorted."""
        result = client.consolidate_keywords(["z", "a", "m"])
        assert result == sorted(result)

    def test_lemmatization_normalises_plurals(self) -> None:
        """Words like 'tools' and 'tool' should consolidate."""
        result = client.consolidate_keywords(["SEO tool", "SEO tools"])
        assert isinstance(result, list)
        assert len(result) == 1


# ============================================================================
# extract_keywords_from_dataforseo_response
# ============================================================================


class TestExtractKeywordsFromDataforseoResponse:
    """Parsing the DataForSEO JSON response structure."""

    def test_extracts_keywords_from_valid_response(
        self, mock_dataforseo_response
    ) -> None:
        """Given a well-formed response, all keyword strings are extracted."""
        keywords = client.extract_keywords_from_dataforseo_response(
            mock_dataforseo_response
        )
        assert isinstance(keywords, list)
        assert len(keywords) == 3
        assert "SEO-Tools" in keywords
        assert "Suchmaschinenoptimierung" in keywords
        assert "Keyword-Recherche" in keywords

    def test_empty_response_returns_empty_list(self) -> None:
        """A completely empty dict should gracefully yield an empty list."""
        result = client.extract_keywords_from_dataforseo_response({})
        assert result == []

    def test_missing_tasks_key_returns_empty_list(self) -> None:
        """If 'tasks' is missing, the function must not crash."""
        result = client.extract_keywords_from_dataforseo_response(
            {"unexpected": "data"}
        )
        assert result == []

    def test_missing_items_in_response(self) -> None:
        """A task without 'items' should still return an empty list."""
        response = {"tasks": [{"result": [{"items": []}]}]}
        result = client.extract_keywords_from_dataforseo_response(response)
        assert result == []

    def test_keyword_info_missing_does_not_crash(self) -> None:
        """If 'keyword_info' is missing, the function should not raise."""
        response = {"tasks": [{"result": [{"items": [{"keyword": "test"}]}]}]}
        # This would raise a KeyError inside the try, but the function catches it
        result = client.extract_keywords_from_dataforseo_response(response)
        # The item without keyword_info would cause an error in parsing,
        # but the function should still return whatever was collected
        assert isinstance(result, list)


# ============================================================================
# RestClient mocking
# ============================================================================


class TestRestClientMocked:
    """Verify that RestClient can be mocked to avoid real network calls."""

    def test_rest_client_post_returns_mocked_data(
        self, mock_dataforseo_response
    ) -> None:
        """Mock RestClient.post to return the fixture response."""
        with patch.object(client.RestClient, "post", return_value=mock_dataforseo_response):
            mock_username = "fake_user"
            mock_password = "fake_pass"
            rc = client.RestClient(mock_username, mock_password)
            response = rc.post("/v3/test/path", {"key": "value"})

            assert response == mock_dataforseo_response
            keywords = client.extract_keywords_from_dataforseo_response(response)
            assert len(keywords) == 3

    def test_rest_client_get_returns_mocked_data(self) -> None:
        """Mock RestClient.get to return a predictable dict."""
        expected = {"status": "ok"}
        with patch.object(client.RestClient, "get", return_value=expected):
            rc = client.RestClient("u", "p")
            result = rc.get("/v3/status")
            assert result == expected

    def test_rest_client_post_raises_on_network_error(self) -> None:
        """Simulate a network failure on RestClient.post."""
        with patch.object(
            client.RestClient,
            "post",
            side_effect=ConnectionError("API unreachable"),
        ):
            rc = client.RestClient("u", "p")
            with pytest.raises(ConnectionError, match="API unreachable"):
                rc.post("/v3/test", {})

    def test_consolidate_after_extract_integration(
        self, mock_dataforseo_response
    ) -> None:
        """End-to-end: extract -> consolidate should produce deduplicated list."""
        keywords = client.extract_keywords_from_dataforseo_response(
            mock_dataforseo_response
        )
        consolidated = client.consolidate_keywords(keywords)
        assert isinstance(consolidated, list)
        assert len(consolidated) <= len(keywords)  # deduplication may reduce count
        for kw in consolidated:
            assert isinstance(kw, str)


# ============================================================================
# RestClient.request() — actual HTTP method dispatch & error handling
# ============================================================================


class TestRestClientRequestMethod:
    """Exercise the actual ``request()`` implementation with mocked ``requests``."""

    def test_get_request_dispatch(self) -> None:
        """A GET call should invoke ``requests.get`` with the correct URL."""
        with patch("DataForSEO.client.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "ok"}
            mock_get.return_value = mock_response

            rc = client.RestClient("user", "pass")
            result = rc.get("/v3/test")

            mock_get.assert_called_once()
            url_arg = mock_get.call_args[0][0]
            assert "/v3/test" in url_arg
            assert result == {"status": "ok"}

    def test_post_request_with_dict_data(self) -> None:
        """A POST with a dict should use ``requests.post(json=...)``."""
        with patch("DataForSEO.client.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"result": "ok"}
            mock_post.return_value = mock_response

            rc = client.RestClient("user", "pass")
            post_data = {"keyword": "test"}
            result = rc.post("/v3/post", post_data)

            mock_post.assert_called_once()
            # When passing a dict, the ``json`` kwarg is used
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs.get("json") == post_data
            assert result == {"result": "ok"}

    def test_post_request_with_string_data(self) -> None:
        """A POST with a string should use ``requests.post(data=...)``."""
        with patch("DataForSEO.client.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"result": "ok"}
            mock_post.return_value = mock_response

            rc = client.RestClient("user", "pass")
            result = rc.post("/v3/post", '{"keyword": "test"}')

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert "json" not in call_kwargs
            assert call_kwargs.get("data") == '{"keyword": "test"}'
            assert result == {"result": "ok"}

    def test_request_unsupported_method_raises(self) -> None:
        """An unsupported HTTP method should raise ``ValueError``."""
        rc = client.RestClient("u", "p")
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            rc.request("/path", "DELETE")

    def test_request_timeout_raises(self) -> None:
        """A ``requests.Timeout`` should propagate."""
        with patch("DataForSEO.client.requests.get", side_effect=requests.exceptions.Timeout("timeout")):
            rc = client.RestClient("u", "p")
            with pytest.raises(requests.exceptions.Timeout):
                rc.get("/v3/test")

    def test_request_http_error_raises(self) -> None:
        """A 4xx/5xx HTTP response should raise."""
        from requests.exceptions import HTTPError
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error": "unauthorized"}'
        http_error = HTTPError("401 Unauthorized")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with patch("DataForSEO.client.requests.get", return_value=mock_response):
            rc = client.RestClient("u", "p")
            with pytest.raises(HTTPError):
                rc.get("/v3/test")

    def test_request_generic_exception_raises(self) -> None:
        """A non-requests exception should still propagate."""
        with patch("DataForSEO.client.requests.get", side_effect=ConnectionError("No route to host")):
            rc = client.RestClient("u", "p")
            with pytest.raises(ConnectionError):
                rc.get("/v3/test")

    def test_auth_header_format(self) -> None:
        """The Basic auth header should be set correctly."""
        rc = client.RestClient("testuser", "testpass")
        assert "Authorization" in rc.auth_headers
        assert rc.auth_headers["Authorization"].startswith("Basic ")
        # Verify the encoding: base64 of "testuser:testpass"
        import base64
        expected_b64 = base64.b64encode(b"testuser:testpass").decode("ascii")
        assert rc.auth_headers["Authorization"] == f"Basic {expected_b64}"

    def test_http_error_logs_response_body(self, caplog) -> None:
        """When an HTTPError occurs, the response status and body should be logged."""
        import logging
        from requests.exceptions import HTTPError

        caplog.set_level(logging.ERROR)

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = '{"error": "forbidden"}'
        http_error = HTTPError("403 Forbidden")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with patch("DataForSEO.client.requests.get", return_value=mock_response):
            rc = client.RestClient("u", "p")
            with pytest.raises(HTTPError):
                rc.get("/v3/test")

        # The error logging should include the status code
        assert any("403" in record.getMessage() for record in caplog.records)

    def test_http_error_with_no_response_body(self, caplog) -> None:
        """When an HTTPError occurs and response text fails, it should not crash."""
        import logging
        from requests.exceptions import HTTPError

        caplog.set_level(logging.ERROR)

        mock_response = MagicMock()
        mock_response.status_code = 500
        # Make accessing text raise an exception
        type(mock_response).text = property(
            lambda s: (_ for _ in ()).throw(Exception("can't read"))
        )
        http_error = HTTPError("500 Server Error")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error

        with patch("DataForSEO.client.requests.get", return_value=mock_response):
            rc = client.RestClient("u", "p")
            with pytest.raises(HTTPError):
                rc.get("/v3/test")
