"""GitManager 단위 테스트."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from slotmachine.sync.git_manager import DiffResult, GitManager


# ---------------------------------------------------------------------------
# DiffResult
# ---------------------------------------------------------------------------

class TestDiffResult:
    def test_changed_combines_added_and_modified(self):
        d = DiffResult(added=[Path("a.md")], modified=[Path("b.md")], deleted=[Path("c.md")])
        assert d.changed == [Path("a.md"), Path("b.md")]

    def test_changed_excludes_deleted(self):
        d = DiffResult(deleted=[Path("d.md")])
        assert d.changed == []

    def test_is_empty_true_when_no_files(self):
        assert DiffResult().is_empty is True

    def test_is_empty_false_when_added(self):
        assert DiffResult(added=[Path("a.md")]).is_empty is False

    def test_is_empty_false_when_modified(self):
        assert DiffResult(modified=[Path("m.md")]).is_empty is False

    def test_is_empty_false_when_deleted(self):
        assert DiffResult(deleted=[Path("d.md")]).is_empty is False


# ---------------------------------------------------------------------------
# generate_commit_message (static)
# ---------------------------------------------------------------------------

class TestGenerateCommitMessage:
    def test_empty_staged_returns_default(self):
        msg = GitManager.generate_commit_message([])
        assert "[SlotMachine]" in msg

    def test_single_file_includes_stem(self):
        msg = GitManager.generate_commit_message(["notes/hello.md"])
        assert "hello" in msg
        assert "[SlotMachine]" in msg

    def test_two_files_includes_both_stems(self):
        msg = GitManager.generate_commit_message(["a.md", "b.md"])
        assert "a" in msg and "b" in msg

    def test_three_files_inline(self):
        msg = GitManager.generate_commit_message(["a.md", "b.md", "c.md"])
        assert "a" in msg and "b" in msg and "c" in msg

    def test_many_files_shows_total_count(self):
        files = [f"note{i}.md" for i in range(10)]
        msg = GitManager.generate_commit_message(files)
        assert "10" in msg
        assert "[SlotMachine]" in msg

    def test_many_files_shows_md_count(self):
        files = ["a.md", "b.md", "c.txt", "d.md", "e.png", "f.md"]
        msg = GitManager.generate_commit_message(files)
        assert "6" in msg   # total
        assert "4" in msg   # md count


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_git_manager(repo_path: Path) -> tuple[GitManager, MagicMock]:
    """GitManager + mock Repo 쌍을 생성한다."""
    with patch("slotmachine.sync.git_manager.git.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.working_tree_dir = str(repo_path)
        mock_repo_cls.return_value = mock_repo
        mgr = GitManager(repo_path)
    return mgr, mock_repo


# ---------------------------------------------------------------------------
# current_head
# ---------------------------------------------------------------------------

class TestCurrentHead:
    def test_returns_hexsha(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_repo.head.commit.hexsha = "abc123" * 7
        assert mgr.current_head() == mock_repo.head.commit.hexsha

    def test_returns_none_on_value_error(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        type(mock_repo.head).commit = PropertyMock(side_effect=ValueError)
        assert mgr.current_head() is None


# ---------------------------------------------------------------------------
# add_all
# ---------------------------------------------------------------------------

class TestAddAll:
    def test_returns_staged_paths(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_repo.git.status.return_value = "A  notes/hello.md\nM  ideas.md"
        mock_repo.git.add = MagicMock()

        result = mgr.add_all()
        assert "notes/hello.md" in result
        assert "ideas.md" in result

    def test_empty_status_returns_empty_list(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_repo.git.status.return_value = ""
        mock_repo.git.add = MagicMock()

        assert mgr.add_all() == []

    def test_untracked_files_ignored_in_staged_list(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_repo.git.status.return_value = "?? untracked.md"
        mock_repo.git.add = MagicMock()

        assert mgr.add_all() == []

    def test_rename_format_takes_new_path(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_repo.git.status.return_value = "R  old.md -> new.md"
        mock_repo.git.add = MagicMock()

        result = mgr.add_all()
        assert "new.md" in result
        assert "old.md" not in result

    def test_deleted_file_included(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_repo.git.status.return_value = "D  removed.md"
        mock_repo.git.add = MagicMock()

        result = mgr.add_all()
        assert "removed.md" in result


# ---------------------------------------------------------------------------
# commit
# ---------------------------------------------------------------------------

class TestCommit:
    def test_returns_hexsha(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_commit = MagicMock()
        mock_commit.hexsha = "deadbeef" * 5
        mock_repo.index.commit.return_value = mock_commit

        result = mgr.commit("test message")
        assert result == mock_commit.hexsha
        mock_repo.index.commit.assert_called_once_with("test message")


# ---------------------------------------------------------------------------
# push / pull (tenacity 재시도 없이 정상 경로만 테스트)
# ---------------------------------------------------------------------------

class TestPushPull:
    def test_push_calls_remote_push(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_remote = MagicMock()
        mock_repo.remote.return_value = mock_remote

        mgr.push()
        mock_remote.push.assert_called_once_with("main")

    def test_push_uses_specified_remote_and_branch(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_remote = MagicMock()
        mock_repo.remote.return_value = mock_remote

        mgr.push(remote="upstream", branch="dev")
        mock_repo.remote.assert_called_once_with("upstream")
        mock_remote.push.assert_called_once_with("dev")

    def test_pull_returns_new_head(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_remote = MagicMock()
        mock_repo.remote.return_value = mock_remote
        mock_repo.head.commit.hexsha = "newheadsha1234"

        result = mgr.pull()
        assert result == "newheadsha1234"

    def test_pull_calls_remote_pull(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_remote = MagicMock()
        mock_repo.remote.return_value = mock_remote
        mock_repo.head.commit.hexsha = "sha"

        mgr.pull(remote="origin", branch="main")
        mock_repo.remote.assert_called_once_with("origin")
        mock_remote.pull.assert_called_once_with("main")


# ---------------------------------------------------------------------------
# diff_files
# ---------------------------------------------------------------------------

def _diff_item(change_type: str, a_path: str, b_path: str | None = None) -> MagicMock:
    item = MagicMock()
    item.change_type = change_type
    item.a_path = a_path
    item.b_path = b_path or a_path
    return item


class TestDiffFiles:
    def test_added_md_file(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_from, mock_to = MagicMock(), MagicMock()
        mock_repo.commit.side_effect = [mock_from, mock_to]
        mock_from.diff.return_value = [_diff_item("A", "new.md")]

        result = mgr.diff_files("from_sha", "to_sha")
        assert len(result.added) == 1
        assert result.added[0].name == "new.md"

    def test_modified_md_file(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_from, mock_to = MagicMock(), MagicMock()
        mock_repo.commit.side_effect = [mock_from, mock_to]
        mock_from.diff.return_value = [_diff_item("M", "note.md")]

        result = mgr.diff_files("from_sha", "to_sha")
        assert len(result.modified) == 1
        assert result.modified[0].name == "note.md"

    def test_deleted_md_file(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_from, mock_to = MagicMock(), MagicMock()
        mock_repo.commit.side_effect = [mock_from, mock_to]
        mock_from.diff.return_value = [_diff_item("D", "old.md")]

        result = mgr.diff_files("from_sha", "to_sha")
        assert len(result.deleted) == 1

    def test_renamed_md_file_treated_as_delete_and_add(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_from, mock_to = MagicMock(), MagicMock()
        mock_repo.commit.side_effect = [mock_from, mock_to]
        mock_from.diff.return_value = [_diff_item("R", "old.md", "renamed.md")]

        result = mgr.diff_files("from_sha", "to_sha")
        assert len(result.deleted) == 1
        assert len(result.added) == 1

    def test_non_md_files_ignored(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_from, mock_to = MagicMock(), MagicMock()
        mock_repo.commit.side_effect = [mock_from, mock_to]
        mock_from.diff.return_value = [
            _diff_item("A", "image.png"),
            _diff_item("M", "script.py"),
        ]

        result = mgr.diff_files("from_sha", "to_sha")
        assert result.is_empty

    def test_from_commit_none_returns_all_md_as_added(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_to = MagicMock()
        mock_repo.commit.return_value = mock_to

        blob_md = MagicMock()
        blob_md.path = "note.md"
        blob_img = MagicMock()
        blob_img.path = "image.png"
        mock_to.tree.traverse.return_value = [blob_md, blob_img]

        result = mgr.diff_files(None, "to_sha")
        assert len(result.added) == 1
        assert result.added[0].name == "note.md"
        assert result.modified == []
        assert result.deleted == []

    def test_multiple_changes_counted_separately(self, tmp_path):
        mgr, mock_repo = _make_git_manager(tmp_path)
        mock_from, mock_to = MagicMock(), MagicMock()
        mock_repo.commit.side_effect = [mock_from, mock_to]
        mock_from.diff.return_value = [
            _diff_item("A", "new.md"),
            _diff_item("M", "modified.md"),
            _diff_item("D", "deleted.md"),
        ]

        result = mgr.diff_files("from_sha", "to_sha")
        assert len(result.added) == 1
        assert len(result.modified) == 1
        assert len(result.deleted) == 1
