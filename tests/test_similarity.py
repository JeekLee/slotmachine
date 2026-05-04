"""classifier.similarity 단위 테스트."""
from __future__ import annotations

from unittest.mock import MagicMock

from slotmachine.classifier.similarity import (
    SimilarDocument,
    compute_category_hints,
    find_similar_for_inbox,
)


# ---------------------------------------------------------------------------
# fake embedding provider
# ---------------------------------------------------------------------------


class FakeEmbedder:
    """주어진 매핑 {텍스트 키워드: 벡터}로 임베딩을 결정적으로 만든다."""

    def __init__(self, mapping: dict[str, list[float]]):
        self._mapping = mapping

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(t) for t in texts]

    def embed_one(self, text: str) -> list[float]:
        for key, vec in self._mapping.items():
            if key in text:
                return vec
        return [0.0, 0.0, 0.0]


def _make_db(rows: list[dict]) -> MagicMock:
    """db.search_similar_by_embedding이 정해진 rows를 반환하는 mock."""
    db = MagicMock()
    db.search_similar_by_embedding.return_value = rows
    return db


# ---------------------------------------------------------------------------
# find_similar_for_inbox
# ---------------------------------------------------------------------------


class TestFindSimilarForInbox:
    def test_returns_top_k_by_score(self):
        """vector_search 결과를 그대로 받아 score 내림차순 top_k 반환."""
        provider = FakeEmbedder({"crypto": [1.0, 0.0, 0.0]})
        db = _make_db([
            {"path": "Projects/Rocky.md", "title": "Rocky",
             "para_category": "Projects", "tags": [], "score": 1.0},
            {"path": "Resources/Algo.md", "title": "Algo",
             "para_category": "Resources", "tags": [], "score": 0.95},
            {"path": "Resources/RustBook.md", "title": "RustBook",
             "para_category": "Resources", "tags": [], "score": 0.0},
        ])
        result = find_similar_for_inbox(
            "crypto trading idea", [], provider, db, top_k=2, threshold=0.1
        )
        assert len(result) == 2
        assert result[0].path == "Projects/Rocky.md"
        assert result[1].path == "Resources/Algo.md"
        assert result[0].score >= result[1].score
        # GraphDB가 호출된 인자 — top_k는 내부에서 *3으로 끌어온다
        assert db.search_similar_by_embedding.call_args.kwargs["top_k"] == 6

    def test_threshold_filters_low_scores(self):
        provider = FakeEmbedder({"x": [1.0, 0.0]})
        db = _make_db([
            {"path": "A.md", "title": "A",
             "para_category": "Resources", "tags": [], "score": 0.0},
        ])
        result = find_similar_for_inbox("x", [], provider, db, threshold=0.5)
        assert result == []

    def test_tag_overlap_boosts_score(self):
        """태그 교집합이 있으면 점수에 +0.05~0.20 보너스."""
        provider = FakeEmbedder({"x": [1.0, 0.0]})
        rows = [
            {"path": "A.md", "title": "A",
             "para_category": "Resources",
             "tags": ["python", "rust"], "score": 0.6},
        ]
        no_tag = find_similar_for_inbox("x", [], provider, _make_db(rows), threshold=0.0)
        with_tag = find_similar_for_inbox(
            "x", ["python", "rust"], provider, _make_db(rows), threshold=0.0
        )
        assert with_tag[0].score > no_tag[0].score
        # 태그 2개 → +0.10
        assert abs(with_tag[0].score - no_tag[0].score - 0.10) < 1e-3

    def test_tag_boost_capped(self):
        """태그 5개 이상이어도 보너스는 0.20에서 멈춘다."""
        provider = FakeEmbedder({"x": [1.0, 0.0]})
        many_tags = ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]
        db = _make_db([
            {"path": "A.md", "title": "A",
             "para_category": "Resources", "tags": many_tags, "score": 1.0},
        ])
        result = find_similar_for_inbox(
            "x", many_tags, provider, db, threshold=0.0
        )
        # vector_score=1.0 + boost(0.20 cap) → final=1.0 (min cap)
        assert result[0].score == 1.0
        assert result[0].vector_score == 1.0

    def test_empty_db_returns_empty(self):
        provider = FakeEmbedder({"x": [1.0]})
        assert find_similar_for_inbox("x", [], provider, _make_db([])) == []

    def test_no_provider_returns_empty(self):
        db = _make_db([{"path": "A.md", "score": 1.0}])
        assert find_similar_for_inbox("x", [], None, db) == []

    def test_no_db_returns_empty(self):
        provider = FakeEmbedder({"x": [1.0]})
        assert find_similar_for_inbox("x", [], provider, None) == []

    def test_empty_text_returns_empty(self):
        provider = FakeEmbedder({"x": [1.0]})
        db = _make_db([{"path": "A.md", "score": 1.0}])
        assert find_similar_for_inbox("   ", [], provider, db) == []

    def test_provider_failure_returns_empty(self):
        """embed_one_safe가 None을 반환하면(2회 재시도 모두 실패) 빈 리스트."""

        class FailingProvider:
            def embed_one(self, text):
                raise RuntimeError("network error")

            def embed(self, texts):
                raise RuntimeError("network error")

        db = _make_db([{"path": "A.md", "score": 1.0}])
        assert find_similar_for_inbox("x", [], FailingProvider(), db) == []

    def test_db_search_failure_returns_empty(self):
        """search_similar_by_embedding이 예외를 던지면 빈 리스트로 폴백."""
        provider = FakeEmbedder({"x": [1.0, 0.0]})
        db = MagicMock()
        db.search_similar_by_embedding.side_effect = RuntimeError("neo4j down")
        assert find_similar_for_inbox("x", [], provider, db) == []

    def test_filters_to_non_archive_categories(self):
        """검색 시 Archives 제외, Projects/Areas/Resources만 후보."""
        provider = FakeEmbedder({"x": [1.0]})
        db = _make_db([])
        find_similar_for_inbox("x", [], provider, db)
        kwargs = db.search_similar_by_embedding.call_args.kwargs
        assert set(kwargs["para_filter"]) == {"Projects", "Areas", "Resources"}


# ---------------------------------------------------------------------------
# compute_category_hints
# ---------------------------------------------------------------------------


class TestComputeCategoryHints:
    def test_single_category_normalized_to_one(self):
        sims = [
            SimilarDocument("A", "p1", "Resources", 0.8, 0.8),
            SimilarDocument("B", "p2", "Resources", 0.6, 0.6),
        ]
        hints = compute_category_hints(sims)
        assert hints == {"Resources": 1.0}

    def test_multiple_categories_share_distribution(self):
        sims = [
            SimilarDocument("A", "p1", "Projects", 0.8, 0.8),
            SimilarDocument("B", "p2", "Resources", 0.2, 0.2),
        ]
        hints = compute_category_hints(sims)
        assert hints["Projects"] == 0.8
        assert hints["Resources"] == 0.2
        assert abs(sum(hints.values()) - 1.0) < 1e-6

    def test_empty_returns_empty(self):
        assert compute_category_hints([]) == {}

    def test_zero_total_returns_empty(self):
        sims = [SimilarDocument("A", "p1", "Resources", 0.0, 0.0)]
        assert compute_category_hints(sims) == {}
