"""
Tests for the ``newssummary.summary`` module.

Covers:
- ``summarize_text()`` with mocked ``google.genai.Client``.
- Valid inputs, empty text, empty search_words.
- Verification that the prompt contains expected content.
- Structured output parsing via Pydantic schemas.
"""

import json
from unittest.mock import MagicMock, patch

from google.genai import types

from newssummary import summary


def _valid_json_response(
    website_number: int = 1,
    title: str = "Test Title",
    summary_text: str = "Test summary.",
    qa_count: int = 1,
) -> str:
    """Build a valid JSON string that matches ``WebsiteStructures`` schema."""
    qa_list = [
        {"question": f"Q{i}?", "answer": f"A{i}."}
        for i in range(1, qa_count + 1)
    ]
    data = {
        "websites": [
            {
                "website_number": website_number,
                "title": title,
                "summary": summary_text,
                "qa_list": qa_list,
                "sources": ["https://example.com"],
            }
        ]
    }
    return json.dumps(data)


def _build_mock_response(
    text: str,
    finish_reason=types.FinishReason.STOP,
) -> types.GenerateContentResponse:
    """Build a real ``GenerateContentResponse`` with the given text and finish reason."""
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(parts=[types.Part(text=text)]),
                finish_reason=finish_reason,
            )
        ]
    )


class TestSummarizeText:
    """``summarize_text()`` with mocked Gemini API client."""

    # ── Successful calls ────────────────────────────────────────────────

    def test_returns_parsed_list_of_dicts(self) -> None:
        """When the model returns a valid JSON response matching the schema,
        ``summarize_text`` must return a list of dicts with the expected keys."""
        json_str = _valid_json_response(website_number=1, title="SEO Test")
        mock_response = _build_mock_response(json_str)

        with patch.object(summary, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            result = summary.summarize_text(
                "Some article content.", ["SEO", "test"]
            )

            assert isinstance(result, list)
            assert len(result) == 1
            site = result[0]
            assert site["website_number"] == 1
            assert site["title"] == "SEO Test"
            assert site["summary"] == "Test summary."
            assert "qa_list" in site
            assert "sources" in site

    def test_prompt_contains_search_words(self) -> None:
        """The generated prompt must include the provided search words."""
        with patch.object(summary, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.models.generate_content.return_value = _build_mock_response(
                "output"
            )

            summary.summarize_text("Article body.", ["keyword1", "keyword2"])

            # Capture the prompt that was passed to generate_content
            call_args = mock_client.models.generate_content.call_args
            assert call_args is not None
            prompt = call_args.kwargs.get("contents", "")
            assert "keyword1" in prompt
            assert "keyword2" in prompt

    def test_prompt_contains_text_content(self) -> None:
        """The generated prompt must include the actual article text."""
        article_text = "This is the article body content for testing."

        with patch.object(summary, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.models.generate_content.return_value = _build_mock_response(
                "output"
            )

            summary.summarize_text(article_text, ["test"])

            call_args = mock_client.models.generate_content.call_args
            assert call_args is not None
            prompt = call_args.kwargs.get("contents", "")
            assert article_text in prompt

    def test_list_of_texts_joined(self) -> None:
        """When ``text`` is a list, the function must join them before prompting."""
        texts = ["First article body.", "Second article body."]

        with patch.object(summary, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.models.generate_content.return_value = _build_mock_response(
                "output"
            )

            summary.summarize_text(texts, ["test"])

            call_args = mock_client.models.generate_content.call_args
            assert call_args is not None
            prompt = call_args.kwargs.get("contents", "")
            assert "First article body." in prompt
            assert "Second article body." in prompt
            # The separator between texts should be present
            assert "---" in prompt

    def test_list_of_search_words_joined(self) -> None:
        """When ``search_words`` is a list, it must be joined into a comma-separated string."""
        with patch.object(summary, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.models.generate_content.return_value = _build_mock_response(
                "output"
            )

            summary.summarize_text("Article.", ["SEO", "tools", "2025"])

            call_args = mock_client.models.generate_content.call_args
            assert call_args is not None
            prompt = call_args.kwargs.get("contents", "")
            # The search words should appear joined
            assert "SEO, tools, 2025" in prompt or all(
                w in prompt for w in ["SEO", "tools", "2025"]
            )

    # ── Edge cases ──────────────────────────────────────────────────────

    def test_empty_text_returns_none(self) -> None:
        """When ``text`` is empty/falsy, the function should return ``None``
        without calling the Gemini API."""
        result = summary.summarize_text("", ["test"])
        assert result is None

    def test_none_text_returns_none(self) -> None:
        """When ``text`` is None (falsy), the function should return ``None``."""
        result = summary.summarize_text(None, ["test"])
        assert result is None

    def test_empty_text_with_empty_search_words(self) -> None:
        """Both empty text and empty search words — should return ``None``."""
        result = summary.summarize_text("", [])
        assert result is None

    # ── Error handling ──────────────────────────────────────────────────

    def test_gemini_api_exception_returns_none(self) -> None:
        """If the Gemini API raises an exception, the function must return
        ``None``."""
        with patch.object(summary, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.models.generate_content.side_effect = RuntimeError(
                "API rate limit exceeded"
            )

            result = summary.summarize_text("Article body.", ["test"])

            assert result is None

    def test_client_creation_failure_returns_none(self) -> None:
        """If creating the client itself fails, return ``None``."""
        with patch.object(
            summary,
            "_get_client",
            side_effect=Exception("Client creation failed"),
        ):
            result = summary.summarize_text("Article body.", ["test"])
            assert result is None

    def test_safety_block_returns_none(self) -> None:
        """A safety-blocked response must return ``None``."""
        mock_response = _build_mock_response(
            "blocked", finish_reason=types.FinishReason.SAFETY
        )

        with patch.object(summary, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            result = summary.summarize_text("Article body.", ["test"])
            assert result is None

    def test_empty_response_text_returns_none(self) -> None:
        """A response with no text parts must return ``None``."""
        empty_response = types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(parts=[types.Part(text="")]),
                    finish_reason=types.FinishReason.STOP,
                )
            ]
        )

        with patch.object(summary, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.models.generate_content.return_value = empty_response

            result = summary.summarize_text("Article body.", ["test"])
            assert result is None
