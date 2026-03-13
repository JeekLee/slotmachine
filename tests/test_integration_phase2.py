"""Phase 2 통합 테스트 — save/sync 파이프라인 end-to-end.

GitManager는 mock으로 대체하고, GraphDB 드라이버도 mock을 사용한다.
실제 파일 시스템(tmp_path)을 사용해 parse_document까지 실제 동작을 검증한다.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slotmachine.sync.git_manager import DiffResult
from slotmachine.sync.graphdb import GraphDB
from slotmachine.sync.pipelines import LiveSyncResult, SaveResult, live_sync, save


# ---------------------------------------------------------------------------
# 공용 헬퍼
# ---------------------------------------------------------------------------

def _write_md(base: Path, rel: str, content: str) -> Path:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _make_db() -> tuple[GraphDB, MagicMock]:
    with patch("slotmachine.sync.graphdb.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        db = GraphDB("bolt://localhost:7687", "neo4j", "test")
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    mock_session.run.return_value.single.return_value = None
    return db, mock_session


def _make_git_mock(
    *,
    old_head: str | None = "old_head_sha",
    new_head: str = "new_head_sha",
    staged: list[str] | None = None,
    diff: DiffResult | None = None,
) -> MagicMock:
    """GitManager 인스턴스 mock을 생성한다."""
    mgr = MagicMock()
    mgr.current_head.return_value = old_head
    mgr.add_all.return_value = staged if staged is not None else ["note.md"]
    mgr.commit.return_value = new_head
    mgr.push.return_value = None
    mgr.pull.return_value = new_head
    mgr.diff_files.return_value = diff if diff is not None else DiffResult()
    mgr.generate_commit_message.return_value = "chore: auto msg [SlotMachine]"
    return mgr


# ---------------------------------------------------------------------------
# save 파이프라인
# ---------------------------------------------------------------------------

class TestSavePipeline:
    def test_nothing_to_commit_when_no_staged_files(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(staged=[])

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = save(tmp_path, db)

        assert result.nothing_to_commit is True
        assert result.commit_hash is None
        mock_mgr.commit.assert_not_called()
        mock_mgr.push.assert_not_called()

    def test_successful_save_returns_commit_hash(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(staged=["note.md"])

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = save(tmp_path, db)

        assert result.success is True
        assert result.commit_hash == "new_head_sha"

    def test_save_with_added_file_syncs_graphdb(self, tmp_path):
        p = _write_md(tmp_path, "note.md", "# Note\n본문")
        db, _ = _make_db()
        mock_mgr = _make_git_mock(staged=["note.md"], diff=DiffResult(added=[p]))

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = save(tmp_path, db)

        assert result.sync_result.added == 1
        assert result.sync_result.failed == 0

    def test_save_with_deleted_file_removes_from_graphdb(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(
            staged=["deleted.md"],
            diff=DiffResult(deleted=[tmp_path / "deleted.md"]),
        )

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = save(tmp_path, db)

        assert result.sync_result.deleted == 1

    def test_custom_commit_message_used(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(staged=["note.md"])

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            save(tmp_path, db, commit_message="custom message")

        mock_mgr.commit.assert_called_once_with("custom message")

    def test_auto_commit_message_generated_when_none(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(staged=["note.md"])

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            save(tmp_path, db, commit_message=None)

        # generate_commit_message를 호출해서 나온 값으로 commit이 호출됐는지 검증
        mock_mgr.commit.assert_called_once_with("chore: auto msg [SlotMachine]")

    def test_git_error_captured_in_result(self, tmp_path):
        import git
        db, _ = _make_db()
        mock_mgr = _make_git_mock(staged=["note.md"])
        mock_mgr.push.side_effect = git.GitCommandError("push", "connection refused")

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = save(tmp_path, db)

        assert result.success is False
        assert result.error is not None
        assert "Git" in result.error

    def test_non_git_error_captured_in_result(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(staged=["note.md"])
        mock_mgr.commit.side_effect = RuntimeError("예상치 못한 오류")

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = save(tmp_path, db)

        assert result.success is False
        assert "예상치 못한 오류" in result.error

    def test_save_records_to_history(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(staged=["note.md"])
        mock_history = MagicMock()

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            save(tmp_path, db, sync_history=mock_history)

        mock_history.record.assert_called_once()
        operation, sync_result = mock_history.record.call_args[0]
        assert operation == "save"

    def test_save_passes_commit_hash_to_history(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(staged=["note.md"], new_head="abc123")
        mock_history = MagicMock()

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            save(tmp_path, db, sync_history=mock_history)

        _, kwargs = mock_history.record.call_args
        assert kwargs.get("commit_hash") == "abc123"

    def test_nothing_to_commit_skips_history(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(staged=[])
        mock_history = MagicMock()

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            save(tmp_path, db, sync_history=mock_history)

        mock_history.record.assert_not_called()

    def test_initial_commit_old_head_none(self, tmp_path):
        p = _write_md(tmp_path, "first.md", "# First\n첫 문서")
        db, _ = _make_db()
        mock_mgr = _make_git_mock(
            old_head=None, staged=["first.md"], diff=DiffResult(added=[p])
        )

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = save(tmp_path, db)

        assert result.success is True
        assert result.sync_result.added == 1


# ---------------------------------------------------------------------------
# live_sync 파이프라인
# ---------------------------------------------------------------------------

class TestLiveSyncPipeline:
    def test_nothing_to_sync_when_head_unchanged(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(old_head="same_sha", new_head="same_sha")

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = live_sync(tmp_path, db)

        assert result.nothing_to_sync is True
        mock_mgr.diff_files.assert_not_called()

    def test_sync_processes_modified_files(self, tmp_path):
        p = _write_md(tmp_path, "updated.md", "# Updated\n변경됨")
        db, _ = _make_db()
        mock_mgr = _make_git_mock(
            old_head="old", new_head="new", diff=DiffResult(modified=[p])
        )

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = live_sync(tmp_path, db)

        assert result.success is True
        assert result.sync_result.modified == 1

    def test_sync_processes_deleted_files(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(
            old_head="old", new_head="new",
            diff=DiffResult(deleted=[tmp_path / "removed.md"]),
        )

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = live_sync(tmp_path, db)

        assert result.sync_result.deleted == 1

    def test_previous_and_new_head_recorded_in_result(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(old_head="aaa111", new_head="bbb222")

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = live_sync(tmp_path, db)

        assert result.previous_head == "aaa111"
        assert result.new_head == "bbb222"

    def test_git_error_captured_in_result(self, tmp_path):
        import git
        db, _ = _make_db()
        mock_mgr = MagicMock()
        mock_mgr.current_head.return_value = "sha"
        mock_mgr.pull.side_effect = git.GitCommandError("pull", "connection refused")

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = live_sync(tmp_path, db)

        assert result.success is False
        assert result.error is not None

    def test_sync_records_to_history(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(old_head="old", new_head="new")
        mock_history = MagicMock()

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            live_sync(tmp_path, db, sync_history=mock_history)

        mock_history.record.assert_called_once()
        assert mock_history.record.call_args[0][0] == "sync"

    def test_nothing_to_sync_skips_history(self, tmp_path):
        db, _ = _make_db()
        mock_mgr = _make_git_mock(old_head="sha", new_head="sha")
        mock_history = MagicMock()

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            live_sync(tmp_path, db, sync_history=mock_history)

        mock_history.record.assert_not_called()

    def test_sync_with_initial_pull_from_none_head(self, tmp_path):
        """로컬에 커밋이 없는 상태에서 첫 pull."""
        p = _write_md(tmp_path, "first.md", "# First\n첫 문서")
        db, _ = _make_db()
        mock_mgr = _make_git_mock(
            old_head=None, new_head="first_commit",
            diff=DiffResult(added=[p]),
        )

        with patch("slotmachine.sync.pipelines.GitManager", return_value=mock_mgr):
            result = live_sync(tmp_path, db)

        assert result.success is True
        assert result.sync_result.added == 1
