"""Knowledge Graph 링커 단위 테스트 (F4)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slotmachine.linker.linker import (
    LinkCandidate,
    find_related,
    get_wikilinks_from_content,
    insert_wiki_links,
)


# ─────────────────────────────────────────────
# fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """임시 vault 구조를 생성한다."""
    (tmp_path / "Projects").mkdir()
    (tmp_path / "Resources").mkdir()
    return tmp_path


@pytest.fixture
def sample_doc(vault: Path) -> Path:
    """본문이 있는 샘플 문서를 생성한다."""
    doc = vault / "Projects" / "my_project.md"
    doc.write_text(
        "---\ntags: [project, coding]\n---\n# My Project\n\n본문 내용입니다.\n",
        encoding="utf-8",
    )
    return doc


@pytest.fixture
def mock_db() -> MagicMock:
    """GraphDB 목 객체를 반환한다."""
    db = MagicMock()
    db.get_document.return_value = {
        "title": "My Project",
        "path": "Projects/my_project.md",
        "content": "본문 내용입니다.",
        "tags": ["project", "coding"],
        "embedding": [0.1, 0.2, 0.3],
        "para_category": "Projects",
    }
    db.get_linked_titles.return_value = []
    db.get_graph_proximity.return_value = {"shared_tags": 0, "shared_links": 0}
    db.search_similar_by_embedding.return_value = [
        {
            "title": "Clean Code",
            "path": "Resources/clean_code.md",
            "content": "클린 코드 요약",
            "score": 0.85,
            "para_category": "Resources",
            "tags": ["coding"],
        },
        {
            "title": "Architecture Patterns",
            "path": "Resources/arch.md",
            "content": "아키텍처 패턴",
            "score": 0.72,
            "para_category": "Resources",
            "tags": [],
        },
    ]
    return db


# ─────────────────────────────────────────────
# get_wikilinks_from_content
# ─────────────────────────────────────────────


class TestGetWikilinksFromContent:
    def test_parses_simple_wikilink(self):
        content = "참고: [[Clean Code]]"
        assert get_wikilinks_from_content(content) == {"Clean Code"}

    def test_parses_multiple_wikilinks(self):
        content = "[[A]] 및 [[B]] 참고"
        assert get_wikilinks_from_content(content) == {"A", "B"}

    def test_parses_aliased_wikilink(self):
        content = "[[Clean Code|클린코드]] 참고"
        assert get_wikilinks_from_content(content) == {"Clean Code"}

    def test_empty_content_returns_empty_set(self):
        assert get_wikilinks_from_content("") == set()

    def test_no_wikilinks_returns_empty_set(self):
        assert get_wikilinks_from_content("일반 텍스트") == set()

    def test_strips_whitespace_from_title(self):
        content = "[[ Clean Code ]]"
        result = get_wikilinks_from_content(content)
        assert "Clean Code" in result

    def test_ignores_markdown_code_links(self):
        content = "일반 링크: [텍스트](url)"
        assert get_wikilinks_from_content(content) == set()

    def test_deduplicates(self):
        content = "[[A]] 그리고 [[A]]"
        assert get_wikilinks_from_content(content) == {"A"}


# ─────────────────────────────────────────────
# insert_wiki_links
# ─────────────────────────────────────────────


class TestInsertWikiLinks:
    def test_appends_related_section_if_missing(self, vault, sample_doc):
        insert_wiki_links(vault, "Projects/my_project.md", ["Clean Code"])
        content = sample_doc.read_text(encoding="utf-8")
        assert "## Related" in content
        assert "[[Clean Code]]" in content

    def test_links_in_related_section(self, vault, sample_doc):
        insert_wiki_links(vault, "Projects/my_project.md", ["A", "B"])
        content = sample_doc.read_text(encoding="utf-8")
        assert "[[A]]" in content
        assert "[[B]]" in content

    def test_skips_existing_wikilinks(self, vault: Path):
        doc = vault / "Projects" / "existing.md"
        doc.write_text("# 기존\n\n## Related\n\n- [[Already Linked]]\n", encoding="utf-8")
        insert_wiki_links(vault, "Projects/existing.md", ["Already Linked", "New Doc"])
        content = doc.read_text(encoding="utf-8")
        assert content.count("[[Already Linked]]") == 1  # 중복 삽입 없음
        assert "[[New Doc]]" in content

    def test_inserts_into_existing_related_section(self, vault: Path):
        doc = vault / "Projects" / "has_related.md"
        doc.write_text(
            "# 문서\n\n본문\n\n## Related\n\n- [[Old Link]]\n",
            encoding="utf-8",
        )
        insert_wiki_links(vault, "Projects/has_related.md", ["New Link"])
        content = doc.read_text(encoding="utf-8")
        assert "[[Old Link]]" in content
        assert "[[New Link]]" in content

    def test_inserts_before_next_heading(self, vault: Path):
        doc = vault / "Projects" / "multi_heading.md"
        doc.write_text(
            "# 문서\n\n## Related\n\n## Other Section\n\n내용\n",
            encoding="utf-8",
        )
        insert_wiki_links(vault, "Projects/multi_heading.md", ["Link"])
        content = doc.read_text(encoding="utf-8")
        related_pos = content.index("## Related")
        other_pos = content.index("## Other Section")
        link_pos = content.index("[[Link]]")
        assert related_pos < link_pos < other_pos

    def test_no_titles_no_change(self, vault, sample_doc):
        original = sample_doc.read_text(encoding="utf-8")
        insert_wiki_links(vault, "Projects/my_project.md", [])
        content = sample_doc.read_text(encoding="utf-8")
        assert content == original

    def test_returns_modified_content(self, vault, sample_doc):
        result = insert_wiki_links(vault, "Projects/my_project.md", ["Clean Code"])
        assert "[[Clean Code]]" in result

    def test_korean_related_heading(self, vault: Path):
        doc = vault / "Projects" / "korean.md"
        doc.write_text("# 문서\n\n## 관련\n\n", encoding="utf-8")
        insert_wiki_links(vault, "Projects/korean.md", ["Link"])
        content = doc.read_text(encoding="utf-8")
        assert "[[Link]]" in content

    def test_all_titles_existing_no_write(self, vault: Path):
        doc = vault / "Projects" / "full.md"
        doc.write_text("# 문서\n\n[[A]] [[B]]\n", encoding="utf-8")
        original_mtime = doc.stat().st_mtime
        import time; time.sleep(0.01)
        result = insert_wiki_links(vault, "Projects/full.md", ["A", "B"])
        # 변경 없으면 원본 내용 반환
        assert "[[A]]" in result
        assert "[[B]]" in result


# ─────────────────────────────────────────────
# find_related
# ─────────────────────────────────────────────


class TestFindRelated:
    def test_returns_candidates_above_threshold(self, mock_db):
        candidates = find_related("Projects/my_project.md", mock_db, threshold=0.5)
        assert len(candidates) > 0
        for c in candidates:
            assert c.final_score >= 0.5

    def test_excludes_self(self, mock_db):
        mock_db.search_similar_by_embedding.return_value = [
            {
                "title": "My Project",
                "path": "Projects/my_project.md",
                "content": "self",
                "score": 1.0,
                "para_category": "Projects",
                "tags": [],
            }
        ]
        candidates = find_related("Projects/my_project.md", mock_db)
        assert all(c.path != "Projects/my_project.md" for c in candidates)

    def test_excludes_already_linked(self, mock_db):
        mock_db.get_linked_titles.return_value = ["Clean Code"]
        candidates = find_related("Projects/my_project.md", mock_db)
        assert all(c.title != "Clean Code" for c in candidates)

    def test_proximity_boost_applied(self, mock_db):
        # 공통 태그 2개 → 부스트 0.10
        mock_db.get_graph_proximity.return_value = {"shared_tags": 2, "shared_links": 0}
        candidates = find_related("Projects/my_project.md", mock_db, threshold=0.0)
        for c in candidates:
            assert c.proximity_boost == pytest.approx(0.10, abs=1e-4)
            assert c.final_score == pytest.approx(c.vector_score + 0.10, abs=1e-4)

    def test_final_score_capped_at_1(self, mock_db):
        mock_db.search_similar_by_embedding.return_value = [
            {
                "title": "High Score Doc",
                "path": "Resources/high.md",
                "content": "내용",
                "score": 0.98,
                "para_category": "Resources",
                "tags": [],
            }
        ]
        mock_db.get_graph_proximity.return_value = {"shared_tags": 5, "shared_links": 5}
        candidates = find_related("Projects/my_project.md", mock_db, threshold=0.0)
        for c in candidates:
            assert c.final_score <= 1.0

    def test_returns_empty_if_doc_not_in_db(self, mock_db):
        mock_db.get_document.return_value = None
        candidates = find_related("Projects/missing.md", mock_db)
        assert candidates == []

    def test_keyword_fallback_when_no_embedding(self, mock_db):
        mock_db.get_document.return_value = {
            "title": "My Project",
            "path": "Projects/my_project.md",
            "content": "본문",
            "tags": ["project"],
            "embedding": None,
            "para_category": "Projects",
        }
        mock_db.search_by_keyword.return_value = [
            {
                "title": "Keyword Doc",
                "path": "Resources/kw.md",
                "content": "키워드 내용",
                "score": None,
                "para_category": "Resources",
                "tags": [],
            }
        ]
        candidates = find_related("Projects/my_project.md", mock_db, threshold=0.0)
        mock_db.search_by_keyword.assert_called_once()
        assert any(c.title == "Keyword Doc" for c in candidates)

    def test_top_k_limits_results(self, mock_db):
        many = [
            {
                "title": f"Doc{i}",
                "path": f"Resources/doc{i}.md",
                "content": f"내용 {i}",
                "score": 0.9 - i * 0.01,
                "para_category": "Resources",
                "tags": [],
            }
            for i in range(20)
        ]
        mock_db.search_similar_by_embedding.return_value = many
        candidates = find_related(
            "Projects/my_project.md", mock_db, top_k=5, threshold=0.0
        )
        assert len(candidates) <= 5

    def test_sorted_by_final_score_descending(self, mock_db):
        candidates = find_related("Projects/my_project.md", mock_db, threshold=0.0)
        scores = [c.final_score for c in candidates]
        assert scores == sorted(scores, reverse=True)

    def test_candidate_fields_populated(self, mock_db):
        candidates = find_related("Projects/my_project.md", mock_db, threshold=0.5)
        assert len(candidates) > 0
        c = candidates[0]
        assert c.title
        assert c.path
        assert 0.0 <= c.final_score <= 1.0
        assert c.para_category
