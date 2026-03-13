"""임베딩 프로바이더 단위 테스트."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slotmachine.sync.embedding import (
    BaseEmbeddingProvider,
    GeminiEmbeddingProvider,
    JinaEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
    VoyageEmbeddingProvider,
    get_provider,
)


DUMMY_VECTORS = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


# ---------------------------------------------------------------------------
# BaseEmbeddingProvider.embed_one
# ---------------------------------------------------------------------------

def test_embed_one_returns_single_vector():
    class _Stub(BaseEmbeddingProvider):
        def embed(self, texts):
            return [[float(i) for i in range(3)] for _ in texts]

    stub = _Stub()
    result = stub.embed_one("hello")
    assert isinstance(result, list)
    assert len(result) == 3


# ---------------------------------------------------------------------------
# JinaEmbeddingProvider
# ---------------------------------------------------------------------------

def test_jina_embed_returns_vectors():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"index": 0, "embedding": [0.1, 0.2]},
            {"index": 1, "embedding": [0.3, 0.4]},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("slotmachine.sync.embedding.httpx.post", return_value=mock_response):
        provider = JinaEmbeddingProvider(api_key="key", model="jina-embeddings-v3")
        result = provider.embed(["text1", "text2"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_jina_embed_sorts_by_index():
    """응답의 data 순서가 뒤섞여도 index 기준으로 정렬돼야 한다."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"index": 1, "embedding": [0.3, 0.4]},
            {"index": 0, "embedding": [0.1, 0.2]},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("slotmachine.sync.embedding.httpx.post", return_value=mock_response):
        provider = JinaEmbeddingProvider(api_key="key", model="jina-embeddings-v3")
        result = provider.embed(["t1", "t2"])

    assert result[0] == [0.1, 0.2]
    assert result[1] == [0.3, 0.4]


def test_jina_sends_correct_headers_and_body():
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"index": 0, "embedding": [0.1]}]}
    mock_response.raise_for_status = MagicMock()

    with patch("slotmachine.sync.embedding.httpx.post", return_value=mock_response) as mock_post:
        provider = JinaEmbeddingProvider(api_key="mykey", model="jina-embeddings-v3")
        provider.embed(["hello"])

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer mykey"
    assert kwargs["json"]["model"] == "jina-embeddings-v3"
    assert kwargs["json"]["input"] == ["hello"]


# ---------------------------------------------------------------------------
# VoyageEmbeddingProvider
# ---------------------------------------------------------------------------

def test_voyage_embed():
    mock_client = MagicMock()
    mock_client.embed.return_value.embeddings = DUMMY_VECTORS

    mock_voyageai = MagicMock()
    mock_voyageai.Client.return_value = mock_client

    with patch.dict("sys.modules", {"voyageai": mock_voyageai}):
        provider = VoyageEmbeddingProvider(api_key="key", model="voyage-3")
        result = provider.embed(["a", "b"])

    assert result == DUMMY_VECTORS
    mock_client.embed.assert_called_once_with(["a", "b"], model="voyage-3")


# ---------------------------------------------------------------------------
# OpenAIEmbeddingProvider
# ---------------------------------------------------------------------------

def test_openai_embed():
    mock_e0 = MagicMock()
    mock_e0.embedding = [0.1, 0.2]
    mock_e1 = MagicMock()
    mock_e1.embedding = [0.3, 0.4]

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value.data = [mock_e0, mock_e1]

    with patch("openai.OpenAI", return_value=mock_client):
        provider = OpenAIEmbeddingProvider(api_key="key", model="text-embedding-3-small")
        result = provider.embed(["a", "b"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    mock_client.embeddings.create.assert_called_once_with(
        input=["a", "b"], model="text-embedding-3-small"
    )


# ---------------------------------------------------------------------------
# GeminiEmbeddingProvider
# ---------------------------------------------------------------------------

def test_gemini_embed():
    mock_emb_0 = MagicMock()
    mock_emb_0.values = [0.1, 0.2]
    mock_emb_1 = MagicMock()
    mock_emb_1.values = [0.3, 0.4]

    mock_client = MagicMock()
    mock_client.models.embed_content.return_value.embeddings = [mock_emb_0, mock_emb_1]

    mock_genai_types = MagicMock()

    with patch("google.genai.Client", return_value=mock_client), \
         patch("google.genai.types", mock_genai_types):
        provider = GeminiEmbeddingProvider(api_key="key", model="text-embedding-004")
        result = provider.embed(["a", "b"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


# ---------------------------------------------------------------------------
# OllamaEmbeddingProvider
# ---------------------------------------------------------------------------

def test_ollama_embed():
    mock_client = MagicMock()
    mock_client.embed.return_value.embeddings = DUMMY_VECTORS

    with patch("ollama.Client", return_value=mock_client):
        provider = OllamaEmbeddingProvider(
            base_url="http://localhost:11434", model="nomic-embed-text"
        )
        result = provider.embed(["a", "b"])

    assert result == DUMMY_VECTORS
    mock_client.embed.assert_called_once_with(
        model="nomic-embed-text", input=["a", "b"]
    )


# ---------------------------------------------------------------------------
# get_provider 팩토리
# ---------------------------------------------------------------------------

def _make_settings(provider: str, vault_path: Path) -> MagicMock:
    from slotmachine.config import EmbeddingProvider
    s = MagicMock()
    s.embedding_provider = EmbeddingProvider(provider)
    s.embedding_model = "test-model"
    s.jina_api_key = "jina-key"
    s.voyage_api_key = "voyage-key"
    s.openai_api_key = "openai-key"
    s.gemini_api_key = "gemini-key"
    s.ollama_base_url = "http://localhost:11434"
    return s


@pytest.fixture
def vault(tmp_path):
    return tmp_path


def test_get_provider_jina(vault):
    with patch("slotmachine.sync.embedding.JinaEmbeddingProvider") as mock_cls:
        get_provider(_make_settings("jina", vault))
    mock_cls.assert_called_once_with(api_key="jina-key", model="test-model")


def test_get_provider_voyage(vault):
    mock_voyageai = MagicMock()
    with patch.dict("sys.modules", {"voyageai": mock_voyageai}), \
         patch("slotmachine.sync.embedding.VoyageEmbeddingProvider") as mock_cls:
        get_provider(_make_settings("voyage", vault))
    mock_cls.assert_called_once_with(api_key="voyage-key", model="test-model")


def test_get_provider_openai(vault):
    with patch("openai.OpenAI"), \
         patch("slotmachine.sync.embedding.OpenAIEmbeddingProvider") as mock_cls:
        get_provider(_make_settings("openai", vault))
    mock_cls.assert_called_once_with(api_key="openai-key", model="test-model")


def test_get_provider_ollama(vault):
    with patch("ollama.Client"), \
         patch("slotmachine.sync.embedding.OllamaEmbeddingProvider") as mock_cls:
        get_provider(_make_settings("ollama", vault))
    mock_cls.assert_called_once_with(
        base_url="http://localhost:11434", model="test-model"
    )
