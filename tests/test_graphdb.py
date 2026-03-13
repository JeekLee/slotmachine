"""GraphDB 단위 테스트 — Neo4j 드라이버를 mock으로 대체한다."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from slotmachine.sync.graphdb import GraphDB, doc_id
from slotmachine.sync.parser import ParsedDocument


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_doc(
    path: str = "/vault/note.md",
    title: str = "Test Note",
    tags: list[str] | None = None,
    wiki_links: list[str] | None = None,
    content: str = "본문",
) -> ParsedDocument:
    return ParsedDocument(
        path=Path(path),
        title=title,
        frontmatter={},
        tags=tags or [],
        wiki_links=wiki_links or [],
        raw_content=content,
    )


def _make_db() -> tuple[GraphDB, MagicMock]:
    """GraphDB 인스턴스와 mock 드라이버를 반환한다."""
    with patch("slotmachine.sync.graphdb.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        db = GraphDB("bolt://localhost:7687", "neo4j", "test")
    return db, mock_driver


# ---------------------------------------------------------------------------
# doc_id
# ---------------------------------------------------------------------------

def test_doc_id_is_deterministic():
    assert doc_id(Path("/vault/note.md")) == doc_id(Path("/vault/note.md"))


def test_doc_id_length():
    assert len(doc_id(Path("/vault/note.md"))) == 16


def test_doc_id_differs_for_different_paths():
    assert doc_id(Path("/vault/a.md")) != doc_id(Path("/vault/b.md"))


# ---------------------------------------------------------------------------
# 연결 관리
# ---------------------------------------------------------------------------

def test_close_calls_driver_close():
    db, mock_driver = _make_db()
    db.close()
    mock_driver.close.assert_called_once()


def test_context_manager_closes_on_exit():
    db, mock_driver = _make_db()
    with db:
        pass
    mock_driver.close.assert_called_once()


def test_verify_connectivity_delegates():
    db, mock_driver = _make_db()
    db.verify_connectivity()
    mock_driver.verify_connectivity.assert_called_once()


# ---------------------------------------------------------------------------
# init_schema
# ---------------------------------------------------------------------------

def test_init_schema_runs_five_statements():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    db.init_schema()

    assert mock_session.run.call_count == 5


# ---------------------------------------------------------------------------
# upsert_document
# ---------------------------------------------------------------------------

def test_upsert_returns_doc_id():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    doc = _make_doc()
    result = db.upsert_document(doc)

    assert result == doc_id(doc.path)


def test_upsert_runs_merge_for_document():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    db.upsert_document(_make_doc())

    # 첫 번째 run 호출이 MERGE (d:Document ...) 포함해야 함
    first_call_query = mock_session.run.call_args_list[0][0][0]
    assert "MERGE (d:Document" in first_call_query


def test_upsert_skips_embedding_when_none():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    db.upsert_document(_make_doc(), embedding=None)

    all_queries = [c[0][0] for c in mock_session.run.call_args_list]
    assert not any("embedding" in q for q in all_queries)


def test_upsert_stores_embedding_when_provided():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    db.upsert_document(_make_doc(), embedding=[0.1, 0.2, 0.3])

    all_queries = [c[0][0] for c in mock_session.run.call_args_list]
    assert any("embedding" in q for q in all_queries)


def test_upsert_creates_tag_edges_per_tag():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    db.upsert_document(_make_doc(tags=["태그A", "태그B"]))

    tag_merge_calls = [
        c for c in mock_session.run.call_args_list
        if "MERGE (t:Tag" in c[0][0]
    ]
    assert len(tag_merge_calls) == 2


def test_upsert_creates_wiki_link_edges():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    db.upsert_document(_make_doc(wiki_links=["노트A", "노트B"]))

    links_to_calls = [
        c for c in mock_session.run.call_args_list
        if "LINKS_TO" in c[0][0] and "MERGE" in c[0][0]
    ]
    assert len(links_to_calls) == 2


def test_upsert_uses_inbox_as_default_para_category():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    db.upsert_document(_make_doc())

    first_kwargs = mock_session.run.call_args_list[0][1]
    assert first_kwargs["para_category"] == "Inbox"


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------

def test_delete_returns_true_when_deleted():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    mock_result = MagicMock()
    mock_result.single.return_value = {"deleted": 1}
    mock_session.run.return_value = mock_result

    assert db.delete_document(Path("/vault/note.md")) is True


def test_delete_returns_false_when_not_found():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    mock_result = MagicMock()
    mock_result.single.return_value = {"deleted": 0}
    mock_session.run.return_value = mock_result

    assert db.delete_document(Path("/vault/ghost.md")) is False


# ---------------------------------------------------------------------------
# get_document / document_exists
# ---------------------------------------------------------------------------

def test_get_document_returns_dict_when_found():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    mock_node = {"id": "abc123", "title": "Test"}
    mock_record = MagicMock()
    mock_record.__getitem__ = MagicMock(return_value=mock_node)
    mock_session.run.return_value.single.return_value = mock_record

    result = db.get_document(Path("/vault/note.md"))
    assert result == mock_node


def test_get_document_returns_none_when_not_found():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    mock_session.run.return_value.single.return_value = None

    assert db.get_document(Path("/vault/ghost.md")) is None


def test_document_exists_true():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    mock_node = {"id": "abc123"}
    mock_record = MagicMock()
    mock_record.__getitem__ = MagicMock(return_value=mock_node)
    mock_session.run.return_value.single.return_value = mock_record

    assert db.document_exists(Path("/vault/note.md")) is True


def test_document_exists_false():
    db, mock_driver = _make_db()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    mock_session.run.return_value.single.return_value = None

    assert db.document_exists(Path("/vault/ghost.md")) is False
