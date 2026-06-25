"""
Shared fixtures and configuration for the SEOOptimizer test suite.

Adds the project root to ``sys.path`` so that all application modules
can be imported as ``from config import config`` etc.
"""

import sys
from pathlib import Path

import nltk
import pytest

# ---------------------------------------------------------------------------
# Ensure required NLTK data is available (used by DataForSEO/client.py)
# ---------------------------------------------------------------------------
# SSL certificates may not be configured correctly on macOS for NLTK's
# downloader; point to certifi's bundle as a reliable fallback.
import certifi
import os as _os
_os.environ.setdefault("SSL_CERT_FILE", certifi.where())
_os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

_NLTK_RESOURCES = [
    ("tokenizers/punkt", "punkt"),
    ("corpora/wordnet", "wordnet"),
    ("tokenizers/punkt_tab", "punkt_tab"),
]


def _ensure_nltk_data() -> None:
    """Download missing NLTK resource without prompting."""
    for resource_id, resource_name in _NLTK_RESOURCES:
        try:
            nltk.data.find(resource_id)
        except LookupError:
            nltk.download(resource_name, quiet=True)


_ensure_nltk_data()

# Ensure the required punkt_tab/english tokenizers are present.
# The punkt_tab resource name changed in newer NLTK versions.
try:
    nltk.data.find("tokenizers/punkt_tab/english/")
except LookupError:
    nltk.download("punkt_tab", quiet=True)

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so we can import application modules
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_keywords() -> list:
    """A small list of realistic German keywords (as returned by DataForSEO)."""
    return [
        "SEO Tools",
        "seo-tools",
        "SEO-Tools",
        "Seo tools",
        "Suchmaschinenoptimierung",
        "suchmaschinenoptimierung",
        "keyword recherche",
        "Keyword-Recherche",
    ]


@pytest.fixture
def sample_article_data() -> dict:
    """Simulated parsed article dict (as returned by newspaper4k)."""
    return {
        "https://example.com/news/ai-2025": {
            "title": "AI Advances in 2025",
            "text": "Artificial intelligence continues to reshape industries worldwide.",
            "authors": ["Jane Doe"],
            "publish_date": "2025-06-01",
            "top_image": "https://example.com/img.jpg",
            "movies": [],
            "url": "https://example.com/news/ai-2025",
        },
        "https://example.com/news/tech-boom": {
            "title": "Tech Boom Expected",
            "text": "The technology sector is experiencing unprecedented growth.",
            "authors": ["John Smith"],
            "publish_date": "2025-06-02",
            "top_image": "",
            "movies": [],
            "url": "https://example.com/news/tech-boom",
        },
    }


@pytest.fixture
def sample_html_with_urls() -> str:
    """HTML snippet resembling a Google News search result page."""
    return """
    <html>
    <body>
    <a href="https://news.google.com/articles/123">Google News wrapper</a>
    <a href="https://www.example.com/article/seo-tips-2025">SEO Tips 2025</a>
    <a href="https://www.techradar.com/news/ai-breakthrough">AI Breakthrough</a>
    <img src="https://example.com/image.jpg"/>
    <a href="https://www.google.com/search?q=test">Google search result</a>
    <a href="https://www.bbc.com/news/technology-123456">BBC Tech Article</a>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_no_urls() -> str:
    """HTML with no valid article URLs."""
    return """
    <html>
    <body>
    <p>No links here!</p>
    <img src="https://example.com/image.jpg"/>
    </body>
    </html>
    """


@pytest.fixture
def mock_dataforseo_response() -> dict:
    """A minimal, realistic DataForSEO API response."""
    return {
        "tasks": [
            {
                "result": [
                    {
                        "items": [
                            {
                                "keyword": "SEO-Tools",
                                "keyword_info": {
                                    "competition_level": "MEDIUM",
                                },
                            },
                            {
                                "keyword": "Suchmaschinenoptimierung",
                                "keyword_info": {
                                    "competition_level": "HIGH",
                                },
                            },
                            {
                                "keyword": "Keyword-Recherche",
                                "keyword_info": {
                                    "competition_level": "LOW",
                                },
                            },
                        ]
                    }
                ]
            }
        ]
    }
