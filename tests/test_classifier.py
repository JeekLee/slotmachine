"""PARA 분류 모듈 단위 테스트."""
from pathlib import Path

import pytest

from slotmachine.classifier.para import (
    PARA_FOLDERS,
    apply_classification,
    load_inbox,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """임시 vault 구조를 생성한다."""
    inbox = tmp_path / "INBOX"
    inbox.mkdir()
    return tmp_path


@pytest.fixture
def inbox_with_docs(vault: Path) -> Path:
    """INBOX에 샘플 .md 파일 3개를 생성한다."""
    inbox = vault / "INBOX"
    (inbox / "프로젝트A.md").write_text(
        "---\ntags: [project]\n---\n# 프로젝트A\n마감: 2026-04-01\n구체적인 태스크 목록",
        encoding="utf-8",
    )
    (inbox / "독서노트.md").write_text(
        "# 독서노트\n원칙 by Ray Dalio\n요약 및 핵심 내용",
        encoding="utf-8",
    )
    (inbox / "아이디어.md").write_text(
        "# 아이디어\n뭔가 해야 할 것 같은데...",
        encoding="utf-8",
    )
    return inbox


# ---------------------------------------------------------------------------
# load_inbox
# ---------------------------------------------------------------------------

class TestLoadInbox:
    def test_returns_docs_from_inbox(self, vault, inbox_with_docs):
        docs = load_inbox(vault / "INBOX", vault)
        assert len(docs) == 3

    def test_doc_fields_populated(self, vault, inbox_with_docs):
        docs = load_inbox(vault / "INBOX", vault)
        titles = {d.title for d in docs}
        assert "프로젝트A" in titles
        assert "독서노트" in titles

    def test_path_is_relative_to_vault(self, vault, inbox_with_docs):
        docs = load_inbox(vault / "INBOX", vault)
        for doc in docs:
            assert not Path(doc.path).is_absolute()
            assert doc.path.startswith("INBOX")

    def test_excerpt_truncated(self, vault: Path):
        inbox = vault / "INBOX"
        inbox.mkdir(exist_ok=True)
        long_content = "a" * 1000
        (inbox / "long.md").write_text(f"# Long\n{long_content}", encoding="utf-8")
        docs = load_inbox(inbox, vault)
        assert len(docs[0].excerpt) <= 300

    def test_empty_inbox_returns_empty_list(self, vault: Path):
        docs = load_inbox(vault / "INBOX", vault)
        assert docs == []

    def test_nonexistent_inbox_returns_empty_list(self, vault: Path):
        docs = load_inbox(vault / "NONEXISTENT", vault)
        assert docs == []

    def test_hidden_folders_excluded(self, vault: Path):
        inbox = vault / "INBOX"
        inbox.mkdir(exist_ok=True)
        hidden = inbox / ".obsidian"
        hidden.mkdir()
        (hidden / "secret.md").write_text("# secret", encoding="utf-8")
        (inbox / "visible.md").write_text("# visible", encoding="utf-8")
        docs = load_inbox(inbox, vault)
        assert len(docs) == 1
        assert docs[0].title == "visible"


# ---------------------------------------------------------------------------
# apply_classification
# ---------------------------------------------------------------------------

class TestApplyClassification:
    def test_moves_file_to_correct_folder(self, vault, inbox_with_docs):
        classifications = [
            {"path": "INBOX/프로젝트A.md", "category": "Projects"},
        ]
        result = apply_classification(vault, classifications)
        assert result.moved == 1
        assert result.skipped == 0
        assert (vault / "Projects" / "프로젝트A.md").exists()
        assert not (vault / "INBOX" / "프로젝트A.md").exists()

    def test_inbox_category_skipped(self, vault, inbox_with_docs):
        classifications = [
            {"path": "INBOX/아이디어.md", "category": "Inbox"},
        ]
        result = apply_classification(vault, classifications)
        assert result.moved == 0
        assert result.skipped == 1
        assert (vault / "INBOX" / "아이디어.md").exists()

    def test_multiple_classifications(self, vault, inbox_with_docs):
        classifications = [
            {"path": "INBOX/프로젝트A.md", "category": "Projects"},
            {"path": "INBOX/독서노트.md", "category": "Resources"},
            {"path": "INBOX/아이디어.md", "category": "Inbox"},
        ]
        result = apply_classification(vault, classifications)
        assert result.moved == 2
        assert result.skipped == 1
        assert (vault / "Projects" / "프로젝트A.md").exists()
        assert (vault / "Resources" / "독서노트.md").exists()
        assert (vault / "INBOX" / "아이디어.md").exists()

    def test_creates_target_folder_if_missing(self, vault, inbox_with_docs):
        assert not (vault / "Areas").exists()
        classifications = [
            {"path": "INBOX/독서노트.md", "category": "Areas"},
        ]
        apply_classification(vault, classifications)
        assert (vault / "Areas").exists()

    def test_nonexistent_file_recorded_as_error(self, vault):
        classifications = [
            {"path": "INBOX/없는파일.md", "category": "Projects"},
        ]
        result = apply_classification(vault, classifications)
        assert result.skipped == 1
        assert len(result.errors) == 1

    def test_filename_conflict_resolved(self, vault, inbox_with_docs):
        # Projects 폴더에 동일한 파일명 사전 생성
        (vault / "Projects").mkdir()
        (vault / "Projects" / "프로젝트A.md").write_text("기존 파일", encoding="utf-8")
        classifications = [
            {"path": "INBOX/프로젝트A.md", "category": "Projects"},
        ]
        result = apply_classification(vault, classifications)
        assert result.moved == 1
        # 기존 파일 보존 + 새 파일 _1 접미사
        assert (vault / "Projects" / "프로젝트A.md").exists()
        assert (vault / "Projects" / "프로젝트A_1.md").exists()

    def test_all_para_categories_supported(self, vault: Path):
        inbox = vault / "INBOX"
        inbox.mkdir(exist_ok=True)
        for category in PARA_FOLDERS:
            fname = f"test_{category}.md"
            (inbox / fname).write_text(f"# {category}", encoding="utf-8")
            result = apply_classification(
                vault, [{"path": f"INBOX/{fname}", "category": category}]
            )
            assert result.moved == 1
            assert (vault / PARA_FOLDERS[category] / fname).exists()
