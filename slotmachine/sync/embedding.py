"""임베딩 생성 모듈 — 다중 프로바이더 추상화.

지원 프로바이더: Jina (httpx) / Voyage / OpenAI / Gemini / Ollama
모든 구현체는 BaseEmbeddingProvider를 상속하며 embed() 하나만 구현하면 된다.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from slotmachine.config import EmbeddingProvider, Settings

logger = logging.getLogger(__name__)

_MAX_EMBED_CHARS = 20_000  # 이 길이 초과 시 분할 대상으로 판단


# ---------------------------------------------------------------------------
# 인터페이스
# ---------------------------------------------------------------------------

class BaseEmbeddingProvider(ABC):
    """임베딩 프로바이더 공통 인터페이스."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 리스트를 임베딩 벡터 리스트로 변환한다.

        Args:
            texts: 임베딩할 텍스트 목록

        Returns:
            texts와 같은 순서의 임베딩 벡터 목록
        """

    def embed_one(self, text: str) -> list[float]:
        """단일 텍스트를 임베딩 벡터로 변환한다."""
        return self.embed([text])[0]


# ---------------------------------------------------------------------------
# Jina (httpx REST)
# ---------------------------------------------------------------------------

class JinaEmbeddingProvider(BaseEmbeddingProvider):
    _API_URL = "https://api.jina.ai/v1/embeddings"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = httpx.post(
            self._API_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "input": texts},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()["data"]
        # data는 index 기준 정렬이 보장되지 않을 수 있으므로 index로 정렬
        return [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]


# ---------------------------------------------------------------------------
# Voyage
# ---------------------------------------------------------------------------

class VoyageEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: str, model: str) -> None:
        import voyageai  # 런타임 임포트 — 미설치 시 에러 명확화
        self._client = voyageai.Client(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._client.embed(texts, model=self._model)
        return result.embeddings


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [e.embedding for e in response.data]


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: str, model: str) -> None:
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        from google.genai import types as genai_types
        result = self._client.models.embed_content(
            model=self._model,
            contents=texts,
            config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        return [e.values for e in result.embeddings]


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, base_url: str, model: str) -> None:
        import ollama
        self._client = ollama.Client(host=base_url)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embed(model=self._model, input=texts)
        return response.embeddings


# ---------------------------------------------------------------------------
# 팩토리
# ---------------------------------------------------------------------------

def embed_one_safe(
    provider: BaseEmbeddingProvider,
    content: str,
    path: Path | str | None = None,
) -> tuple[list[float] | None, bool]:
    """임베딩 생성 — 길이 초과 시 분할 대상으로 표시, 일시적 오류 시 재시도 후 None 폴백.

    - 길이가 _MAX_EMBED_CHARS 초과: (None, True) 반환 — 분할 대상
    - 일시적 오류 (네트워크, Rate Limit): 1회 재시도 후 (None, False) 반환 — embedding-less upsert

    Args:
        provider: 임베딩 프로바이더
        content: 임베딩할 텍스트
        path: 로그용 파일 경로 (옵션)

    Returns:
        (embedding, is_oversized) 튜플.
        is_oversized=True → 분할 대상, False → 성공 또는 일시적 실패
    """
    label = str(path) if path else "?"

    if len(content) > _MAX_EMBED_CHARS:
        logger.warning("문서 크기 초과 (분할 필요): %s (%d자)", label, len(content))
        return None, True

    for attempt in range(2):
        try:
            return provider.embed_one(content), False
        except Exception as exc:
            if attempt == 0:
                logger.warning("임베딩 실패 (재시도): %s — %s", label, exc)
            else:
                logger.warning("임베딩 실패 (embedding=None 폴백): %s — %s", label, exc)

    return None, False


def get_provider(settings: Settings) -> BaseEmbeddingProvider:
    """Settings에 따라 적절한 EmbeddingProvider 인스턴스를 반환한다."""
    provider = settings.embedding_provider
    model = settings.embedding_model

    if provider == EmbeddingProvider.JINA:
        return JinaEmbeddingProvider(api_key=settings.jina_api_key, model=model)
    if provider == EmbeddingProvider.VOYAGE:
        return VoyageEmbeddingProvider(api_key=settings.voyage_api_key, model=model)
    if provider == EmbeddingProvider.OPENAI:
        return OpenAIEmbeddingProvider(api_key=settings.openai_api_key, model=model)
    if provider == EmbeddingProvider.GEMINI:
        return GeminiEmbeddingProvider(api_key=settings.gemini_api_key, model=model)
    if provider == EmbeddingProvider.OLLAMA:
        return OllamaEmbeddingProvider(base_url=settings.ollama_base_url, model=model)

    raise ValueError(f"지원하지 않는 임베딩 프로바이더: {provider}")
