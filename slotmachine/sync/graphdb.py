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
        vault_path: Path | None = None,
        embedding: list[float] | None = None,
        para_category: str = "Inbox",
    ) -> str:
        """Document 노드를 생성 또는 업데이트하고 관련 엣지를 재연결한다.

        Args:
            vault_path: vault 루트 경로. 제공 시 vault 기준 상대 경로로 저장된다.
        Returns:
            생성·업데이트된 Document 노드의 id
        """
        # vault_path가 있으면 상대 경로(포직스 형식)로 변환
        if vault_path is not None:
            try:
                rel = doc.path.relative_to(vault_path)
                stored_path = rel.as_posix()
                folder_path = rel.parent.as_posix()
            except ValueError:
                stored_path = doc.path.as_posix()
                folder_path = doc.path.parent.as_posix()
        else:
            stored_path = str(doc.path)
            folder_path = str(doc.path.parent)

        node_id = doc_id(stored_path)

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
                path=stored_path,
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
                folder_path=folder_path,
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

    def delete_document(self, path: Path | str, *, vault_path: Path | None = None) -> bool:
        """Document 노드와 연결된 모든 엣지를 제거한다.

        Args:
            path: 삭제할 문서 경로 (절대 또는 상대)
            vault_path: vault 루트 경로. 제공 시 vault 기준 상대 경로로 ID를 계산한다.
        Returns:
            삭제된 노드가 있으면 True
        """
        if vault_path is not None:
            try:
                stored_path = Path(path).relative_to(vault_path).as_posix()
            except ValueError:
                stored_path = Path(path).as_posix()
        else:
            stored_path = str(path)
        node_id = doc_id(stored_path)
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
        para_filter: list[str] | None = None,
    ) -> list[dict]:
        """쿼리 임베딩과 코사인 유사도가 높은 Document를 반환한다.

        임베딩이 저장된 문서에 한해 Python-side 코사인 유사도를 계산한다.
        유사도 계산 시 content는 제외하고, 상위 top_k 문서에 대해서만 별도 조회한다.

        Args:
            query_embedding: 쿼리 임베딩 벡터
            top_k: 반환할 최대 문서 수
            para_filter: 검색할 PARA 카테고리 목록 (None이면 전체)
        Returns:
            score 내림차순으로 정렬된 문서 dict 목록 (embedding 필드 제외)
        """
        import numpy as np

        with self._driver.session() as session:
            if para_filter:
                rows = session.run(
                    """
                    MATCH (d:Document)
                    WHERE d.embedding IS NOT NULL
                      AND d.para_category IN $para_filter
                    RETURN d.id AS id, d.title AS title, d.path AS path,
                           d.embedding AS embedding,
                           d.para_category AS para_category, d.tags AS tags
                    """,
                    para_filter=para_filter,
                ).data()
            else:
                rows = session.run(
                    """
                    MATCH (d:Document)
                    WHERE d.embedding IS NOT NULL
                    RETURN d.id AS id, d.title AS title, d.path AS path,
                           d.embedding AS embedding,
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
        top = scored[:top_k]

        # 선별된 top_k 문서에 대해서만 content 조회
        top_paths = [doc["path"] for _, doc in top]
        contents = self.get_contents_by_paths(top_paths)
        return [
            {"score": s, **doc, "content": contents.get(doc["path"], "")}
            for s, doc in top
        ]

    def get_contents_by_paths(self, paths: list[str]) -> dict[str, str]:
        """경로 목록에 해당하는 문서의 content를 한 번에 조회한다.

        Args:
            paths: vault 기준 상대 경로 목록
        Returns:
            {path: content} 딕셔너리
        """
        if not paths:
            return {}
        with self._driver.session() as session:
            rows = session.run(
                """
                MATCH (d:Document)
                WHERE d.path IN $paths
                RETURN d.path AS path, d.content AS content
                """,
                paths=paths,
            ).data()
        return {row["path"]: row["content"] or "" for row in rows}

    def load_embeddings_cache(
        self, para_filter: list[str] | None = None
    ) -> list[dict]:
        """전체 문서 임베딩을 한 번에 로드한다 (relink 배치용).

        content를 제외하고 임베딩과 메타데이터만 반환한다.
        Archives는 항상 제외된다.

        Args:
            para_filter: 로드할 PARA 카테고리 목록 (None이면 Archives 외 전체)
        Returns:
            {"id", "title", "path", "para_category", "tags", "embedding"} 목록
        """
        categories = (
            [c for c in para_filter if c != "Archives"]
            if para_filter
            else None
        )
        with self._driver.session() as session:
            if categories:
                rows = session.run(
                    """
                    MATCH (d:Document)
                    WHERE d.embedding IS NOT NULL
                      AND d.para_category IN $categories
                    RETURN d.id AS id, d.title AS title, d.path AS path,
                           d.para_category AS para_category, d.tags AS tags,
                           d.embedding AS embedding
                    """,
                    categories=categories,
                ).data()
            else:
                rows = session.run(
                    """
                    MATCH (d:Document)
                    WHERE d.embedding IS NOT NULL
                      AND d.para_category <> 'Archives'
                    RETURN d.id AS id, d.title AS title, d.path AS path,
                           d.para_category AS para_category, d.tags AS tags,
                           d.embedding AS embedding
                    """
                ).data()
        return rows

    def get_graph_proximity_batch(
        self,
        src_path: str,
        cand_paths: list[str],
    ) -> dict[str, dict]:
        """src_path와 여러 후보 문서 간 근접성을 단일 쿼리로 계산한다.

        Args:
            src_path: 기준 문서 경로
            cand_paths: 비교할 후보 문서 경로 목록
        Returns:
            {cand_path: {"shared_tags": int, "shared_links": int}} 딕셔너리
        """
        if not cand_paths:
            return {}
        with self._driver.session() as session:
            rows = session.run(
                """
                MATCH (src:Document {path: $src})
                MATCH (cand:Document) WHERE cand.path IN $cands
                OPTIONAL MATCH (src)-[:TAGGED_WITH]->(t:Tag)<-[:TAGGED_WITH]-(cand)
                WITH src, cand, count(DISTINCT t) AS shared_tags
                OPTIONAL MATCH (src)-[:LINKS_TO]->(x:Document)<-[:LINKS_TO]-(cand)
                RETURN cand.path AS path,
                       shared_tags,
                       count(DISTINCT x) AS shared_links
                """,
                src=str(src_path),
                cands=cand_paths,
            ).data()
        return {
            row["path"]: {
                "shared_tags": row["shared_tags"] or 0,
                "shared_links": row["shared_links"] or 0,
            }
            for row in rows
        }

    # ------------------------------------------------------------------
    # Sync 메타데이터
    # ------------------------------------------------------------------

    def upsert_sync_meta(self, commit_hash: str) -> None:
        """마지막으로 GraphDB에 반영된 커밋 해시를 Neo4j에 기록한다.

        싱글턴 SyncMeta 노드에 MERGE하므로 항상 최신 값만 유지된다.

        Args:
            commit_hash: 반영 완료된 commit hash
        """
        with self._driver.session() as session:
            session.run(
                """
                MERGE (m:SyncMeta {id: 'singleton'})
                SET m.last_commit = $commit_hash,
                    m.synced_at   = datetime()
                """,
                commit_hash=commit_hash,
            )

    def get_sync_meta(self) -> dict | None:
        """Neo4j에 저장된 sync 메타데이터를 반환한다.

        Returns:
            {last_commit, synced_at, id} dict, 초기화 전이면 None
        """
        with self._driver.session() as session:
            result = session.run(
                "MATCH (m:SyncMeta {id: 'singleton'}) RETURN m"
            )
            record = result.single()
            return dict(record["m"]) if record else None

    # ------------------------------------------------------------------
    # Knowledge Graph (F4)
    # ------------------------------------------------------------------

    def get_graph_proximity(self, src_path: Path | str, cand_path: Path | str) -> dict:
        """두 문서 간 그래프 근접성 지표를 반환한다.

        공통 태그 수 + 공통 위키링크 대상 수를 계산한다.
        점수가 높을수록 두 문서는 그래프 상에서 가깝다.

        Args:
            src_path: 기준 문서 경로
            cand_path: 비교 대상 문서 경로
        Returns:
            {"shared_tags": int, "shared_links": int}
        """
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (src:Document {path: $src}), (cand:Document {path: $cand})
                OPTIONAL MATCH (src)-[:TAGGED_WITH]->(t:Tag)<-[:TAGGED_WITH]-(cand)
                WITH src, cand, count(DISTINCT t) AS shared_tags
                OPTIONAL MATCH (src)-[:LINKS_TO]->(x:Document)<-[:LINKS_TO]-(cand)
                RETURN shared_tags, count(DISTINCT x) AS shared_links
                """,
                src=str(src_path),
                cand=str(cand_path),
            ).single()
        if result is None:
            return {"shared_tags": 0, "shared_links": 0}
        return {
            "shared_tags": result["shared_tags"] or 0,
            "shared_links": result["shared_links"] or 0,
        }

    def get_linked_titles(self, path: Path | str) -> list[str]:
        """해당 문서에서 LINKS_TO 엣지로 연결된 문서 제목 목록을 반환한다.

        Args:
            path: 기준 문서 경로
        Returns:
            연결된 문서 제목 목록
        """
        with self._driver.session() as session:
            rows = session.run(
                """
                MATCH (d:Document {path: $path})-[:LINKS_TO]->(linked:Document)
                RETURN linked.title AS title
                """,
                path=str(path),
            ).data()
        return [row["title"] for row in rows]

    def update_links_evaluated_at(self, path: str) -> None:
        """문서의 links_evaluated_at 타임스탬프를 현재 시각으로 갱신한다.

        apply_links 실행 후 호출해 재판단 기준 시각을 기록한다.

        Args:
            path: vault 기준 문서 상대 경로
        """
        with self._driver.session() as session:
            session.run(
                "MATCH (d:Document {path: $path}) SET d.links_evaluated_at = datetime()",
                path=str(path),
            )

    def get_delta_documents(
        self, para_filter: list[str] | None = None
    ) -> list[dict]:
        """링크 재판단 대상 문서(피벗 후보)를 반환한다.

        links_evaluated_at이 없거나 updated_at보다 이전인 문서만 반환한다.
        Archives는 항상 제외된다.

        Args:
            para_filter: 반환할 PARA 카테고리 목록 (None이면 Archives 외 전체)
        Returns:
            {"title": str, "path": str} 목록
        """
        categories = (
            [c for c in para_filter if c != "Archives"]
            if para_filter
            else None
        )
        with self._driver.session() as session:
            if categories:
                rows = session.run(
                    """
                    MATCH (d:Document)
                    WHERE d.para_category IN $categories
                      AND (d.links_evaluated_at IS NULL
                           OR d.updated_at > d.links_evaluated_at)
                    RETURN d.title AS title, d.path AS path
                    """,
                    categories=categories,
                ).data()
            else:
                rows = session.run(
                    """
                    MATCH (d:Document)
                    WHERE d.para_category <> 'Archives'
                      AND (d.links_evaluated_at IS NULL
                           OR d.updated_at > d.links_evaluated_at)
                    RETURN d.title AS title, d.path AS path
                    """
                ).data()
        return rows

    def get_all_linkable_documents(
        self, para_filter: list[str] | None = None
    ) -> list[dict]:
        """Archives를 제외한 전체 문서를 반환한다 (Full relink용).

        Args:
            para_filter: 반환할 PARA 카테고리 목록 (None이면 Archives 외 전체)
        Returns:
            {"title": str, "path": str} 목록
        """
        categories = (
            [c for c in para_filter if c != "Archives"]
            if para_filter
            else None
        )
        with self._driver.session() as session:
            if categories:
                rows = session.run(
                    """
                    MATCH (d:Document)
                    WHERE d.para_category IN $categories
                    RETURN d.title AS title, d.path AS path
                    """,
                    categories=categories,
                ).data()
            else:
                rows = session.run(
                    """
                    MATCH (d:Document)
                    WHERE d.para_category <> 'Archives'
                    RETURN d.title AS title, d.path AS path
                    """
                ).data()
        return rows

    def upsert_related_edges(
        self,
        src_path: Path | str,
        related: list[tuple[str, float]],
    ) -> None:
        """RELATED_TO 엣지를 생성 또는 업데이트한다.

        Args:
            src_path: 기준 문서 경로
            related: [(cand_path, score), ...] 목록
        """
        with self._driver.session() as session:
            for cand_path, score in related:
                session.run(
                    """
                    MATCH (src:Document {path: $src}), (dst:Document {path: $dst})
                    MERGE (src)-[r:RELATED_TO]->(dst)
                    SET r.score = $score, r.updated_at = datetime()
                    """,
                    src=str(src_path),
                    dst=str(cand_path),
                    score=score,
                )

    def search_by_keyword(
        self,
        query: str,
        top_k: int = 5,
        para_filter: list[str] | None = None,
    ) -> list[dict]:
        """제목 또는 내용에서 키워드로 Document를 검색한다.

        Args:
            query: 검색 키워드
            top_k: 반환할 최대 문서 수
            para_filter: 검색할 PARA 카테고리 목록 (None이면 전체)
        Returns:
            매칭된 문서 dict 목록 (score=None)
        """
        with self._driver.session() as session:
            if para_filter:
                rows = session.run(
                    """
                    MATCH (d:Document)
                    WHERE (toLower(d.content) CONTAINS toLower($query)
                       OR toLower(d.title) CONTAINS toLower($query))
                      AND d.para_category IN $para_filter
                    RETURN d.id AS id, d.title AS title, d.path AS path,
                           d.content AS content,
                           d.para_category AS para_category, d.tags AS tags
                    LIMIT $top_k
                    """,
                    query=query,
                    top_k=top_k,
                    para_filter=para_filter,
                ).data()
            else:
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
