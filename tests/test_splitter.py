"""apply_split() 단위 테스트."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slotmachine.classifier.splitter import SplitResult, apply_split

_PARA_MAP = {
    "Projects": "Projects",
    "Areas": "Areas",
    "Resources": "Resources",
    "Archives": "Archives",
}


def _make_db() -> MagicMock:
    db = MagicMock()
    db.upsert_document.return_value = None
    db.delete_document.return_value = None
    return db


def _write(path: Path, content: str = "# Note\n본문") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# SplitResult
# ---------------------------------------------------------------------------

class TestSplitResult:
    def test_success_when_created_and_no_failed(self):
        r = SplitResult(created=["a.md"], deleted="orig.md", failed=0)
        assert r.success is True

    def test_not_success_when_nothing_created(self):
        r = SplitResult(created=[], deleted="orig.md", failed=0)
        assert r.success is False

    def test_not_success_when_failed(self):
        r = SplitResult(created=["a.md"], deleted="orig.md", failed=1)
        assert r.success is False


# ---------------------------------------------------------------------------
# apply_split — 정상 경로
# ---------------------------------------------------------------------------

class TestApplySplit:
    def test_creates_split_files(self, tmp_path):
        original = _write(tmp_path / "Resources" / "big.md", "# Big\n" + "x" * 100)
        db = _make_db()

        result = apply_split(
            tmp_path,
            "Resources/big.md",
            [
                {"filename": "part1.md", "content": "# Part 1\n내용"},
                {"filename": "part2.md", "content": "# Part 2\n내용"},
            ],
            db,
            para_folder_map=_PARA_MAP,
        )

        assert len(result.created) == 2
        assert (tmp_path / "Resources" / "part1.md").exists()
        assert (tmp_path / "Resources" / "part2.md").exists()

    def test_deletes_original(self, tmp_path):
        original = _write(tmp_path / "Resources" / "big.md")
        db = _make_db()

        result = apply_split(
            tmp_path,
            "Resources/big.md",
            [{"filename": "part1.md", "content": "# Part 1\n내용"}],
            db,
            para_folder_map=_PARA_MAP,
        )

        assert not original.exists()
        assert result.deleted == "Resources/big.md"

    def test_upserts_split_docs_to_graphdb(self, tmp_path):
        _write(tmp_path / "Resources" / "big.md")
        db = _make_db()

        apply_split(
            tmp_path,
            "Resources/big.md",
            [
                {"filename": "part1.md", "content": "# Part 1\n내용"},
                {"filename": "part2.md", "content": "# Part 2\n내용"},
            ],
            db,
            para_folder_map=_PARA_MAP,
        )

        assert db.upsert_document.call_count == 2

    def test_deletes_original_from_graphdb(self, tmp_path):
        _write(tmp_path / "Resources" / "big.md")
        db = _make_db()

        apply_split(
            tmp_path,
            "Resources/big.md",
            [{"filename": "part1.md", "content": "# Part 1\n내용"}],
            db,
            para_folder_map=_PARA_MAP,
        )

        db.delete_document.assert_called_once()

    def test_inbox_skips_graphdb_update(self, tmp_path):
        """INBOX 문서 분할 시 GraphDB 업데이트를 생략한다."""
        _write(tmp_path / "INBOX" / "big.md")
        db = _make_db()

        result = apply_split(
            tmp_path,
            "INBOX/big.md",
            [{"filename": "part1.md", "content": "# Part 1\n내용"}],
            db,
            inbox_folder="INBOX",
            para_folder_map=_PARA_MAP,
        )

        db.upsert_document.assert_not_called()
        db.delete_document.assert_not_called()
        assert not (tmp_path / "INBOX" / "big.md").exists()
        assert (tmp_path / "INBOX" / "part1.md").exists()

    def test_filename_collision_adds_suffix(self, tmp_path):
        """분할 파일명이 이미 존재하면 번호를 붙인다."""
        _write(tmp_path / "Resources" / "big.md")
        _write(tmp_path / "Resources" / "part1.md", "# 기존 파일")
        db = _make_db()

        result = apply_split(
            tmp_path,
            "Resources/big.md",
            [{"filename": "part1.md", "content": "# Part 1\n새 내용"}],
            db,
            para_folder_map=_PARA_MAP,
        )

        assert len(result.created) == 1
        assert "part1_1.md" in result.created[0]

    def test_md_extension_added_if_missing(self, tmp_path):
        """filename에 .md 확장자가 없으면 자동으로 붙인다."""
        _write(tmp_path / "Resources" / "big.md")
        db = _make_db()

        result = apply_split(
            tmp_path,
            "Resources/big.md",
            [{"filename": "part1", "content": "# Part 1\n내용"}],
            db,
            para_folder_map=_PARA_MAP,
        )

        assert any(p.endswith("part1.md") for p in result.created)

    def test_empty_filename_counts_as_failed(self, tmp_path):
        _write(tmp_path / "Resources" / "big.md")
        db = _make_db()

        result = apply_split(
            tmp_path,
            "Resources/big.md",
            [{"filename": "", "content": "내용"}],
            db,
            para_folder_map=_PARA_MAP,
        )

        assert result.failed == 1
        assert len(result.created) == 0

    def test_returns_relative_paths_in_created(self, tmp_path):
        _write(tmp_path / "Resources" / "big.md")
        db = _make_db()

        result = apply_split(
            tmp_path,
            "Resources/big.md",
            [{"filename": "part1.md", "content": "# Part 1\n내용"}],
            db,
            para_folder_map=_PARA_MAP,
        )

        assert all(not Path(p).is_absolute() for p in result.created)
