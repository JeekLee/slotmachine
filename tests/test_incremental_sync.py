"""증분 동기화 단위 테스트."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slotmachine.sync.embedding import BaseEmbeddingProvider
from slotmachine.sync.git_manager import DiffResult
from slotmachine.sync.incremental_sync import IncrementalSyncResult, incremental_sync


def _make_db():
    with patch("slotmachine.sync.graphdb.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        from slotmachine.sync.graphdb import GraphDB
        db = GraphDB("bolt://localhost:7687", "neo4j", "test")
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    mock_session.run.return_value.single.return_value = None
    return db, mock_session


# ---------------------------------------------------------------------------
# IncrementalSyncResult
# ---------------------------------------------------------------------------

class TestIncrementalSyncResult:
    def test_total_changed_sums_all(self):
        r = IncrementalSyncResult(added=2, modified=3, deleted=1)
        assert r.total_changed == 6

    def test_total_changed_excludes_failed(self):
        r = IncrementalSyncResult(added=1, failed=5)
        assert r.total_changed == 1

    def test_success_equals_total_changed(self):
        r = IncrementalSyncResult(added=1, modified=1, deleted=1)
        assert r.success == 3


# ---------------------------------------------------------------------------
# incremental_sync
# ---------------------------------------------------------------------------

class TestIncrementalSync:
    def test_empty_diff_returns_zero_result(self, tmp_path):
        db, _ = _make_db()
        result = incremental_sync(DiffResult(), tmp_path, db)
        assert result.total_changed == 0
        assert result.failed == 0

    def test_added_file_increments_added(self, tmp_path):
        p = tmp_path / "note.md"
        p.write_text("# Hello\n본문", encoding="utf-8")
        db, _ = _make_db()

        result = incremental_sync(DiffResult(added=[p]), tmp_path, db)
        assert result.added == 1
        assert result.failed == 0

    def test_modified_file_increments_modified(self, tmp_path):
        p = tmp_path / "note.md"
        p.write_text("# Modified\n수정됨", encoding="utf-8")
        db, _ = _make_db()

        result = incremental_sync(DiffResult(modified=[p]), tmp_path, db)
        assert result.modified == 1
        assert result.failed == 0

    def test_deleted_file_increments_deleted(self, tmp_path):
        p = tmp_path / "deleted.md"
        db, _ = _make_db()

        result = incremental_sync(DiffResult(deleted=[p]), tmp_path, db)
        assert result.deleted == 1
        assert result.failed == 0

    def test_error_in_parse_counts_as_failed(self, tmp_path):
        p = tmp_path / "bad.md"
        db, _ = _make_db()

        with patch("slotmachine.sync.incremental_sync.parse_document", side_effect=ValueError("파싱 오류")):
            result = incremental_sync(DiffResult(added=[p]), tmp_path, db)

        assert result.failed == 1
        assert result.added == 0
        assert len(result.errors) == 1

    def test_error_in_delete_counts_as_failed(self, tmp_path):
        p = tmp_path / "gone.md"
        db, _ = _make_db()

        with patch.object(db, "delete_document", side_effect=RuntimeError("DB 오류")):
            result = incremental_sync(DiffResult(deleted=[p]), tmp_path, db)

        assert result.failed == 1
        assert result.deleted == 0

    def test_error_includes_path_and_message(self, tmp_path):
        p = tmp_path / "bad.md"
        db, _ = _make_db()

        with patch("slotmachine.sync.incremental_sync.parse_document", side_effect=ValueError("오류메시지")):
            result = incremental_sync(DiffResult(added=[p]), tmp_path, db)

        assert result.errors[0][0] == p
        assert "오류메시지" in result.errors[0][1]

    def test_embedding_called_when_provider_given(self, tmp_path):
        p = tmp_path / "note.md"
        p.write_text("# Note\n본문", encoding="utf-8")
        db, _ = _make_db()
        embedder = MagicMock(spec=BaseEmbeddingProvider)
        embedder.embed_one.return_value = [0.1, 0.2, 0.3]

        incremental_sync(DiffResult(added=[p]), tmp_path, db, embedding_provider=embedder)
        embedder.embed_one.assert_called_once()

    def test_no_embedding_when_provider_none(self, tmp_path):
        p = tmp_path / "note.md"
        p.write_text("# Note\n본문", encoding="utf-8")
        db, _ = _make_db()

        with patch.object(db, "upsert_document") as mock_upsert:
            with patch("slotmachine.sync.incremental_sync.parse_document") as mock_parse:
                mock_doc = MagicMock()
                mock_doc.raw_content = "본문"
                mock_doc.path = p
                mock_parse.return_value = mock_doc
                incremental_sync(DiffResult(added=[p]), tmp_path, db, embedding_provider=None)

            _, kwargs = mock_upsert.call_args
            assert kwargs.get("embedding") is None

    def test_multiple_files_all_processed(self, tmp_path):
        for i in range(3):
            (tmp_path / f"note{i}.md").write_text(f"# Note {i}\n본문", encoding="utf-8")
        db, _ = _make_db()
        diff = DiffResult(added=[tmp_path / f"note{i}.md" for i in range(3)])

        result = incremental_sync(diff, tmp_path, db)
        assert result.added == 3

    def test_error_in_one_file_does_not_stop_others(self, tmp_path):
        good = tmp_path / "good.md"
        good.write_text("# Good\n본문", encoding="utf-8")
        bad = tmp_path / "bad.md"
        db, _ = _make_db()

        original_parse = __import__(
            "slotmachine.sync.parser", fromlist=["parse_document"]
        ).parse_document

        def selective_parse(path):
            if path == bad:
                raise ValueError("파싱 실패")
            return original_parse(path)

        with patch("slotmachine.sync.incremental_sync.parse_document", side_effect=selective_parse):
            result = incremental_sync(DiffResult(added=[bad, good]), tmp_path, db)

        assert result.added == 1
        assert result.failed == 1
