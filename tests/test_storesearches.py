"""
Tests for the ``searchstore.storesearches`` module.

Covers:
- ``save_search()``, ``get_search_history()``, ``get_search_by_topic()``.
- Uses ``tmp_path`` to avoid polluting the real filesystem.
"""

from pathlib import Path

import pytest


class TestStoresearches:
    """All store-search operations backed by a temporary TinyDB database."""

    # ------------------------------------------------------------------
    # Helper: patch TinyDB to use a temp file
    # ------------------------------------------------------------------

    @pytest.fixture(autouse=True)
    def _patch_db_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Before each test, redirect TinyDB to a temporary JSON file."""
        self._db_file = tmp_path / "test_search_history.json"
        monkeypatch.setattr(
            "searchstore.storesearches._DB_PATH", str(self._db_file)
        )
        # Also reset the module-level TinyDB instance by clearing its tables
        from searchstore import storesearches
        storesearches._db = storesearches.TinyDB(str(self._db_file))
        storesearches._search_table = storesearches._db.table("searches")

    # ------------------------------------------------------------------
    # save_search
    # ------------------------------------------------------------------

    def test_save_search_returns_doc_id(self) -> None:
        """``save_search`` should return a positive integer document ID."""
        from searchstore import storesearches
        doc_id = storesearches.save_search(
            topic="AI", keywords=["AI", "artificial"], result="Some result"
        )
        assert isinstance(doc_id, int)
        assert doc_id > 0

    def test_saved_record_contains_expected_fields(self) -> None:
        """The record persisted by ``save_search`` must contain timestamp,
        topic, keywords, and result."""
        from searchstore import storesearches
        storesearches.save_search(
            topic="Test Topic",
            keywords=["kw1", "kw2"],
            result="Test result text",
        )
        all_records = storesearches._search_table.all()
        assert len(all_records) == 1
        record = all_records[0]
        assert "timestamp" in record
        assert record["topic"] == "Test Topic"
        assert record["keywords"] == ["kw1", "kw2"]
        assert record["result"] == "Test result text"

    # ------------------------------------------------------------------
    # get_search_history
    # ------------------------------------------------------------------

    def test_get_search_history_returns_newest_first(self) -> None:
        """History must be ordered newest-first by timestamp."""
        from searchstore import storesearches
        storesearches.save_search(
            topic="Older", keywords=["old"], result="Old result"
        )
        storesearches.save_search(
            topic="Newer", keywords=["new"], result="New result"
        )

        history = storesearches.get_search_history()
        assert len(history) == 2
        # Due to ISO-8601 ordering, the second save has a later timestamp
        assert history[0]["topic"] == "Newer"
        assert history[1]["topic"] == "Older"

    def test_get_search_history_with_limit(self) -> None:
        """Passing a ``limit`` should truncate the results."""
        from searchstore import storesearches
        for i in range(5):
            storesearches.save_search(
                topic=f"Topic {i}",
                keywords=[f"kw{i}"],
                result=f"Result {i}",
            )
        history = storesearches.get_search_history(limit=3)
        assert len(history) == 3

    def test_get_search_history_empty(self) -> None:
        """When no searches exist, history should be an empty list."""
        from searchstore import storesearches
        history = storesearches.get_search_history()
        assert history == []

    def test_get_search_history_no_limit_returns_all(self) -> None:
        """Without a limit, all records should be returned."""
        from searchstore import storesearches
        for i in range(3):
            storesearches.save_search(
                topic=f"Topic {i}", keywords=[], result=""
            )
        history = storesearches.get_search_history()
        assert len(history) == 3

    # ------------------------------------------------------------------
    # get_search_by_topic
    # ------------------------------------------------------------------

    def test_get_search_by_topic_finds_exact_match(self) -> None:
        """Searching for an existing topic should return that record."""
        from searchstore import storesearches
        storesearches.save_search(
            topic="Machine Learning",
            keywords=["ML", "deep learning"],
            result="ML result",
        )
        record = storesearches.get_search_by_topic("Machine Learning")
        assert record is not None
        assert record["topic"] == "Machine Learning"
        assert record["keywords"] == ["ML", "deep learning"]

    def test_get_search_by_topic_returns_newest(self) -> None:
        """If there are multiple records for the same topic, the newest
        should be returned."""
        from searchstore import storesearches
        storesearches.save_search(
            topic="SEO", keywords=["old"], result="Old result"
        )
        storesearches.save_search(
            topic="SEO", keywords=["new"], result="New result"
        )
        record = storesearches.get_search_by_topic("SEO")
        assert record is not None
        assert record["result"] == "New result"

    def test_get_search_by_topic_nonexistent(self) -> None:
        """Searching for a non-existent topic returns ``None``."""
        from searchstore import storesearches
        record = storesearches.get_search_by_topic("DoesNotExist")
        assert record is None

    def test_get_search_by_topic_case_sensitive(self) -> None:
        """Topic matching should be case-sensitive (no fuzzy matching)."""
        from searchstore import storesearches
        storesearches.save_search(
            topic="Exact Match", keywords=[], result="Found"
        )
        record = storesearches.get_search_by_topic("exact match")
        assert record is None  # Case mismatch

    def test_get_search_by_topic_partial_match(self) -> None:
        """A partial topic string should NOT match (exact match only)."""
        from searchstore import storesearches
        storesearches.save_search(
            topic="Full Topic Name", keywords=[], result="Data"
        )
        record = storesearches.get_search_by_topic("Full Topic")
        assert record is None  # Partial match

    # ------------------------------------------------------------------
    # Integration: save → history → by_topic
    # ------------------------------------------------------------------

    def test_save_and_retrieve_round_trip(self) -> None:
        """Save a search, verify it appears in history and can be looked up."""
        from searchstore import storesearches
        storesearches.save_search(
            topic="Round Trip",
            keywords=["test"],
            result="Round trip result",
        )
        # Check history
        history = storesearches.get_search_history()
        assert any(r["topic"] == "Round Trip" for r in history)

        # Check by-topic lookup
        record = storesearches.get_search_by_topic("Round Trip")
        assert record is not None
        assert record["result"] == "Round trip result"

    # ------------------------------------------------------------------
    # delete_search
    # ------------------------------------------------------------------

    def test_delete_search_removes_record(self) -> None:
        """``delete_search`` should remove the record and return ``True``."""
        from searchstore import storesearches
        doc_id = storesearches.save_search(
            topic="To Delete", keywords=["del"], result="Delete me"
        )
        # Confirm it exists
        history_before = storesearches.get_search_history()
        assert any(r["doc_id"] == doc_id for r in history_before)

        result = storesearches.delete_search(doc_id)
        assert result is True

        # Confirm it's gone
        history_after = storesearches.get_search_history()
        assert not any(r["doc_id"] == doc_id for r in history_after)

    def test_delete_search_nonexistent_id(self) -> None:
        """Deleting a non-existent ``doc_id`` should return ``False``."""
        from searchstore import storesearches
        # Use a doc_id that cannot exist (TinyDB IDs start at 1, save one record,
        # then use a very large number)
        storesearches.save_search(topic="Temp", keywords=[], result="")
        result = storesearches.delete_search(99999)
        assert result is False

    def test_delete_search_only_removes_target(self) -> None:
        """Deleting one record must not affect other records."""
        from searchstore import storesearches
        doc_id_1 = storesearches.save_search(
            topic="Keep", keywords=["keep"], result="Keep me"
        )
        doc_id_2 = storesearches.save_search(
            topic="Remove", keywords=["rem"], result="Remove me"
        )
        storesearches.delete_search(doc_id_2)

        history = storesearches.get_search_history()
        doc_ids_in_history = [r["doc_id"] for r in history]
        assert doc_id_1 in doc_ids_in_history
        assert doc_id_2 not in doc_ids_in_history
