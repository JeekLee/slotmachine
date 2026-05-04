"""INBOX 분류 보조 — 기존 vault 문서와의 유사도 매칭.

INBOX 문서를 임베딩하고 GraphDB의 벡터 인덱스로 top-k 후보를 추출한다.
태그 교집합 보너스를 더해 최종 점수를 산출하고, 카테고리별 가중 점수 분포로
Claude Code의 분류 판단에 힌트를 제공한다.

INBOX 문서는 GraphDB에 저장되지 않으므로 그래프 근접성(공통 링크 등)은
사용하지 않는다 — 순수 벡터 + 태그 기반.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# 태그 하나당 점수 보정치 (최대 0.20까지 누적) — linker.py와 동일 정책
_TAG_BOOST_UNIT = 0.05
_TAG_BOOST_MAX = 0.20

# Archives는 항상 분류 후보에서 제외 (linker._ISOLATED_CATEGORIES와 정합).
# Areas는 INBOX 분류 시점엔 의미있는 후보가 될 수 있으므로 포함한다.
_DEFAULT_CANDIDATE_CATEGORIES = ["Projects", "Areas", "Resources"]


@dataclass
class SimilarDocument:
    """INBOX 문서와 유사한 기존 vault 문서."""

    title: str
    path: str
    para_category: str
    score: float          # 최종 점수 (vector + tag boost)
    vector_score: float   # 코사인 유사도 원점수
    tags: list[str] = field(default_factory=list)


def find_similar_for_inbox(
    inbox_text: str,
    inbox_tags: list[str],
    embedding_provider,
    db,
    *,
    top_k: int = 3,
    threshold: float = 0.5,
) -> list[SimilarDocument]:
    """INBOX 문서와 유사한 기존 vault 문서 top-k를 반환한다.

    Neo4j 벡터 인덱스로 후보 풀(top_k * 3)을 받고, Python에서 태그 교집합
    보너스를 더해 최종 score 기준 top-k로 추린다. 인덱스 미존재 시
    db.search_similar_by_embedding이 자동으로 풀스캔 폴백한다.

    Args:
        inbox_text: INBOX 문서의 임베딩 입력 텍스트 (보통 raw_content)
        inbox_tags: INBOX 문서의 태그 목록
        embedding_provider: 임베딩 프로바이더 (None이면 빈 결과)
        db: GraphDB 인스턴스 (None이면 빈 결과)
        top_k: 반환할 최대 후보 수
        threshold: 최소 final_score 임계값
    Returns:
        score 내림차순 SimilarDocument 목록. 임베딩/검색 실패 시 빈 리스트.
    """
    if embedding_provider is None or db is None or not inbox_text.strip():
        return []

    from slotmachine.sync.embedding import embed_one_safe

    embedding, _oversized = embed_one_safe(embedding_provider, inbox_text)
    if embedding is None:
        return []

    try:
        rows = db.search_similar_by_embedding(
            embedding,
            top_k=top_k * 3,
            para_filter=_DEFAULT_CANDIDATE_CATEGORIES,
        )
    except Exception as exc:
        logger.warning("유사도 검색 실패: %s", exc)
        return []

    inbox_tag_set = {t.lower() for t in inbox_tags or []}
    candidates: list[SimilarDocument] = []
    for row in rows:
        vector_score = float(row.get("score") or 0.0)
        tags = list(row.get("tags") or [])
        shared = sum(1 for t in tags if t.lower() in inbox_tag_set)
        boost = min(shared * _TAG_BOOST_UNIT, _TAG_BOOST_MAX)
        final = min(vector_score + boost, 1.0)
        if final < threshold:
            continue
        candidates.append(
            SimilarDocument(
                title=row.get("title") or Path(row.get("path", "")).stem,
                path=row.get("path", ""),
                para_category=row.get("para_category", "Inbox"),
                score=round(final, 4),
                vector_score=round(vector_score, 4),
                tags=tags,
            )
        )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:top_k]


def compute_category_hints(similar: list[SimilarDocument]) -> dict[str, float]:
    """top-k 후보의 점수를 카테고리별로 합산해 정규화한 분포를 반환한다.

    Args:
        similar: SimilarDocument 목록 (보통 find_similar_for_inbox 결과)
    Returns:
        {카테고리: 정규화 점수(0~1)} 딕셔너리. similar가 비어있으면 빈 dict.
    """
    if not similar:
        return {}
    raw: dict[str, float] = {}
    for s in similar:
        cat = s.para_category or "Inbox"
        raw[cat] = raw.get(cat, 0.0) + s.score
    total = sum(raw.values())
    if total <= 0:
        return {}
    return {cat: round(score / total, 4) for cat, score in raw.items()}
