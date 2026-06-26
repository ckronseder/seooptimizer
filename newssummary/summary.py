import logging
import re
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel
from config import config

logger = logging.getLogger("Summary")

# Path to the prompt template file (alongside this module)
_PROMPT_PATH = Path(__file__).resolve().parent / "prompt.txt"

# Cached API client (lazily created)
_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEM_API)
    return _client


class QAPair(BaseModel):
    question: str
    answer: str


class WebsiteStructure(BaseModel):
    website_number: int
    title: str
    summary: str
    qa_list: list[QAPair]
    sources: list[str]


class WebsiteStructures(BaseModel):
    websites: list[WebsiteStructure]


def _extract_text(response) -> str | None:
    """Extract response text from a ``GenerateContentResponse``.

    Handles both the new SDK (``candidates[0].content.parts[0].text``) and
    the legacy SDK (``response.text``) as a safety net during migration.
    """
    text = getattr(response, "text", None)
    if text:
        return text
    try:
        return response.candidates[0].content.parts[0].text
    except (IndexError, AttributeError, TypeError):
        return None


def summarize_text(
    text, search_words, model="gemini-2.5-flash"
) -> list[dict] | None:
    """Summarizes the given text using the Gemini model with structured output.

    The LLM prompt is loaded from ``prompt.txt`` at runtime. The response is
    parsed into a list of dictionaries matching the ``WebsiteStructure`` schema.

    Args:
        text: Concatenated article text (or list of article texts).
        search_words: List of keywords to incorporate.

    Returns:
        A list of dicts (each representing a website structure), or ``None`` if
        the input was empty, the response was blocked for safety, or an error
        occurred.
    """
    if not text:
        return None

    # Convert list of texts to a single string if needed
    if isinstance(text, list):
        text = "\n\n---\n\n".join(filter(None, text))
    if isinstance(search_words, list):
        search_words = ", ".join(search_words)

    try:
        client = _get_client()
        prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = prompt_template.format(text=text, search_words=search_words)

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                http_options=types.HttpOptions(timeout=180_000),
            ),
        )

        # Check for safety blocks
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason
            if finish_reason == types.FinishReason.SAFETY:
                logger.warning(
                    "Response blocked for safety reasons (finish_reason=SAFETY)"
                )
                return None

        resp_text = _extract_text(response)
        if not resp_text:
            logger.error("Gemini response has no text content")
            return None

        # Parse structured response
        try:
            parsed = WebsiteStructures.model_validate_json(resp_text)
            return [site.model_dump() for site in parsed.websites]
        except Exception:
            # Fallback: try to extract JSON from markdown code blocks
            logger.warning("Direct JSON parsing failed; trying regex fallback...")
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", resp_text)
            if match:
                try:
                    parsed = WebsiteStructures.model_validate_json(match.group(1))
                    return [site.model_dump() for site in parsed.websites]
                except Exception:
                    pass
            # Count articles from the already-joined text
            article_count = text.count("\n\n---\n\n") + 1 if text else 0
            logger.error(
                "Failed to parse Gemini response as JSON. "
                "Finish reason: %s. Prompt length: %d chars. "
                "Article count: %d. Full response:\n%s",
                response.candidates[0].finish_reason
                if response.candidates else "NO_CANDIDATES",
                len(prompt),
                article_count,
                resp_text if resp_text else "EMPTY",
            )
            return None
    except Exception as e:
        logger.exception("Error summarizing text: %s", e)
        return None


#=================
if __name__ == "__main__":
    articles_contents = [
        "Database engine developer MongoDB has acquired Voyage AI in order to help enterprises reduce hallucinations in AI-powered applications.",
        "In this episode of \"My First 16,\" a16z Partner Seema Amble talks with MongoDB and Viam co-founder Eliot Horowitz.",
        "",
        "We recently published a list of 10 AI News Investors Probably Missed.",
        "Earnings per share: $1.28 adjusted vs. 66 cents expected. Revenue: $548.4 million.",
    ]

    result = summarize_text(
        articles_contents,
        ["mongoDB", "acquisition", "AI powered applications"],
    )

    if result:
        import pprint

        pprint.pprint(result)
    else:
        print("No summary returned.")