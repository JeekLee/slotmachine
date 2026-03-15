"""RAG 검색 모듈.

쿼리와 관련된 문서를 GraphDB에서 검색해 반환한다.
임베딩 프로바이더가 있으면 벡터 유사도 검색, 없으면 키워드 검색으로 폴백한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from slotmachine.sync.embedding import BaseEmbeddingProvider
from slotmachine.sync.graphdb import GraphDB

logger = logging.getLogger(__name__)


@dataclass
class RetrievedDoc:
    """검색된 단일 문서."""

    title: str
    path: str
    content: str
    score: float | None
    para_category: str
    tags: list[str] = field(default_factory=list)

    @property
    def excerpt(self) -> str:
        """본문 앞 300자 발췌."""
        return self.content[:300] + ("..." if len(self.content) > 300 else "")

    def obsidian_uri(self, vault_name: str) -> str:
        """Obsidian URI scheme 링크를 반환한다."""
        stem = Path(self.path).stem
        return f"obsidian://open?vault={vault_name}&file={stem}"


def retrieve(
    query: str,
    db: GraphDB,
    *,
    embedding_provider: BaseEmbeddingProvider | None = None,
    top_k: int = 5,
    para_filter: list[str] | None = None,
) -> list[RetrievedDoc]:
    """쿼리와 관련된 문서를 GraphDB에서 검색한다.

    임베딩 프로바이더가 있으면 벡터 유사도 검색,
    없으면 키워드 검색으로 폴백한다.

    Args:
        query: 검색 쿼리
        db: GraphDB 인스턴스
        embedding_provider: 임베딩 프로바이더 (None이면 키워드 검색)
        top_k: 반환할 최대 문서 수
        para_filter: 검색 범위를 제한할 PARA 카테고리 목록
                     예: ["Projects", "Areas"] — None이면 전체 카테고리 검색
    Returns:
        관련도 순 RetrievedDoc 목록
    """
    if embedding_provider:
        logger.debug("벡터 유사도 검색: %s (top_k=%d)", query, top_k)
        query_embedding = embedding_provider.embed_one(query)
        rows = db.search_similar_by_embedding(
            query_embedding, top_k=top_k, para_filter=para_filter
        )
    else:
        logger.debug("키워드 검색 (임베딩 프로바이더 없음): %s", query)
        rows = db.search_by_keyword(query, top_k=top_k, para_filter=para_filter)

    return [
        RetrievedDoc(
            title=row.get("title", ""),
            path=row.get("path", ""),
            content=row.get("content", ""),
            score=row.get("score"),
            para_category=row.get("para_category", "Inbox"),
            tags=row.get("tags") or [],
        )
        for row in rows
    ]
