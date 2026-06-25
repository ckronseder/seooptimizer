import logging
import re
from pathlib import Path

import google.generativeai as genai
from pydantic import BaseModel
from config import config

logger = logging.getLogger("Summary")

# Path to the prompt template file (alongside this module)
_PROMPT_PATH = Path(__file__).resolve().parent / "prompt.txt"


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
    genai.configure(api_key=config.GEM_API)

    if not text:
        return None

    # Convert list of texts to a single string if needed
    if isinstance(text, list):
        text = "\n\n---\n\n".join(filter(None, text))
    if isinstance(search_words, list):
        search_words = ", ".join(search_words)

    try:
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json",
        )
        model = genai.GenerativeModel(model, generation_config=generation_config)
        prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = prompt_template.format(text=text, search_words=search_words)

        response = model.generate_content(
            prompt, request_options={"timeout": 180},
        )

        # Check for safety blocks
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason
            if finish_reason == 3:  # SAFETY
                logger.warning(
                    "Response blocked for safety reasons (finish_reason=3)"
                )
                return None

        # Parse structured response
        try:
            parsed = WebsiteStructures.model_validate_json(response.text)
            return [site.model_dump() for site in parsed.websites]
        except Exception:
            # Fallback: try to extract JSON from markdown code blocks
            logger.warning("Direct JSON parsing failed; trying regex fallback...")
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response.text)
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
                getattr(response.candidates[0], "finish_reason", "N/A")
                if response.candidates else "NO_CANDIDATES",
                len(prompt),
                article_count,
                response.text if response.text else "EMPTY",
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