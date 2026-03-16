"""full_sync() 단위 테스트."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slotmachine.sync.full_sync import SyncResult, _collect_md_files, full_sync


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """임시 vault 디렉토리를 반환한다."""
    return tmp_path


def _write_md(vault: Path, rel: str, content: str = "# Note\n") -> Path:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _make_db() -> MagicMock:
    db = MagicMock()
    db.upsert_document.return_value = "abc123"
    return db


# ---------------------------------------------------------------------------
# _collect_md_files
# ---------------------------------------------------------------------------

def test_collect_finds_md_files(vault):
    _write_md(vault, "a.md")
    _write_md(vault, "sub/b.md")
    files = _collect_md_files(vault)
    assert len(files) == 2


def test_collect_ignores_non_md(vault):
    _write_md(vault, "note.md")
    (vault / "readme.txt").write_text("hi")
    files = _collect_md_files(vault)
    assert all(f.suffix == ".md" for f in files)


def test_collect_returns_sorted(vault):
    _write_md(vault, "z.md")
    _write_md(vault, "a.md")
    files = _collect_md_files(vault)
    assert files == sorted(files)


def test_collect_empty_vault(vault):
    assert _collect_md_files(vault) == []


def test_collect_excludes_hidden_dir(vault):
    """숨김 디렉토리(.obsidian, .git 등) 하위 파일은 수집에서 제외된다."""
    _write_md(vault, "visible.md")
    _write_md(vault, ".obsidian/config.md")
    _write_md(vault, ".git/COMMIT_EDITMSG.md")
    files = _collect_md_files(vault)
    assert len(files) == 1
    assert all(".obsidian" not in str(f) and ".git" not in str(f) for f in files)


def test_collect_excludes_nested_hidden_dir(vault):
    """중첩된 숨김 디렉토리 내 파일도 제외된다."""
    _write_md(vault, "Projects/task.md")
    _write_md(vault, "Projects/.trash/deleted.md")
    files = _collect_md_files(vault)
    names = [f.name for f in files]
    assert "task.md" in names
    assert "deleted.md" not in names


# ---------------------------------------------------------------------------
# SyncResult
# ---------------------------------------------------------------------------

def test_sync_result_skipped():
    r = SyncResult(total=10, success=7, failed=2)
    assert r.skipped == 1


def test_sync_result_all_success():
    r = SyncResult(total=5, success=5, failed=0)
    assert r.skipped == 0


# ---------------------------------------------------------------------------
# full_sync — 정상 경로
# ---------------------------------------------------------------------------

def test_full_sync_returns_sync_result(vault):
    _write_md(vault, "note.md")
    db = _make_db()
    result = full_sync(vault, db, show_progress=False)
    assert isinstance(result, SyncResult)


def test_full_sync_counts_total(vault):
    _write_md(vault, "Resources/a.md")
    _write_md(vault, "Resources/b.md")
    _write_md(vault, "Resources/c.md")
    result = full_sync(
        vault, _make_db(),
        para_folder_map={"Projects": "Projects", "Areas": "Areas",
                         "Resources": "Resources", "Archives": "Archives"},
        show_progress=False,
    )
    assert result.total == 3


def test_full_sync_all_success(vault):
    _write_md(vault, "Resources/a.md")
    _write_md(vault, "Resources/b.md")
    result = full_sync(
        vault, _make_db(),
        para_folder_map={"Projects": "Projects", "Areas": "Areas",
                         "Resources": "Resources", "Archives": "Archives"},
        show_progress=False,
    )
    assert result.success == 2
    assert result.failed == 0


def test_full_sync_calls_upsert_per_file(vault):
    _write_md(vault, "Resources/a.md")
    _write_md(vault, "Resources/b.md")
    db = _make_db()
    full_sync(
        vault, db,
        para_folder_map={"Projects": "Projects", "Areas": "Areas",
                         "Resources": "Resources", "Archives": "Archives"},
        show_progress=False,
    )
    assert db.upsert_document.call_count == 2


def test_full_sync_infers_para_category_from_path(vault):
    """파일 경로에서 PARA 카테고리를 자동으로 추론한다."""
    _write_md(vault, "Resources/note.md")
    db = _make_db()
    full_sync(
        vault, db,
        para_folder_map={"Projects": "Projects", "Areas": "Areas",
                         "Resources": "Resources", "Archives": "Archives"},
        show_progress=False,
    )
    _, kwargs = db.upsert_document.call_args
    assert kwargs["para_category"] == "Resources"


def test_full_sync_empty_vault(vault):
    result = full_sync(vault, _make_db(), show_progress=False)
    assert result.total == 0
    assert result.success == 0


_PARA_MAP = {"Projects": "Projects", "Areas": "Areas",
             "Resources": "Resources", "Archives": "Archives"}


# ---------------------------------------------------------------------------
# full_sync — 오류 처리
# ---------------------------------------------------------------------------

def test_full_sync_counts_failed_on_parse_error(vault):
    _write_md(vault, "Resources/bad.md")
    db = _make_db()
    with patch("slotmachine.sync.full_sync.parse_document", side_effect=ValueError("파싱 실패")):
        result = full_sync(vault, db, para_folder_map=_PARA_MAP, show_progress=False)
    assert result.failed == 1
    assert result.success == 0


def test_full_sync_counts_failed_on_db_error(vault):
    _write_md(vault, "Resources/note.md")
    db = _make_db()
    db.upsert_document.side_effect = RuntimeError("DB 오류")
    result = full_sync(vault, db, para_folder_map=_PARA_MAP, show_progress=False)
    assert result.failed == 1


def test_full_sync_records_error_path(vault):
    p = _write_md(vault, "Resources/bad.md")
    db = _make_db()
    with patch("slotmachine.sync.full_sync.parse_document", side_effect=ValueError("에러")):
        result = full_sync(vault, db, para_folder_map=_PARA_MAP, show_progress=False)
    assert result.errors[0][0] == p
    assert "에러" in result.errors[0][1]


# ---------------------------------------------------------------------------
# full_sync — Inbox 제외
# ---------------------------------------------------------------------------

def test_full_sync_skips_inbox_files(vault):
    """INBOX 폴더 파일은 upsert 호출 없이 스킵된다."""
    _write_md(vault, "INBOX/raw.md")
    _write_md(vault, "Projects/task.md")
    db = _make_db()
    result = full_sync(
        vault, db,
        inbox_folder="INBOX",
        para_folder_map={"Projects": "Projects", "Areas": "Areas",
                         "Resources": "Resources", "Archives": "Archives"},
        show_progress=False,
    )
    assert db.upsert_document.call_count == 1
    assert result.success == 1


def test_full_sync_inbox_only_vault(vault):
    """모든 파일이 INBOX에만 있으면 upsert가 한 번도 호출되지 않는다."""
    _write_md(vault, "INBOX/a.md")
    _write_md(vault, "INBOX/b.md")
    db = _make_db()
    result = full_sync(vault, db, inbox_folder="INBOX", show_progress=False)
    db.upsert_document.assert_not_called()
    assert result.success == 0
    assert result.failed == 0


def test_full_sync_continues_after_error(vault):
    _write_md(vault, "Resources/bad.md")
    _write_md(vault, "Resources/good.md")
    db = _make_db()

    call_count = 0

    def fake_parse(path: Path):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("첫 번째 파일 실패")
        from slotmachine.sync.parser import ParsedDocument
        return ParsedDocument(path=path, title="Good", frontmatter={})

    with patch("slotmachine.sync.full_sync.parse_document", side_effect=fake_parse):
        result = full_sync(vault, db, para_folder_map=_PARA_MAP, show_progress=False)

    assert result.failed == 1
    assert result.success == 1
