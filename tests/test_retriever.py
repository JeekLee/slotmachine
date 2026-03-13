"""RAG retriever 및 GraphDB 검색 메서드 테스트."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from slotmachine.rag.retriever import RetrievedDoc, retrieve
from slotmachine.sync.embedding import BaseEmbeddingProvider


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_db(rows: list[dict] | None = None) -> MagicMock:
    db = MagicMock()
    rows = rows or []
    db.search_similar_by_embedding.return_value = rows
    db.search_by_keyword.return_value = rows
    return db


def _row(
    title: str = "Test",
    path: str = "/vault/test.md",
    content: str = "내용",
    score: float | None = 0.9,
    para_category: str = "Resources",
    tags: list[str] | None = None,
) -> dict:
    return {
        "title": title,
        "path": path,
        "content": content,
        "score": score,
        "para_category": para_category,
        "tags": tags or [],
    }


# ---------------------------------------------------------------------------
# RetrievedDoc
# ---------------------------------------------------------------------------

class TestRetrievedDoc:
    def test_excerpt_truncates_long_content(self):
        doc = RetrievedDoc(
            title="T", path="/t.md", content="x" * 400, score=0.9, para_category="Inbox"
        )
        assert doc.excerpt.endswith("...")
        assert len(doc.excerpt) == 303  # 300 + "..."

    def test_excerpt_no_ellipsis_for_short_content(self):
        doc = RetrievedDoc(
            title="T", path="/t.md", content="short", score=0.9, para_category="Inbox"
        )
        assert doc.excerpt == "short"

    def test_excerpt_exactly_300_chars_no_ellipsis(self):
        doc = RetrievedDoc(
            title="T", path="/t.md", content="x" * 300, score=0.9, para_category="Inbox"
        )
        assert not doc.excerpt.endswith("...")

    def test_obsidian_uri_contains_vault_name(self):
        doc = RetrievedDoc(
            title="Note", path="/vault/Note.md", content="", score=None, para_category="Inbox"
        )
        uri = doc.obsidian_uri("MyVault")
        assert "obsidian://open" in uri
        assert "MyVault" in uri

    def test_obsidian_uri_uses_file_stem(self):
        doc = RetrievedDoc(
            title="Note", path="/vault/my_note.md", content="", score=None, para_category="Inbox"
        )
        uri = doc.obsidian_uri("Vault")
        assert "my_note" in uri

    def test_tags_default_to_empty_list(self):
        doc = RetrievedDoc(
            title="T", path="/t.md", content="", score=None, para_category="Inbox"
        )
        assert doc.tags == []


# ---------------------------------------------------------------------------
# retrieve() — 라우팅
# ---------------------------------------------------------------------------

class TestRetrieve:
    def test_uses_vector_search_when_provider_given(self):
        db = _make_db([_row()])
        embedder = MagicMock(spec=BaseEmbeddingProvider)
        embedder.embed_one.return_value = [0.1, 0.2]

        retrieve("쿼리", db, embedding_provider=embedder)

        db.search_similar_by_embedding.assert_called_once()
        db.search_by_keyword.assert_not_called()

    def test_uses_keyword_search_when_no_provider(self):
        db = _make_db([_row()])

        retrieve("쿼리", db, embedding_provider=None)

        db.search_by_keyword.assert_called_once_with("쿼리", top_k=5)
        db.search_similar_by_embedding.assert_not_called()

    def test_top_k_forwarded_to_vector_search(self):
        db = _make_db()
        embedder = MagicMock(spec=BaseEmbeddingProvider)
        embedder.embed_one.return_value = [0.1]

        retrieve("q", db, embedding_provider=embedder, top_k=3)

        _, kwargs = db.search_similar_by_embedding.call_args
        assert kwargs.get("top_k") == 3 or db.search_similar_by_embedding.call_args[0][1] == 3

    def test_top_k_forwarded_to_keyword_search(self):
        db = _make_db()
        retrieve("q", db, embedding_provider=None, top_k=3)
        db.search_by_keyword.assert_called_once_with("q", top_k=3)

    def test_returns_retrieved_doc_instances(self):
        db = _make_db([_row(title="My Note")])
        result = retrieve("q", db)
        assert len(result) == 1
        assert isinstance(result[0], RetrievedDoc)
        assert result[0].title == "My Note"

    def test_empty_result_returns_empty_list(self):
        db = _make_db([])
        result = retrieve("q", db)
        assert result == []

    def test_score_preserved(self):
        db = _make_db([_row(score=0.87)])
        result = retrieve("q", db)
        assert result[0].score == pytest.approx(0.87)

    def test_score_none_preserved(self):
        db = _make_db([_row(score=None)])
        result = retrieve("q", db)
        assert result[0].score is None

    def test_tags_none_becomes_empty_list(self):
        db = _make_db([_row(tags=None)])
        result = retrieve("q", db)
        assert result[0].tags == []

    def test_multiple_docs_returned(self):
        db = _make_db([_row(title=f"Doc{i}") for i in range(3)])
        result = retrieve("q", db)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# GraphDB.search_similar_by_embedding (mock 세션 사용)
# ---------------------------------------------------------------------------

def _make_graphdb_with_session():
    with patch("slotmachine.sync.graphdb.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        from slotmachine.sync.graphdb import GraphDB
        db = GraphDB("bolt://localhost:7687", "neo4j", "test")
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return db, mock_session


class TestGraphDBSearch:
    def test_search_similar_empty_when_no_docs(self):
        db, mock_session = _make_graphdb_with_session()
        mock_session.run.return_value.data.return_value = []

        result = db.search_similar_by_embedding([0.1, 0.2], top_k=5)
        assert result == []

    def test_search_similar_returns_top_k(self):
        db, mock_session = _make_graphdb_with_session()
        rows = [
            {"title": f"Doc{i}", "path": f"/d{i}.md", "content": "c",
             "para_category": "Inbox", "tags": [],
             "embedding": [0.1 * (i + 1), 0.1 * (i + 1)]}
            for i in range(5)
        ]
        mock_session.run.return_value.data.return_value = rows

        result = db.search_similar_by_embedding([0.9, 0.9], top_k=3)
        assert len(result) == 3

    def test_search_similar_excludes_embedding_field(self):
        db, mock_session = _make_graphdb_with_session()
        mock_session.run.return_value.data.return_value = [
            {"title": "T", "path": "/t.md", "content": "c",
             "para_category": "Inbox", "tags": [], "embedding": [0.5, 0.5]}
        ]
        result = db.search_similar_by_embedding([0.5, 0.5], top_k=1)
        assert "embedding" not in result[0]

    def test_search_similar_has_score_field(self):
        db, mock_session = _make_graphdb_with_session()
        mock_session.run.return_value.data.return_value = [
            {"title": "T", "path": "/t.md", "content": "c",
             "para_category": "Inbox", "tags": [], "embedding": [1.0, 0.0]}
        ]
        result = db.search_similar_by_embedding([1.0, 0.0], top_k=1)
        assert "score" in result[0]
        assert result[0]["score"] == pytest.approx(1.0)

    def test_search_by_keyword_returns_rows(self):
        db, mock_session = _make_graphdb_with_session()
        mock_session.run.return_value.data.return_value = [
            {"title": "Python 노트", "path": "/p.md", "content": "파이썬 내용",
             "para_category": "Resources", "tags": ["python"]}
        ]
        result = db.search_by_keyword("파이썬", top_k=5)
        assert len(result) == 1
        assert result[0]["title"] == "Python 노트"

    def test_search_by_keyword_score_is_none(self):
        db, mock_session = _make_graphdb_with_session()
        mock_session.run.return_value.data.return_value = [
            {"title": "T", "path": "/t.md", "content": "c",
             "para_category": "Inbox", "tags": []}
        ]
        result = db.search_by_keyword("T", top_k=5)
        assert result[0]["score"] is None
