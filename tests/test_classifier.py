"""PARA 분류 모듈 단위 테스트."""
from pathlib import Path

import pytest

from slotmachine.classifier.para import (
    DEFAULT_PARA_FOLDERS,
    apply_classification,
    get_vault_structure,
    load_document_contents,
    load_inbox,
    load_template,
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
        for category in DEFAULT_PARA_FOLDERS:
            fname = f"test_{category}.md"
            (inbox / fname).write_text(f"# {category}", encoding="utf-8")
            result = apply_classification(
                vault, [{"path": f"INBOX/{fname}", "category": category}]
            )
            assert result.moved == 1
            assert (vault / DEFAULT_PARA_FOLDERS[category] / fname).exists()

    def test_custom_folder_names(self, vault, inbox_with_docs):
        custom_map = {
            "Projects": "프로젝트",
            "Areas": "영역",
            "Resources": "자료",
            "Archives": "보관",
        }
        classifications = [
            {"path": "INBOX/프로젝트A.md", "category": "Projects"},
        ]
        result = apply_classification(vault, classifications, para_folder_map=custom_map)
        assert result.moved == 1
        assert (vault / "프로젝트" / "프로젝트A.md").exists()

    def test_content_written_before_move(self, vault, inbox_with_docs):
        """content 필드가 있으면 이동 전 파일에 덮어쓴다."""
        rewritten = "---\nstatus: active\n---\n# 프로젝트A (재작성됨)\n\n재작성된 내용"
        classifications = [
            {"path": "INBOX/프로젝트A.md", "category": "Projects", "content": rewritten},
        ]
        result = apply_classification(vault, classifications)
        assert result.moved == 1
        actual = (vault / "Projects" / "프로젝트A.md").read_text(encoding="utf-8")
        assert actual == rewritten

    def test_no_content_preserves_original(self, vault, inbox_with_docs):
        """content 필드가 없으면 원본 내용을 그대로 이동한다."""
        original = (vault / "INBOX" / "독서노트.md").read_text(encoding="utf-8")
        classifications = [
            {"path": "INBOX/독서노트.md", "category": "Resources"},
        ]
        apply_classification(vault, classifications)
        actual = (vault / "Resources" / "독서노트.md").read_text(encoding="utf-8")
        assert actual == original

    def test_target_folder_overrides_category_folder(self, vault, inbox_with_docs):
        """target_folder가 있으면 category 폴더 대신 해당 경로로 이동한다."""
        classifications = [
            {
                "path": "INBOX/프로젝트A.md",
                "category": "Projects",
                "target_folder": "Projects/SubTeam/Rocky",
            }
        ]
        result = apply_classification(vault, classifications)
        assert result.moved == 1
        assert (vault / "Projects" / "SubTeam" / "Rocky" / "프로젝트A.md").exists()
        assert not (vault / "Projects" / "프로젝트A.md").exists()

    def test_target_folder_created_if_missing(self, vault, inbox_with_docs):
        """target_folder가 없으면 자동 생성한다."""
        classifications = [
            {
                "path": "INBOX/독서노트.md",
                "category": "Resources",
                "target_folder": "Resources/NewSubDir",
            }
        ]
        apply_classification(vault, classifications)
        assert (vault / "Resources" / "NewSubDir" / "독서노트.md").exists()


# ---------------------------------------------------------------------------
# get_vault_structure
# ---------------------------------------------------------------------------

class TestGetVaultStructure:
    def test_returns_subdirs_and_doc_titles(self, vault: Path):
        para_map = {"Projects": "Projects", "Resources": "Resources"}
        proj = vault / "Projects"
        proj.mkdir()
        (proj / "SubA").mkdir()
        (proj / "SubA" / "SubB").mkdir()
        (proj / "SubA" / "note.md").write_text("# note", encoding="utf-8")

        structure = get_vault_structure(vault, para_map)
        assert "Projects" in structure
        subdirs = structure["Projects"]["subdirs"]
        assert any("SubA" in s for s in subdirs)
        assert "note" in structure["Projects"]["doc_titles"]

    def test_missing_para_folder_returns_empty(self, vault: Path):
        para_map = {"Areas": "30_Areas"}  # 폴더가 실제로 없음
        structure = get_vault_structure(vault, para_map)
        assert structure["Areas"]["subdirs"] == []
        assert structure["Areas"]["doc_titles"] == []

    def test_hidden_dirs_excluded(self, vault: Path):
        para_map = {"Projects": "Projects"}
        proj = vault / "Projects"
        proj.mkdir()
        (proj / ".obsidian").mkdir()
        (proj / ".obsidian" / "hidden.md").write_text("# hidden", encoding="utf-8")
        (proj / "visible.md").write_text("# visible", encoding="utf-8")

        structure = get_vault_structure(vault, para_map)
        assert "visible" in structure["Projects"]["doc_titles"]
        assert "hidden" not in structure["Projects"]["doc_titles"]


# ---------------------------------------------------------------------------
# load_inbox — full_content 지연 로드 확인
# ---------------------------------------------------------------------------

class TestLoadInboxFullContent:
    def test_full_content_is_empty(self, vault, inbox_with_docs):
        """load_inbox는 full_content를 로드하지 않는다."""
        docs = load_inbox(vault / "INBOX", vault)
        for doc in docs:
            assert doc.full_content == ""


# ---------------------------------------------------------------------------
# load_document_contents
# ---------------------------------------------------------------------------

class TestLoadDocumentContents:
    def test_returns_full_content(self, vault, inbox_with_docs):
        paths = ["INBOX/프로젝트A.md", "INBOX/독서노트.md"]
        contents = load_document_contents(vault, paths)
        assert len(contents) == 2
        assert "프로젝트A" in contents["INBOX/프로젝트A.md"]
        assert "독서노트" in contents["INBOX/독서노트.md"]

    def test_includes_frontmatter(self, vault: Path):
        inbox = vault / "INBOX"
        inbox.mkdir(exist_ok=True)
        raw = "---\ntags: [test]\n---\n# 제목\n본문"
        (inbox / "fm_test.md").write_text(raw, encoding="utf-8")
        contents = load_document_contents(vault, ["INBOX/fm_test.md"])
        assert contents["INBOX/fm_test.md"] == raw

    def test_missing_file_excluded(self, vault: Path):
        contents = load_document_contents(vault, ["INBOX/없는파일.md"])
        assert contents == {}

    def test_partial_failure_returns_successful_only(self, vault, inbox_with_docs):
        paths = ["INBOX/프로젝트A.md", "INBOX/없는파일.md"]
        contents = load_document_contents(vault, paths)
        assert len(contents) == 1
        assert "INBOX/프로젝트A.md" in contents


# ---------------------------------------------------------------------------
# load_template
# ---------------------------------------------------------------------------

class TestLoadTemplate:
    def test_returns_template_content(self, vault: Path):
        tmpl = vault / "Templates" / "project.md"
        tmpl.parent.mkdir()
        tmpl.write_text("---\nstatus: active\n---\n## 목표", encoding="utf-8")
        content = load_template(vault, "Templates/project.md")
        assert "status: active" in content

    def test_missing_template_returns_empty(self, vault: Path):
        assert load_template(vault, "Templates/없는파일.md") == ""

    def test_empty_rel_path_returns_empty(self, vault: Path):
        assert load_template(vault, "") == ""
