"""config.py 단위 테스트."""
import pytest
from pathlib import Path
from unittest.mock import patch

from slotmachine.config import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    Settings,
    _DEFAULT_MODELS,
)


@pytest.fixture
def vault_path(tmp_path: Path) -> Path:
    """임시 vault 디렉토리를 생성해 반환한다."""
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


def make_settings(vault_path: Path, **overrides) -> Settings:
    """테스트용 Settings 인스턴스를 생성한다.

    embedding_model을 ""로 초기화해 .env.local 고정값이 validator를 가리지 않도록 한다.
    """
    base = dict(
        neo4j_password="test_password",
        vault_path=vault_path,
        jina_api_key="test_jina_key",
        embedding_model="",
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[call-arg]


class TestEmbeddingProviderDefaults:
    def test_jina_default_model(self, vault_path: Path) -> None:
        s = make_settings(vault_path, embedding_provider="jina")
        assert s.embedding_model == "jina-embeddings-v3"

    def test_voyage_default_model(self, vault_path: Path) -> None:
        s = make_settings(vault_path, embedding_provider="voyage", voyage_api_key="k")
        assert s.embedding_model == "voyage-3"

    def test_openai_default_model(self, vault_path: Path) -> None:
        s = make_settings(vault_path, embedding_provider="openai", openai_api_key="k")
        assert s.embedding_model == "text-embedding-3-small"

    def test_gemini_default_model(self, vault_path: Path) -> None:
        s = make_settings(vault_path, embedding_provider="gemini", gemini_api_key="k")
        assert s.embedding_model == "text-embedding-004"

    def test_explicit_model_overrides_default(self, vault_path: Path) -> None:
        s = make_settings(
            vault_path,
            embedding_provider="voyage",
            voyage_api_key="k",
            embedding_model="voyage-3-lite",
        )
        assert s.embedding_model == "voyage-3-lite"


class TestApiKeyValidation:
    def test_missing_jina_key_raises(self, vault_path: Path) -> None:
        with pytest.raises(ValueError, match="JINA_API_KEY"):
            make_settings(vault_path, embedding_provider="jina", jina_api_key="")

    def test_missing_voyage_key_raises(self, vault_path: Path) -> None:
        with pytest.raises(ValueError, match="VOYAGE_API_KEY"):
            make_settings(vault_path, embedding_provider="voyage", voyage_api_key="")

    def test_ollama_does_not_require_api_key(self, vault_path: Path) -> None:
        s = make_settings(vault_path, embedding_provider="ollama", jina_api_key="")
        assert s.embedding_provider == EmbeddingProvider.OLLAMA


class TestVaultPathValidation:
    def test_nonexistent_vault_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="존재하지 않습니다"):
            make_settings(tmp_path / "no_such_dir")

    def test_file_as_vault_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "file.md"
        f.touch()
        with pytest.raises(ValueError, match="디렉토리여야"):
            make_settings(f)


class TestProperties:
    def test_inbox_path(self, vault_path: Path) -> None:
        s = make_settings(vault_path, inbox_folder="INBOX")
        assert s.inbox_path == vault_path / "INBOX"

    def test_embedding_dimension_known_model(self, vault_path: Path) -> None:
        s = make_settings(vault_path, embedding_model="jina-embeddings-v3")
        assert s.embedding_dimension == 1024

    def test_embedding_dimension_unknown_model_fallback(self, vault_path: Path) -> None:
        s = make_settings(vault_path, embedding_model="unknown-model-xyz")
        assert s.embedding_dimension == 1024  # 기본값
