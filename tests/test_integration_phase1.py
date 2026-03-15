"""Phase 1 통합 테스트.

parse_document → embed → upsert_document 전 파이프라인을 검증한다.
Neo4j 드라이버는 mock으로 대체하고, 파일 시스템은 실제 tmp_path를 사용한다.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from slotmachine.sync.embedding import BaseEmbeddingProvider
from slotmachine.sync.full_sync import SyncResult, full_sync
from slotmachine.sync.graphdb import GraphDB, doc_id
from slotmachine.sync.parser import parse_document


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


class _StubEmbedder(BaseEmbeddingProvider):
    """테스트용 고정 벡터 반환 embedder."""
    def __init__(self, dim: int = 4):
        self._dim = dim
        self.called_with: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.called_with.extend(texts)
        return [[0.1 * (i + 1) for i in range(self._dim)] for _ in texts]


# ---------------------------------------------------------------------------
# 파서 → GraphDB 단위 연동
# ---------------------------------------------------------------------------

class TestParserToGraphDB:
    def test_parsed_doc_upserted_with_correct_title(self, tmp_path):
        p = _write_md(tmp_path, "note.md", "# Hello World\n\n내용")
        db, mock_session = _make_db()

        doc = parse_document(p)
        db.upsert_document(doc)

        first_call_kwargs = mock_session.run.call_args_list[0][1]
        assert first_call_kwargs["title"] == "Hello World"

    def test_parsed_doc_upserted_with_tags(self, tmp_path):
        p = _write_md(tmp_path, "note.md", "---\ntags:\n  - python\n  - test\n---\n# Note\n")
        db, mock_session = _make_db()

        doc = parse_document(p)
        db.upsert_document(doc)

        first_kwargs = mock_session.run.call_args_list[0][1]
        assert "python" in first_kwargs["tags"]
        assert "test" in first_kwargs["tags"]

    def test_parsed_doc_tag_edges_created(self, tmp_path):
        p = _write_md(tmp_path, "note.md", "#태그A #태그B\n")
        db, mock_session = _make_db()

        doc = parse_document(p)
        db.upsert_document(doc)

        tag_calls = [c for c in mock_session.run.call_args_list if "MERGE (t:Tag" in c[0][0]]
        assert len(tag_calls) == 2

    def test_parsed_doc_wiki_link_edges_created(self, tmp_path):
        p = _write_md(tmp_path, "note.md", "참고: [[노트A]] [[노트B]]\n")
        db, mock_session = _make_db()

        doc = parse_document(p)
        db.upsert_document(doc)

        link_calls = [
            c for c in mock_session.run.call_args_list
            if "LINKS_TO" in c[0][0] and "MERGE" in c[0][0]
        ]
        assert len(link_calls) == 2

    def test_doc_id_is_path_based(self, tmp_path):
        p = _write_md(tmp_path, "note.md", "# Note\n")
        doc = parse_document(p)
        assert doc_id(doc.path) == doc_id(p)


# ---------------------------------------------------------------------------
# 임베딩 → GraphDB 연동
# ---------------------------------------------------------------------------

class TestEmbeddingToGraphDB:
    def test_embedding_stored_in_upsert(self, tmp_path):
        p = _write_md(tmp_path, "note.md", "# Note\n본문 내용")
        db, mock_session = _make_db()
        embedder = _StubEmbedder(dim=4)

        doc = parse_document(p)
        vec = embedder.embed_one(doc.raw_content)
        db.upsert_document(doc, embedding=vec)

        emb_call = next(
            c for c in mock_session.run.call_args_list if "embedding" in c[0][0]
        )
        assert emb_call[1]["embedding"] == vec

    def test_embedder_called_with_raw_content(self, tmp_path):
        p = _write_md(tmp_path, "note.md", "# Note\n본문 내용")
        embedder = _StubEmbedder()

        doc = parse_document(p)
        embedder.embed_one(doc.raw_content)

        assert doc.raw_content in embedder.called_with

    def test_no_embedding_call_when_provider_is_none(self, tmp_path):
        p = _write_md(tmp_path, "note.md", "# Note\n")
        db, mock_session = _make_db()

        doc = parse_document(p)
        db.upsert_document(doc, embedding=None)

        emb_calls = [c for c in mock_session.run.call_args_list if "embedding" in c[0][0]]
        assert emb_calls == []


# ---------------------------------------------------------------------------
# full_sync 전체 파이프라인
# ---------------------------------------------------------------------------

class TestFullSyncPipeline:
    def test_pipeline_processes_all_files(self, tmp_path):
        _write_md(tmp_path, "a.md", "# A\n내용A")
        _write_md(tmp_path, "sub/b.md", "# B\n내용B")
        db, _ = _make_db()

        result = full_sync(tmp_path, db, show_progress=False)

        assert result.total == 2
        assert result.success == 2
        assert result.failed == 0

    def test_pipeline_with_embedder_calls_embed_per_file(self, tmp_path):
        _write_md(tmp_path, "a.md", "# A\n내용A")
        _write_md(tmp_path, "b.md", "# B\n내용B")
        db, _ = _make_db()
        embedder = _StubEmbedder()

        full_sync(tmp_path, db, embedding_provider=embedder, show_progress=False)

        assert len(embedder.called_with) == 2

    def test_pipeline_passes_embedding_to_upsert(self, tmp_path):
        _write_md(tmp_path, "note.md", "# Note\n본문")
        db, mock_session = _make_db()
        embedder = _StubEmbedder(dim=4)

        full_sync(tmp_path, db, embedding_provider=embedder, show_progress=False)

        emb_calls = [c for c in mock_session.run.call_args_list if "embedding" in c[0][0]]
        assert len(emb_calls) == 1
        assert emb_calls[0][1]["embedding"] == pytest.approx([0.1, 0.2, 0.3, 0.4])

    def test_pipeline_without_embedder_skips_embedding(self, tmp_path):
        _write_md(tmp_path, "note.md", "# Note\n본문")
        db, mock_session = _make_db()

        full_sync(tmp_path, db, embedding_provider=None, show_progress=False)

        emb_calls = [c for c in mock_session.run.call_args_list if "embedding" in c[0][0]]
        assert emb_calls == []

    def test_pipeline_error_in_embed_counts_as_failed(self, tmp_path):
        _write_md(tmp_path, "note.md", "# Note\n")
        db, _ = _make_db()

        bad_embedder = MagicMock(spec=BaseEmbeddingProvider)
        bad_embedder.embed_one.side_effect = RuntimeError("임베딩 API 오류")

        result = full_sync(tmp_path, db, embedding_provider=bad_embedder, show_progress=False)

        assert result.failed == 1
        assert result.success == 0

    def test_pipeline_infers_para_category_from_path(self, tmp_path):
        """파일 경로에서 PARA 카테고리를 자동으로 추론한다."""
        _write_md(tmp_path, "Resources/note.md", "# Note\n")
        db, mock_session = _make_db()

        full_sync(
            tmp_path, db,
            para_folder_map={"Projects": "Projects", "Areas": "Areas",
                             "Resources": "Resources", "Archives": "Archives"},
            show_progress=False,
        )

        first_kwargs = mock_session.run.call_args_list[0][1]
        assert first_kwargs["para_category"] == "Resources"

    def test_pipeline_nested_vault_structure(self, tmp_path):
        _write_md(tmp_path, "Projects/p1.md", "# P1\n")
        _write_md(tmp_path, "Areas/a1.md", "# A1\n")
        _write_md(tmp_path, "Resources/r1.md", "# R1\n")
        db, _ = _make_db()

        result = full_sync(tmp_path, db, show_progress=False)

        assert result.total == 3
        assert result.success == 3

    def test_pipeline_result_has_error_details(self, tmp_path):
        p = _write_md(tmp_path, "bad.md", "# Bad\n")
        db, _ = _make_db()

        with patch("slotmachine.sync.full_sync.parse_document", side_effect=ValueError("파싱 실패")):
            result = full_sync(tmp_path, db, show_progress=False)

        assert len(result.errors) == 1
        assert result.errors[0][0] == p
        assert "파싱 실패" in result.errors[0][1]
