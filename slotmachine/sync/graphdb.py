"""Neo4j 연결 및 GraphDB 쓰기 모듈.

Document 노드, Tag/Folder 노드, LINKS_TO/TAGGED_WITH/IN_FOLDER 엣지를 관리한다.

스키마 개요
-----------
노드
  - Document  : id(hash), title, path, content, tags[], para_category,
                embedding[], created_at, updated_at
  - Tag       : name
  - Folder    : path

엣지
  - LINKS_TO    : Document → Document  (위키링크)
  - TAGGED_WITH : Document → Tag
  - IN_FOLDER   : Document → Folder
  - RELATED_TO  : Document → Document  (유사도 기반, F4에서 추가)
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase, Driver

from slotmachine.sync.parser import ParsedDocument


def doc_id(path: Path | str) -> str:
    """파일 경로 기반 16자 고유 ID를 반환한다."""
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]


class GraphDB:
    """Neo4j 드라이버 래퍼 — Document 중심 CRUD를 제공한다."""

    def __init__(self, uri: str, username: str, password: str) -> None:
        self._driver: Driver = GraphDatabase.driver(uri, auth=(username, password))

    # ------------------------------------------------------------------
    # 연결 관리
    # ------------------------------------------------------------------

    def verify_connectivity(self) -> None:
        """Neo4j 서버 연결 가능 여부를 확인한다."""
        self._driver.verify_connectivity()

    def close(self) -> None:
        """드라이버 연결을 닫는다."""
        self._driver.close()

    def __enter__(self) -> "GraphDB":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # 스키마 초기화
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """제약조건(Constraint) 및 인덱스를 생성한다.

        멱등성 보장 — 이미 존재하면 무시된다 (IF NOT EXISTS).
        """
        statements = [
            # 유니크 제약
            "CREATE CONSTRAINT document_id_unique IF NOT EXISTS "
            "FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT tag_name_unique IF NOT EXISTS "
            "FOR (t:Tag) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT folder_path_unique IF NOT EXISTS "
            "FOR (f:Folder) REQUIRE f.path IS UNIQUE",
            # 조회 인덱스
            "CREATE INDEX document_path IF NOT EXISTS "
            "FOR (d:Document) ON (d.path)",
            "CREATE INDEX document_title IF NOT EXISTS "
            "FOR (d:Document) ON (d.title)",
        ]
        with self._driver.session() as session:
            for stmt in statements:
                session.run(stmt)

    # ------------------------------------------------------------------
    # Document CRUD
    # ------------------------------------------------------------------

    def upsert_document(
        self,
        doc: ParsedDocument,
        *,
        embedding: list[float] | None = None,
        para_category: str = "Inbox",
    ) -> str:
        """Document 노드를 생성 또는 업데이트하고 관련 엣지를 재연결한다.

        Returns:
            생성·업데이트된 Document 노드의 id
        """
        node_id = doc_id(doc.path)

        with self._driver.session() as session:
            # Document 노드 upsert
            session.run(
                """
                MERGE (d:Document {id: $id})
                ON CREATE SET d.created_at = datetime()
                SET d.title        = $title,
                    d.path         = $path,
                    d.content      = $content,
                    d.tags         = $tags,
                    d.para_category = $para_category,
                    d.updated_at   = datetime()
                """,
                id=node_id,
                title=doc.title,
                path=str(doc.path),
                content=doc.raw_content,
                tags=doc.tags,
                para_category=para_category,
            )

            # 임베딩 (선택)
            if embedding is not None:
                session.run(
                    "MATCH (d:Document {id: $id}) SET d.embedding = $embedding",
                    id=node_id,
                    embedding=embedding,
                )

            # 태그 엣지 재연결
            session.run(
                "MATCH (d:Document {id: $id})-[r:TAGGED_WITH]->() DELETE r",
                id=node_id,
            )
            for tag in doc.tags:
                session.run(
                    """
                    MERGE (t:Tag {name: $tag})
                    WITH t
                    MATCH (d:Document {id: $id})
                    MERGE (d)-[:TAGGED_WITH]->(t)
                    """,
                    tag=tag,
                    id=node_id,
                )

            # 폴더 엣지
            session.run(
                """
                MERGE (f:Folder {path: $folder_path})
                WITH f
                MATCH (d:Document {id: $id})
                MERGE (d)-[:IN_FOLDER]->(f)
                """,
                folder_path=str(doc.path.parent),
                id=node_id,
            )

            # 위키링크 엣지 재연결 (대상 Document가 이미 존재할 때만)
            session.run(
                "MATCH (d:Document {id: $id})-[r:LINKS_TO]->() DELETE r",
                id=node_id,
            )
            for link_title in doc.wiki_links:
                session.run(
                    """
                    MATCH (src:Document {id: $id})
                    MATCH (dst:Document {title: $link_title})
                    MERGE (src)-[:LINKS_TO]->(dst)
                    """,
                    id=node_id,
                    link_title=link_title,
                )

        return node_id

    def delete_document(self, path: Path | str) -> bool:
        """Document 노드와 연결된 모든 엣지를 제거한다.

        Returns:
            삭제된 노드가 있으면 True
        """
        node_id = doc_id(Path(path))
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (d:Document {id: $id})
                DETACH DELETE d
                RETURN count(d) AS deleted
                """,
                id=node_id,
            )
            record = result.single()
            return bool(record and record["deleted"] > 0)

    def get_document(self, path: Path | str) -> dict | None:
        """경로로 Document 노드를 조회한다.

        Returns:
            노드 프로퍼티 dict, 없으면 None
        """
        with self._driver.session() as session:
            result = session.run(
                "MATCH (d:Document {path: $path}) RETURN d",
                path=str(path),
            )
            record = result.single()
            return dict(record["d"]) if record else None

    def document_exists(self, path: Path | str) -> bool:
        """해당 경로의 Document 노드 존재 여부를 반환한다."""
        return self.get_document(path) is not None

    # ------------------------------------------------------------------
    # 검색 (RAG)
    # ------------------------------------------------------------------

    def search_similar_by_embedding(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        """쿼리 임베딩과 코사인 유사도가 높은 Document를 반환한다.

        임베딩이 저장된 문서에 한해 Python-side 코사인 유사도를 계산한다.

        Args:
            query_embedding: 쿼리 임베딩 벡터
            top_k: 반환할 최대 문서 수
        Returns:
            score 내림차순으로 정렬된 문서 dict 목록 (embedding 필드 제외)
        """
        import numpy as np

        with self._driver.session() as session:
            rows = session.run(
                """
                MATCH (d:Document)
                WHERE d.embedding IS NOT NULL
                RETURN d.id AS id, d.title AS title, d.path AS path,
                       d.content AS content, d.embedding AS embedding,
                       d.para_category AS para_category, d.tags AS tags
                """
            ).data()

        if not rows:
            return []

        q = np.array(query_embedding, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))

        scored: list[tuple[float, dict]] = []
        for row in rows:
            emb = np.array(row["embedding"], dtype=np.float32)
            emb_norm = float(np.linalg.norm(emb))
            score = (
                float(np.dot(q, emb) / (q_norm * emb_norm))
                if q_norm > 0 and emb_norm > 0
                else 0.0
            )
            doc = {k: v for k, v in row.items() if k != "embedding"}
            scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"score": s, **doc} for s, doc in scored[:top_k]]

    def search_by_keyword(self, query: str, top_k: int = 5) -> list[dict]:
        """제목 또는 내용에서 키워드로 Document를 검색한다.

        Args:
            query: 검색 키워드
            top_k: 반환할 최대 문서 수
        Returns:
            매칭된 문서 dict 목록 (score=None)
        """
        with self._driver.session() as session:
            rows = session.run(
                """
                MATCH (d:Document)
                WHERE toLower(d.content) CONTAINS toLower($query)
                   OR toLower(d.title) CONTAINS toLower($query)
                RETURN d.id AS id, d.title AS title, d.path AS path,
                       d.content AS content,
                       d.para_category AS para_category, d.tags AS tags
                LIMIT $top_k
                """,
                query=query,
                top_k=top_k,
            ).data()
        return [{"score": None, **row} for row in rows]
