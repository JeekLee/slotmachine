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
    threshold: float = 0.5,
) -> list[LinkCandidate]:
    """대상 문서와 관련된 문서 후보를 반환한다.

    벡터 유사도(임베딩 기반)에 그래프 근접성(공통 태그·링크)을 더해 순위를 매긴다.
    이미 위키링크로 연결된 문서와 자기 자신은 결과에서 제외된다.

    Args:
        target_path: vault 기준 대상 문서 상대 경로
        db: GraphDB 인스턴스
        embedding_provider: 임베딩 프로바이더 (None이면 키워드 검색 폴백)
        top_k: 반환할 최대 후보 수
        threshold: 최소 final_score 임계값 (0~1)
    Returns:
        final_score 내림차순 LinkCandidate 목록
    """
    # 1. 대상 문서 조회
    doc_data = db.get_document(target_path)
    if doc_data is None:
        logger.warning("GraphDB에서 문서를 찾을 수 없음: %s", target_path)
        return []

    target_title = doc_data.get("title", "")
    already_linked = set(db.get_linked_titles(target_path))
    already_linked.add(target_title)  # 자기 자신도 제외

    # 2. 유사 문서 후보 수집 (top_k의 3배 풀에서 필터링)
    raw: list[dict] = []
    embedding = doc_data.get("embedding")

    if embedding_provider and not embedding:
        # DB에 임베딩이 없으면 현재 내용으로 생성
        content = doc_data.get("content", "")
        if content:
            embedding = embedding_provider.embed_one(content)

    if embedding:
        raw = db.search_similar_by_embedding(embedding, top_k=top_k * 3)
    else:
        # 임베딩 없음 → 키워드 폴백 (제목 + 태그 조합)
        query_terms = " ".join([target_title] + list(doc_data.get("tags") or []))
        raw = db.search_by_keyword(query_terms, top_k=top_k * 3)

    # 3. 필터링 + 그래프 근접성 보정
    candidates: list[LinkCandidate] = []
    for row in raw:
        cand_title = row.get("title", "")
        cand_path = row.get("path", "")

        if cand_title in already_linked:
            continue
        if cand_path == target_path:
            continue

        vector_score = float(row.get("score") or 0.0)
        proximity = db.get_graph_proximity(target_path, cand_path)
        boost = min(proximity["shared_tags"] * _TAG_BOOST_UNIT, _TAG_BOOST_MAX) + min(
            proximity["shared_links"] * _LINK_BOOST_UNIT, _LINK_BOOST_MAX
        )
        final_score = min(vector_score + boost, 1.0)

        if final_score < threshold:
            continue

        content = row.get("content", "")
        candidates.append(
            LinkCandidate(
                title=cand_title,
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
    return candidates[:top_k]


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
