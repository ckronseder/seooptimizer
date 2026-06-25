"""
Vector database module for article embedding storage and semantic retrieval.

Uses ChromaDB (persistent, file-based) and sentence-transformers for
computing and storing article embeddings.
"""

import datetime
import hashlib
import logging
from pathlib import Path
from typing import Any

import chromadb
import streamlit as st
from chromadb.config import Settings

logger = logging.getLogger("VectorDB")

# Paths
_CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_db"

# Embedding model name (small, fast, good quality)
_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


@st.cache_resource
def _get_embedder():
    """Load and cache the sentence-transformers embedding model."""
    from sentence_transformers import SentenceTransformer
    logger.info("Loading embedding model: %s", _EMBEDDING_MODEL)
    return SentenceTransformer(_EMBEDDING_MODEL)


def _get_collection():
    """Get or create the ChromaDB collection for articles."""
    _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(_CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection("articles")


def compute_search_id(topic: str, keywords: list[str]) -> str:
    """Generate a deterministic ID for a topic + keywords combination.

    Args:
        topic: The search topic string.
        keywords: List of keyword strings.

    Returns:
        A 16-character hex string uniquely identifying this search.
    """
    raw = (
        f"{topic.strip().lower()}:"
        f"{','.join(sorted(kw.strip().lower() for kw in keywords))}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def store_articles(articles: dict[str, Any], search_id: str = "") -> int:
    """Store article embeddings in ChromaDB.

    Only articles with the same ``search_id`` are removed before inserting
    the new batch, preserving cached articles from other searches.

    Args:
        articles: Dict mapping URL -> parsed article data (must have 'text' key).
        search_id: Tag to group articles by search query (default ``""``).

    Returns:
        Number of articles stored.
    """
    embedder = _get_embedder()
    collection = _get_collection()

    urls = []
    texts = []
    metadatas = []

    for url, data in articles.items():
        if not isinstance(data, dict):
            continue
        article_text = data.get("text", "")
        if not article_text:
            continue
        urls.append(url)
        texts.append(article_text[:5000])  # truncate to avoid OOM
        metadatas.append({
            "url": url,
            "title": data.get("title", "")[:200],
            "search_id": search_id,
            "cached_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    if not urls:
        return 0

    logger.info("Computing embeddings for %d articles...", len(urls))
    embeddings = embedder.encode(texts, show_progress_bar=False).tolist()

    # Delete only stale articles for this search_id (preserve other searches)
    collection.delete(where={"search_id": search_id})

    collection.add(
        ids=urls,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=texts,
    )
    logger.info("Stored %d articles in vector DB", len(urls))
    return len(urls)


def get_cached_articles(
    search_id: str,
    min_count: int = 5,
    max_cache_hours: float = 24,
) -> list[dict] | None:
    """Check if we have cached articles for this search_id.

    Articles older than ``max_cache_hours`` are treated as expired and
    filtered out.  If fewer than ``min_count`` remain after filtering
    (or the metadata is missing / unparseable) the cache is considered
    a miss and ``None`` is returned.

    Args:
        search_id: The search ID to look up.
        min_count: Minimum number of articles required for a cache hit.
        max_cache_hours: Max age in hours for a cached article to be
            considered valid (default 24).

    Returns:
        List of article dicts if cache hit and enough articles, None otherwise.
    """
    collection = _get_collection()

    results = collection.get(where={"search_id": search_id})

    if not results or not results["ids"] or len(results["ids"]) < min_count:
        logger.info(
            "Cache miss for search_id=%s (%d articles, need %d)",
            search_id,
            len(results["ids"]) if results else 0,
            min_count,
        )
        return None

    # Filter by cache freshness
    now = datetime.datetime.now(datetime.timezone.utc)
    valid_articles: list[dict] = []
    for i in range(len(results["ids"])):
        cached_at_str = results["metadatas"][i].get("cached_at", "")
        if not cached_at_str:
            logger.debug("Article %s has no cached_at — treating as expired", results["ids"][i])
            continue
        try:
            cached_at = datetime.datetime.fromisoformat(cached_at_str)
            age_hours = (now - cached_at).total_seconds() / 3600
            if age_hours > max_cache_hours:
                logger.debug(
                    "Article %s is %.1f hours old (max %.1f) — expired",
                    results["ids"][i],
                    age_hours,
                    max_cache_hours,
                )
                continue
        except (ValueError, TypeError):
            logger.debug("Article %s has malformed cached_at '%s' — treating as expired",
                         results["ids"][i], cached_at_str)
            continue

        valid_articles.append({
            "url": results["ids"][i],
            "title": results["metadatas"][i].get("title", ""),
            "text": results["documents"][i],
        })

    if len(valid_articles) < min_count:
        logger.info(
            "Cache miss for search_id=%s (only %d valid after freshness filter, need %d)",
            search_id,
            len(valid_articles),
            min_count,
        )
        return None

    logger.info("Cache hit for search_id=%s (%d articles)", search_id, len(valid_articles))
    return valid_articles


def query_articles(query_text: str, top_k: int = 10) -> list[dict]:
    """Retrieve the most relevant articles for a query.

    Args:
        query_text: The search query (e.g., topic + keywords).
        top_k: Number of articles to return.

    Returns:
        List of dicts with 'url', 'title', 'text', 'score' keys.
    """
    embedder = _get_embedder()
    collection = _get_collection()

    if collection.count() == 0:
        return []

    query_embedding = embedder.encode([query_text]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
    )

    articles = []
    for i in range(len(results["ids"][0])):
        articles.append({
            "url": results["ids"][0][i],
            "title": results["metadatas"][0][i].get("title", ""),
            "text": results["documents"][0][i],
            "score": results["distances"][0][i] if "distances" in results else 0,
        })

    return articles


def collection_size() -> int:
    """Return the number of articles currently stored."""
    return _get_collection().count()
