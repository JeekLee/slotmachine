"""Knowledge Graph 링커 모듈 (F4).

대상 문서와 관련된 문서를 탐색하고 Obsidian 위키링크([[…]])를 삽입한다.

흐름
----
1. find_related()     : 벡터 유사도 + 그래프 근접성으로 관련 문서 후보 반환
2. insert_wiki_links(): 후보 중 승인된 링크를 문서 파일에 삽입
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from slotmachine.sync.graphdb import GraphDB

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# 상수
# ──────────────────────────────────────────

# 태그 하나당 점수 보정치 (최대 0.20까지 누적)
_TAG_BOOST_UNIT = 0.05
_TAG_BOOST_MAX = 0.20

# 공통 링크 하나당 점수 보정치 (최대 0.15까지 누적)
_LINK_BOOST_UNIT = 0.03
_LINK_BOOST_MAX = 0.15

# 링크 생태계에서 완전 격리되는 PARA 카테고리
_ISOLATED_CATEGORIES = {"Archives"}

# wikilink 파싱 패턴:  [[제목]]  또는  [[제목|표시텍스트]]
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# "Related" 섹션 헤딩 패턴 (한/영 통합)
_RELATED_HEADING_RE = re.compile(
    r"^##\s+(?:Related|관련|연관|See\s+Also|Links|링크)",
    re.IGNORECASE | re.MULTILINE,
)

# 다음 h2 헤딩 탐색 패턴
_NEXT_H2_RE = re.compile(r"^\s*##\s", re.MULTILINE)


# ──────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────


@dataclass
class LinkCandidate:
    """관련 문서 후보."""

    title: str
    path: str
    vector_score: float
    proximity_boost: float
    final_score: float
    para_category: str
    tags: list[str] = field(default_factory=list)
    excerpt: str = ""


# ──────────────────────────────────────────
# 핵심 로직
# ──────────────────────────────────────────


def find_related(
    target_path: str,
    db: GraphDB,
    *,
    embedding_provider=None,
    top_k: int = 10,
    threshold: float = 0.65,
    embeddings_cache: list[dict] | None = None,
) -> list[LinkCandidate]:
    """대상 문서와 관련된 문서 후보를 반환한다.

    벡터 유사도(임베딩 기반)에 그래프 근접성(공통 태그·링크)을 더해 순위를 매긴다.
    이미 위키링크로 연결된 문서와 자기 자신은 결과에서 제외된다.

    embeddings_cache가 제공되면 Neo4j 임베딩 풀스캔을 생략하고 캐시를 재사용한다.
    relink 배치 처리 시 활용해 Neo4j 쿼리 수를 대폭 줄인다.

    Args:
        target_path: vault 기준 대상 문서 상대 경로
        db: GraphDB 인스턴스
        embedding_provider: 임베딩 프로바이더 (None이면 키워드 검색 폴백)
        top_k: 반환할 최대 후보 수
        threshold: 최소 final_score 임계값 (0~1)
        embeddings_cache: 사전 로드된 임베딩 목록 (relink 배치용)
    Returns:
        final_score 내림차순 LinkCandidate 목록
    """
    import numpy as np

    # 1. 대상 문서 조회
    if embeddings_cache is not None:
        doc_data = next(
            (d for d in embeddings_cache if d["path"] == target_path), None
        )
    else:
        doc_data = db.get_document(target_path)

    if doc_data is None:
        logger.warning("GraphDB에서 문서를 찾을 수 없음: %s", target_path)
        return []

    target_title = doc_data.get("title", "")
    already_linked = set(db.get_linked_titles(target_path))
    already_linked.add(target_title)

    # 2. 유사 문서 후보 수집 (top_k의 3배 풀)
    raw: list[dict] = []
    embedding = doc_data.get("embedding")

    if embeddings_cache is not None and embedding:
        # 캐시 직접 사용 — Neo4j 풀스캔 없음
        q = np.array(embedding, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))
        scored: list[tuple[float, dict]] = []
        for row in embeddings_cache:
            if row["path"] == target_path:
                continue
            emb = row.get("embedding")
            if not emb:
                continue
            e = np.array(emb, dtype=np.float32)
            e_norm = float(np.linalg.norm(e))
            score = (
                float(np.dot(q, e) / (q_norm * e_norm))
                if q_norm > 0 and e_norm > 0
                else 0.0
            )
            scored.append((score, {k: v for k, v in row.items() if k != "embedding"}))
        scored.sort(key=lambda x: x[0], reverse=True)
        raw = [{"score": s, **doc} for s, doc in scored[: top_k * 3]]
    elif embedding:
        if embedding_provider and not embedding:
            content = doc_data.get("content", "")
            if content:
                embedding = embedding_provider.embed_one(content)
        raw = db.search_similar_by_embedding(embedding, top_k=top_k * 3)
    else:
        query_terms = " ".join([target_title] + list(doc_data.get("tags") or []))
        raw = db.search_by_keyword(query_terms, top_k=top_k * 3)

    # 3. 기본 필터링 (자기 자신 / 이미 연결됨 / 격리 카테고리)
    filtered = [
        row for row in raw
        if row.get("title") not in already_linked
        and row.get("path") != target_path
        and row.get("para_category") not in _ISOLATED_CATEGORIES
    ]
    if not filtered:
        return []

    # 4. 그래프 근접성 보정 — 배치 단일 쿼리
    cand_paths = [row["path"] for row in filtered]
    proximity_map = db.get_graph_proximity_batch(target_path, cand_paths)

    candidates: list[LinkCandidate] = []
    for row in filtered:
        cand_path = row["path"]
        vector_score = float(row.get("score") or 0.0)
        prox = proximity_map.get(str(cand_path), {"shared_tags": 0, "shared_links": 0})
        boost = min(prox["shared_tags"] * _TAG_BOOST_UNIT, _TAG_BOOST_MAX) + min(
            prox["shared_links"] * _LINK_BOOST_UNIT, _LINK_BOOST_MAX
        )
        final_score = min(vector_score + boost, 1.0)

        if final_score < threshold:
            continue

        content = row.get("content", "")
        candidates.append(
            LinkCandidate(
                title=row.get("title", ""),
                path=cand_path,
                vector_score=vector_score,
                proximity_boost=round(boost, 4),
                final_score=round(final_score, 4),
                para_category=row.get("para_category", "Inbox"),
                tags=list(row.get("tags") or []),
                excerpt=content[:300].strip(),
            )
        )

    candidates.sort(key=lambda c: c.final_score, reverse=True)
    top_candidates = candidates[:top_k]

    # 5. 캐시 모드에서 excerpt가 없으면 content 별도 조회
    if embeddings_cache is not None:
        paths_needing_content = [
            c.path for c in top_candidates if not c.excerpt
        ]
        if paths_needing_content:
            contents = db.get_contents_by_paths(paths_needing_content)
            for c in top_candidates:
                if not c.excerpt and c.path in contents:
                    c.excerpt = contents[c.path][:300].strip()

    return top_candidates


# ──────────────────────────────────────────
# 위키링크 파싱
# ──────────────────────────────────────────


def get_wikilinks_from_content(content: str) -> set[str]:
    """마크다운 본문에서 모든 위키링크 제목을 추출한다.

    [[제목]] 또는 [[제목|표시텍스트]] 형식을 모두 처리한다.

    Args:
        content: 마크다운 전체 내용
    Returns:
        링크 제목 집합
    """
    return {m.group(1).strip() for m in _WIKILINK_RE.finditer(content)}


# ──────────────────────────────────────────
# 위키링크 삽입
# ──────────────────────────────────────────


def insert_wiki_links(
    vault_path: Path,
    rel_path: str,
    link_titles: list[str],
) -> str:
    """승인된 위키링크를 문서에 삽입하고 수정된 내용을 반환한다.

    기존 위키링크 중복은 자동으로 제외한다.
    문서에 '## Related' (또는 관련/연관/Links) 섹션이 있으면 해당 섹션 끝에 추가하고,
    없으면 파일 끝에 새 섹션을 만든다.

    Args:
        vault_path: vault 루트 절대 경로
        rel_path: vault 기준 대상 문서 상대 경로
        link_titles: 삽입할 위키링크 제목 목록 (승인된 것만)
    Returns:
        수정된 파일 전체 내용. 변경 없으면 원본 내용 반환.
    """
    file_path = vault_path / rel_path
    content = file_path.read_text(encoding="utf-8")

    # 이미 존재하는 링크 제외
    existing = get_wikilinks_from_content(content)
    new_titles = [t for t in link_titles if t not in existing]
    if not new_titles:
        logger.debug("삽입할 새 링크 없음: %s", rel_path)
        return content

    link_lines = "\n".join(f"- [[{t}]]" for t in new_titles)

    # Related 섹션 탐색
    match = _RELATED_HEADING_RE.search(content)
    if match:
        # 섹션 끝(다음 h2 또는 EOF) 바로 앞에 삽입
        after_heading = content[match.end():]
        next_h2 = _NEXT_H2_RE.search(after_heading)
        if next_h2:
            insert_pos = match.end() + next_h2.start()
            new_content = (
                content[:insert_pos].rstrip()
                + "\n"
                + link_lines
                + "\n\n"
                + content[insert_pos:]
            )
        else:
            new_content = content.rstrip() + "\n" + link_lines + "\n"
    else:
        # Related 섹션이 없으면 파일 끝에 새로 추가
        new_content = content.rstrip() + "\n\n## Related\n\n" + link_lines + "\n"

    file_path.write_text(new_content, encoding="utf-8")
    logger.info("위키링크 %d개 삽입: %s", len(new_titles), rel_path)
    return new_content


# ──────────────────────────────────────────
# Vault-wide 위키링크 정리 (F2-09, F3-10)
# ──────────────────────────────────────────

# 리스트 아이템 형태의 위키링크 한 줄 전체를 매칭: "- [[title]]" 또는 "  - [[title|alias]]"
_LIST_LINK_RE_TEMPLATE = r"^[ \t]*-[ \t]*\[\[{title}(?:\|[^\]]+)?\]\][ \t]*\n?"


def remove_wikilinks_in_vault(vault_path: Path, title: str) -> list[str]:
    """vault 전체 .md 파일에서 [[title]] 위키링크를 제거한다.

    리스트 아이템(`- [[title]]`) 형태의 줄 전체를 제거한다.
    인라인 참조는 건드리지 않는다.

    Args:
        vault_path: vault 루트 절대 경로
        title: 제거할 위키링크 제목
    Returns:
        수정된 파일의 vault 기준 상대 경로 목록
    """
    line_re = re.compile(
        _LIST_LINK_RE_TEMPLATE.format(title=re.escape(title)),
        re.MULTILINE,
    )
    modified: list[str] = []
    for md_file in vault_path.rglob("*.md"):
        if any(part.startswith(".") for part in md_file.parts):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            if f"[[{title}]]" not in content and f"[[{title}|" not in content:
                continue
            new_content = line_re.sub("", content)
            if new_content != content:
                md_file.write_text(new_content, encoding="utf-8")
                modified.append(str(md_file.relative_to(vault_path)))
        except Exception as exc:
            logger.warning("위키링크 제거 실패 — %s: %s", md_file.name, exc)
    if modified:
        logger.info("[[%s]] 제거 완료: %d개 파일", title, len(modified))
    return modified


def replace_wikilinks_in_vault(
    vault_path: Path, old_title: str, new_title: str
) -> list[str]:
    """vault 전체 .md 파일에서 [[old_title]] → [[new_title]]로 교체한다.

    [[old_title|alias]] 형태도 [[new_title|alias]]로 교체된다.

    Args:
        vault_path: vault 루트 절대 경로
        old_title: 교체할 기존 위키링크 제목
        new_title: 교체할 새 위키링크 제목
    Returns:
        수정된 파일의 vault 기준 상대 경로 목록
    """
    pattern = re.compile(r"\[\[" + re.escape(old_title) + r"(\|[^\]]+)?\]\]")
    modified: list[str] = []
    for md_file in vault_path.rglob("*.md"):
        if any(part.startswith(".") for part in md_file.parts):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            if f"[[{old_title}]]" not in content and f"[[{old_title}|" not in content:
                continue
            new_content = pattern.sub(
                lambda m: f"[[{new_title}{m.group(1) or ''}]]", content
            )
            if new_content != content:
                md_file.write_text(new_content, encoding="utf-8")
                modified.append(str(md_file.relative_to(vault_path)))
        except Exception as exc:
            logger.warning("위키링크 교체 실패 — %s: %s", md_file.name, exc)
    if modified:
        logger.info("[[%s]] → [[%s]] 교체 완료: %d개 파일", old_title, new_title, len(modified))
    return modified
