"""classifier.similarity 단위 테스트."""
from __future__ import annotations

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


# ---------------------------------------------------------------------------
# find_similar_for_inbox
# ---------------------------------------------------------------------------


class TestFindSimilarForInbox:
    def test_returns_top_k_by_cosine(self):
        """벡터 유사도 내림차순으로 top_k 반환."""
        provider = FakeEmbedder({"crypto": [1.0, 0.0, 0.0]})
        cache = [
            {
                "path": "Resources/RustBook.md",
                "title": "RustBook",
                "para_category": "Resources",
                "tags": [],
                "embedding": [0.0, 1.0, 0.0],  # 직교 → score 0
            },
            {
                "path": "Projects/Rocky.md",
                "title": "Rocky",
                "para_category": "Projects",
                "tags": [],
                "embedding": [1.0, 0.0, 0.0],  # 동일 방향 → score 1
            },
            {
                "path": "Resources/Algo.md",
                "title": "Algo",
                "para_category": "Resources",
                "tags": [],
                "embedding": [0.9, 0.1, 0.0],  # 거의 동일
            },
        ]
        result = find_similar_for_inbox(
            "crypto trading idea", [], provider, cache, top_k=2, threshold=0.1
        )
        assert len(result) == 2
        # 가장 유사한 Rocky가 1위
        assert result[0].path == "Projects/Rocky.md"
        assert result[1].path == "Resources/Algo.md"
        assert result[0].score >= result[1].score

    def test_threshold_filters_low_scores(self):
        provider = FakeEmbedder({"x": [1.0, 0.0]})
        cache = [
            {
                "path": "A.md",
                "title": "A",
                "para_category": "Resources",
                "tags": [],
                "embedding": [0.0, 1.0],  # 직교 (score=0)
            },
        ]
        result = find_similar_for_inbox("x", [], provider, cache, threshold=0.5)
        assert result == []

    def test_tag_overlap_boosts_score(self):
        """태그 교집합이 있으면 점수에 +0.05~0.20 보너스."""
        provider = FakeEmbedder({"x": [1.0, 0.0]})
        cache = [
            {
                "path": "A.md",
                "title": "A",
                "para_category": "Resources",
                "tags": ["python", "rust"],
                "embedding": [0.6, 0.8],  # 코사인 ~0.6
            },
        ]
        no_tag = find_similar_for_inbox("x", [], provider, cache, threshold=0.0)
        with_tag = find_similar_for_inbox(
            "x", ["python", "rust"], provider, cache, threshold=0.0
        )
        assert with_tag[0].score > no_tag[0].score
        # 태그 2개 → +0.10
        assert abs(with_tag[0].score - no_tag[0].score - 0.10) < 1e-3

    def test_tag_boost_capped(self):
        """태그 5개 이상이어도 보너스는 0.20에서 멈춘다."""
        provider = FakeEmbedder({"x": [1.0, 0.0]})
        many_tags = ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]
        cache = [
            {
                "path": "A.md",
                "title": "A",
                "para_category": "Resources",
                "tags": many_tags,
                "embedding": [1.0, 0.0],  # score=1
            },
        ]
        result = find_similar_for_inbox(
            "x", many_tags, provider, cache, threshold=0.0
        )
        # vector_score=1.0 + boost(0.20 cap) → final=1.0 (min cap)
        assert result[0].score == 1.0
        assert result[0].vector_score == 1.0

    def test_empty_cache_returns_empty(self):
        provider = FakeEmbedder({"x": [1.0]})
        assert find_similar_for_inbox("x", [], provider, []) == []

    def test_no_provider_returns_empty(self):
        cache = [{"path": "A.md", "embedding": [1.0]}]
        assert find_similar_for_inbox("x", [], None, cache) == []

    def test_empty_text_returns_empty(self):
        provider = FakeEmbedder({"x": [1.0]})
        cache = [{"path": "A.md", "embedding": [1.0]}]
        assert find_similar_for_inbox("   ", [], provider, cache) == []

    def test_skips_rows_without_embedding(self):
        provider = FakeEmbedder({"x": [1.0, 0.0]})
        cache = [
            {
                "path": "A.md",
                "title": "A",
                "para_category": "Resources",
                "tags": [],
                "embedding": None,
            },
            {
                "path": "B.md",
                "title": "B",
                "para_category": "Projects",
                "tags": [],
                "embedding": [1.0, 0.0],
            },
        ]
        result = find_similar_for_inbox("x", [], provider, cache, threshold=0.0)
        assert len(result) == 1
        assert result[0].path == "B.md"

    def test_provider_failure_returns_empty(self):
        """embed_one_safe가 None을 반환하면(2회 재시도 모두 실패) 빈 리스트."""

        class FailingProvider:
            def embed_one(self, text):
                raise RuntimeError("network error")

            def embed(self, texts):
                raise RuntimeError("network error")

        cache = [{"path": "A.md", "embedding": [1.0]}]
        assert find_similar_for_inbox("x", [], FailingProvider(), cache) == []

    def test_zero_vector_yields_zero_score(self):
        """0 벡터는 nan 대신 0.0 처리."""
        provider = FakeEmbedder({"x": [0.0, 0.0]})
        cache = [
            {
                "path": "A.md",
                "title": "A",
                "para_category": "Resources",
                "tags": [],
                "embedding": [1.0, 0.0],
            },
        ]
        result = find_similar_for_inbox("x", [], provider, cache, threshold=-1.0)
        assert result[0].vector_score == 0.0


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
