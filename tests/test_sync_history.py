"""SyncHistory 단위 테스트."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from slotmachine.sync.incremental_sync import IncrementalSyncResult
from slotmachine.sync.sync_history import SyncHistory, SyncRecord


@pytest.fixture
def history(tmp_path) -> SyncHistory:
    return SyncHistory(tmp_path / "sync_history.db")


class TestSyncHistoryInit:
    def test_creates_db_file(self, tmp_path):
        db_path = tmp_path / "sub" / "history.db"
        SyncHistory(db_path)
        assert db_path.exists()

    def test_creates_parent_directories(self, tmp_path):
        db_path = tmp_path / "a" / "b" / "c" / "history.db"
        SyncHistory(db_path)
        assert db_path.exists()


class TestRecord:
    def test_record_and_retrieve(self, history):
        result = IncrementalSyncResult(added=2, modified=1, deleted=0, failed=0)
        history.record("save", result, commit_hash="abc123")

        records = history.recent()
        assert len(records) == 1
        assert records[0].operation == "save"
        assert records[0].added == 2
        assert records[0].modified == 1
        assert records[0].commit_hash == "abc123"

    def test_record_sync_without_commit_hash(self, history):
        history.record("sync", IncrementalSyncResult(deleted=1))
        records = history.recent()
        assert records[0].commit_hash is None
        assert records[0].deleted == 1

    def test_record_with_errors_stores_summary(self, history):
        result = IncrementalSyncResult(failed=1, errors=[(Path("bad.md"), "파싱 오류")])
        history.record("save", result)
        records = history.recent()
        assert records[0].error_summary is not None
        assert "bad.md" in records[0].error_summary

    def test_record_without_errors_stores_none(self, history):
        history.record("sync", IncrementalSyncResult(added=1))
        records = history.recent()
        assert records[0].error_summary is None

    def test_timestamp_is_datetime_instance(self, history):
        history.record("save", IncrementalSyncResult())
        records = history.recent()
        assert isinstance(records[0].timestamp, datetime)

    def test_multiple_records_stored(self, history):
        for i in range(5):
            history.record("sync", IncrementalSyncResult(added=i))
        assert len(history.recent(limit=10)) == 5


class TestRecent:
    def test_returns_newest_first(self, history):
        for i in range(5):
            history.record("sync", IncrementalSyncResult(added=i))
        records = history.recent()
        assert records[0].added == 4  # 가장 최근 것 먼저

    def test_respects_limit(self, history):
        for _ in range(10):
            history.record("sync", IncrementalSyncResult())
        assert len(history.recent(limit=3)) == 3

    def test_empty_db_returns_empty_list(self, history):
        assert history.recent() == []

    def test_record_is_sync_record_instance(self, history):
        history.record("save", IncrementalSyncResult())
        records = history.recent()
        assert isinstance(records[0], SyncRecord)


class TestClear:
    def test_clear_removes_all_records(self, history):
        for _ in range(3):
            history.record("sync", IncrementalSyncResult())
        deleted = history.clear()
        assert deleted == 3
        assert history.recent() == []

    def test_clear_empty_db_returns_zero(self, history):
        assert history.clear() == 0
