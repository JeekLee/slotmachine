"""F4 + F5 통합 테스트 — linker 및 recall 파이프라인 end-to-end.

실제 파일 시스템(tmp_path)과 GraphDB mock을 사용한다.
Neo4j 없이 로직 전체를 검증한다.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slotmachine.linker.linker import (
    find_related,
    get_wikilinks_from_content,
    insert_wiki_links,
)
from slotmachine.rag.retriever import RetrievedDoc, retrieve


# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────


def _write_md(base: Path, rel: str, content: str) -> Path:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _make_db_mock(
    doc_data: dict | None = None,
    candidates: list[dict] | None = None,
    linked_titles: list[str] | None = None,
    proximity: dict | None = None,
) -> MagicMock:
    db = MagicMock()
    db.get_document.return_value = doc_data or {
        "title": "Target Doc",
        "path": "Projects/target.md",
        "content": "타겟 문서 내용입니다.",
        "tags": ["project", "coding"],
        "embedding": [0.5, 0.5, 0.5],
        "para_category": "Projects",
    }
    db.get_linked_titles.return_value = linked_titles or []
    db.get_graph_proximity.return_value = proximity or {"shared_tags": 0, "shared_links": 0}
    db.search_similar_by_embedding.return_value = candidates or [
        {
            "title": "Related Doc A",
            "path": "Resources/doc_a.md",
            "content": "관련 문서 A 내용",
            "score": 0.88,
            "para_category": "Resources",
            "tags": ["coding"],
        },
        {
            "title": "Related Doc B",
            "path": "Areas/doc_b.md",
            "content": "관련 문서 B 내용",
            "score": 0.72,
            "para_category": "Areas",
            "tags": ["project"],
        },
    ]
    db.upsert_related_edges.return_value = None
    db.search_by_keyword.return_value = []
    return db


# ─────────────────────────────────────────────
# F4 통합: find_related → insert_wiki_links
# ─────────────────────────────────────────────


class TestF4LinkingPipeline:
    """find_related 결과를 실제 파일에 insert_wiki_links로 적용하는 통합 흐름."""

    def test_full_link_pipeline(self, tmp_path: Path):
        """관련 문서 탐색 → 파일 위키링크 삽입 전체 흐름."""
        # 1. 대상 문서 생성
        target = _write_md(
            tmp_path,
            "Projects/target.md",
            "---\ntags: [project]\n---\n# Target Doc\n\n내용입니다.\n",
        )

        db = _make_db_mock()
        candidates = find_related("Projects/target.md", db, threshold=0.5)

        assert len(candidates) == 2
        assert candidates[0].title == "Related Doc A"
        assert candidates[0].final_score >= candidates[1].final_score

        # 2. 승인된 링크를 파일에 삽입
        link_titles = [c.title for c in candidates]
        result_content = insert_wiki_links(tmp_path, "Projects/target.md", link_titles)

        # 3. 검증
        assert "## Related" in result_content
        assert "[[Related Doc A]]" in result_content
        assert "[[Related Doc B]]" in result_content

        # 파일에 실제 반영됐는지 확인
        on_disk = target.read_text(encoding="utf-8")
        assert "[[Related Doc A]]" in on_disk

    def test_already_linked_not_duplicated(self, tmp_path: Path):
        """이미 연결된 문서는 재삽입되지 않는다."""
        _write_md(
            tmp_path,
            "Projects/target.md",
            "# Target\n\n[[Related Doc A]]\n",
        )
        db = _make_db_mock(linked_titles=["Related Doc A"])
        candidates = find_related("Projects/target.md", db, threshold=0.0)

        # Related Doc A는 already_linked이므로 후보에서 제외
        assert all(c.title != "Related Doc A" for c in candidates)

    def test_proximity_boost_changes_ranking(self, tmp_path: Path):
        """공통 태그가 많으면 순위가 올라간다."""
        _write_md(tmp_path, "Projects/target.md", "# T\n")

        def proximity_side_effect(src, cand):
            if "doc_b" in cand:
                return {"shared_tags": 4, "shared_links": 2}  # 부스트 0.20+0.06=0.26
            return {"shared_tags": 0, "shared_links": 0}

        db = _make_db_mock()
        db.get_graph_proximity.side_effect = proximity_side_effect

        candidates = find_related("Projects/target.md", db, threshold=0.0)
        # doc_b (원래 0.72)가 doc_a (0.88)보다 점수가 높아야 함 (0.72+0.26=0.98 > 0.88)
        assert candidates[0].title == "Related Doc B"

    def test_no_candidates_above_threshold(self, tmp_path: Path):
        """임계값 이상의 후보가 없으면 빈 목록을 반환한다."""
        _write_md(tmp_path, "Projects/target.md", "# T\n")
        db = _make_db_mock(
            candidates=[
                {
                    "title": "Low Score Doc",
                    "path": "Resources/low.md",
                    "content": "내용",
                    "score": 0.3,
                    "para_category": "Resources",
                    "tags": [],
                }
            ]
        )
        candidates = find_related("Projects/target.md", db, threshold=0.5)
        assert candidates == []

    def test_insert_creates_related_section_once(self, tmp_path: Path):
        """위키링크를 두 번 호출해도 Related 섹션이 하나만 생긴다."""
        _write_md(tmp_path, "Projects/target.md", "# T\n\n내용\n")
        insert_wiki_links(tmp_path, "Projects/target.md", ["Doc A"])
        insert_wiki_links(tmp_path, "Projects/target.md", ["Doc B"])

        content = (tmp_path / "Projects/target.md").read_text(encoding="utf-8")
        assert content.count("## Related") == 1
        assert "[[Doc A]]" in content
        assert "[[Doc B]]" in content


# ─────────────────────────────────────────────
# F5 통합: retrieve + para_filter
# ─────────────────────────────────────────────


class TestF5RetrievePipeline:
    """retrieve() 파이프라인 통합 흐름 — para_filter 포함."""

    def test_retrieve_returns_docs_for_query(self):
        db = MagicMock()
        db.search_by_keyword.return_value = [
            {
                "title": "My Note",
                "path": "/vault/note.md",
                "content": "Python async 패턴 정리",
                "score": None,
                "para_category": "Resources",
                "tags": ["python"],
            }
        ]
        docs = retrieve("Python async", db, embedding_provider=None)
        assert len(docs) == 1
        assert isinstance(docs[0], RetrievedDoc)
        assert docs[0].title == "My Note"

    def test_retrieve_with_para_filter_passed_to_db(self):
        db = MagicMock()
        db.search_by_keyword.return_value = []
        retrieve("query", db, embedding_provider=None, para_filter=["Projects"])
        db.search_by_keyword.assert_called_once_with(
            "query", top_k=5, para_filter=["Projects"]
        )

    def test_retrieve_para_filter_with_embedding(self):
        db = MagicMock()
        db.search_similar_by_embedding.return_value = []
        embedder = MagicMock()
        embedder.embed_one.return_value = [0.1, 0.2]

        retrieve("query", db, embedding_provider=embedder, para_filter=["Resources"])

        _, kwargs = db.search_similar_by_embedding.call_args
        assert kwargs.get("para_filter") == ["Resources"]

    def test_retrieve_empty_result_returns_empty_list(self):
        db = MagicMock()
        db.search_by_keyword.return_value = []
        docs = retrieve("없는 내용", db, embedding_provider=None)
        assert docs == []

    def test_retrieve_obsidian_uri_format(self):
        db = MagicMock()
        db.search_by_keyword.return_value = [
            {
                "title": "Note",
                "path": "/vault/Note.md",
                "content": "내용",
                "score": None,
                "para_category": "Projects",
                "tags": [],
            }
        ]
        docs = retrieve("query", db, embedding_provider=None)
        uri = docs[0].obsidian_uri("MyVault")
        assert uri.startswith("obsidian://open")
        assert "MyVault" in uri
        assert "Note" in uri


# ─────────────────────────────────────────────
# F4 + F5 연계: 분류 → 링크 → 검색
# ─────────────────────────────────────────────


class TestF4F5Integration:
    """F4(링크 삽입) 후 F5(검색)에서 위키링크가 포함된 문서를 찾는 통합 시나리오."""

    def test_linked_doc_retrievable_after_insert(self, tmp_path: Path):
        """링크 삽입 후 파일 내용에 위키링크가 포함돼 있어야 한다."""
        _write_md(tmp_path, "Projects/target.md", "# Target\n\n클린코드 공부 중\n")

        insert_wiki_links(tmp_path, "Projects/target.md", ["Clean Code", "Architecture"])
        content = (tmp_path / "Projects/target.md").read_text(encoding="utf-8")

        links = get_wikilinks_from_content(content)
        assert "Clean Code" in links
        assert "Architecture" in links

    def test_wikilinks_in_content_parseable(self, tmp_path: Path):
        """삽입된 위키링크를 get_wikilinks_from_content로 완전히 파싱할 수 있다."""
        _write_md(
            tmp_path,
            "Resources/note.md",
            "# Note\n\n## Related\n\n- [[Doc A]]\n- [[Doc B|별칭]]\n",
        )
        content = (tmp_path / "Resources/note.md").read_text(encoding="utf-8")
        links = get_wikilinks_from_content(content)
        assert links == {"Doc A", "Doc B"}
