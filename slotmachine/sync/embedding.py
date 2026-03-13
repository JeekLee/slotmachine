"""임베딩 생성 모듈 — 다중 프로바이더 추상화.

지원 프로바이더: Jina (httpx) / Voyage / OpenAI / Gemini / Ollama
모든 구현체는 BaseEmbeddingProvider를 상속하며 embed() 하나만 구현하면 된다.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from slotmachine.config import EmbeddingProvider, Settings

logger = logging.getLogger(__name__)


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
