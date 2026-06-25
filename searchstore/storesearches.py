"""
Search History Persistence Layer

Stores and retrieves search results using TinyDB (a lightweight JSON-based
document database).  Each search record contains:
  - timestamp (ISO-8601 string)
  - topic (the user-provided search string)
  - keywords (the selected keyword list)
  - result (the Gemini response text)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from tinydb import TinyDB, Query

# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------
_DB_PATH = "search_history.json"
_db = TinyDB(_DB_PATH)
_search_table = _db.table("searches")
_SearchQuery = Query()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_search(
    topic: str,
    keywords: List[str],
    result: str,
) -> int:
    """Persist a search record.

    Args:
        topic: The user's search topic string.
        keywords: The list of keywords selected by the user.
        result: The Gemini-generated response text.

    Returns:
        The document ID (``doc_id``) of the newly inserted record.
    """
    record: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic,
        "keywords": keywords,
        "result": result,
    }
    doc_id = _search_table.insert(record)
    return doc_id


def get_search_history(
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all past searches, newest first.

    Args:
        limit: Maximum number of records to return (``None`` = no limit).

    Returns:
        A list of search record dicts, each containing ``timestamp``, ``topic``,
        ``keywords``, ``result``, and ``doc_id``.
    """
    records = sorted(
        _search_table.all(),
        key=lambda doc: doc.get("timestamp", ""),
        reverse=True,
    )
    if limit is not None:
        records = records[:limit]
    # Include the TinyDB document ID so the UI can uniquely identify each record
    return [{**doc, "doc_id": doc.doc_id} for doc in records]


def get_search_by_topic(topic: str) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent search for a given topic.

    Args:
        topic: The topic string to look up.

    Returns:
        The most recent matching record, or ``None`` if no match is found.
    """
    results = _search_table.search(_SearchQuery.topic == topic)
    if not results:
        return None
    # Return the newest record for this topic
    return max(results, key=lambda doc: doc.get("timestamp", ""))


def delete_search(doc_id: int) -> bool:
    """Delete a search record by its document ID.

    Args:
        doc_id: The TinyDB document ID to remove.

    Returns:
        True if a record was removed, False otherwise.
    """
    try:
        removed = _search_table.remove(doc_ids=[doc_id])
        return len(removed) > 0
    except KeyError:
        # TinyDB raises KeyError when the document ID does not exist
        return False
