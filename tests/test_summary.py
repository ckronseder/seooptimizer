"""
Tests for the ``newssummary.summary`` module.

Covers:
- ``summarize_text()`` with mocked ``google.generativeai``.
- Valid inputs, empty text, empty search_words.
- Verification that the prompt contains expected content.
- Structured output parsing via Pydantic schemas.
"""

import json
from unittest.mock import MagicMock, patch

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


class TestSummarizeText:
    """``summarize_text()`` with mocked Gemini API."""

    def _mock_gemini_response(
        self,
        text: str = "Mocked summary response",
        finish_reason: int = 1,
    ):
        """Helper: return a mock GenerativeModel whose ``generate_content``
        returns a response with the given text and finish reason."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = text
        mock_candidate = MagicMock()
        mock_candidate.finish_reason = finish_reason
        mock_response.candidates = [mock_candidate]
        mock_model.generate_content.return_value = mock_response
        return mock_model

    # ── Successful calls ────────────────────────────────────────────────

    def test_returns_parsed_list_of_dicts(self) -> None:
        """When the model returns a valid JSON response matching the schema,
        ``summarize_text`` must return a list of dicts with the expected keys."""
        json_str = _valid_json_response(website_number=1, title="SEO Test")

        with patch.object(summary.genai, "GenerativeModel") as mock_model_cls:
            mock_model = self._mock_gemini_response(json_str)
            mock_model_cls.return_value = mock_model

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
        with patch.object(summary.genai, "GenerativeModel") as mock_model_cls:
            mock_model = self._mock_gemini_response("output")
            mock_model_cls.return_value = mock_model

            summary.summarize_text("Article body.", ["keyword1", "keyword2"])

            # Capture the prompt that was passed to generate_content
            call_args = mock_model.generate_content.call_args
            assert call_args is not None
            prompt = call_args[0][0]
            assert "keyword1" in prompt
            assert "keyword2" in prompt

    def test_prompt_contains_text_content(self) -> None:
        """The generated prompt must include the actual article text."""
        article_text = "This is the article body content for testing."

        with patch.object(summary.genai, "GenerativeModel") as mock_model_cls:
            mock_model = self._mock_gemini_response("output")
            mock_model_cls.return_value = mock_model

            summary.summarize_text(article_text, ["test"])

            call_args = mock_model.generate_content.call_args
            assert call_args is not None
            prompt = call_args[0][0]
            assert article_text in prompt

    def test_list_of_texts_joined(self) -> None:
        """When ``text`` is a list, the function must join them before prompting."""
        texts = ["First article body.", "Second article body."]

        with patch.object(summary.genai, "GenerativeModel") as mock_model_cls:
            mock_model = self._mock_gemini_response("output")
            mock_model_cls.return_value = mock_model

            summary.summarize_text(texts, ["test"])

            call_args = mock_model.generate_content.call_args
            assert call_args is not None
            prompt = call_args[0][0]
            assert "First article body." in prompt
            assert "Second article body." in prompt
            # The separator between texts should be present
            assert "---" in prompt

    def test_list_of_search_words_joined(self) -> None:
        """When ``search_words`` is a list, it must be joined into a comma-separated string."""
        with patch.object(summary.genai, "GenerativeModel") as mock_model_cls:
            mock_model = self._mock_gemini_response("output")
            mock_model_cls.return_value = mock_model

            summary.summarize_text("Article.", ["SEO", "tools", "2025"])

            call_args = mock_model.generate_content.call_args
            assert call_args is not None
            prompt = call_args[0][0]
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
        with patch.object(summary.genai, "GenerativeModel") as mock_model_cls:
            mock_model = MagicMock()
            mock_model.generate_content.side_effect = RuntimeError(
                "API rate limit exceeded"
            )
            mock_model_cls.return_value = mock_model

            result = summary.summarize_text("Article body.", ["test"])

            assert result is None

    def test_model_creation_failure_returns_none(self) -> None:
        """If creating the GenerativeModel itself fails, return ``None``."""
        with patch.object(
            summary.genai,
            "GenerativeModel",
            side_effect=Exception("Model not available"),
        ):
            result = summary.summarize_text("Article body.", ["test"])
            assert result is None
