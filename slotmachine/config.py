"""SlotMachine 설정 모듈.

pydantic-settings를 사용해 설정을 로드한다.
로드 우선순위 (낮음 → 높음):
  1. ~/.slotmachine/settings.env  — 사용자 전역 설정 (config_vault로 작성)
  2. .env.local                   — 프로젝트 로컬 오버라이드
  3. 환경 변수                     — 최우선
"""
from enum import StrEnum
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 사용자 홈 설정 파일 경로 (config_vault 툴이 여기에 저장)
HOME_CONFIG: Path = Path.home() / ".slotmachine" / "settings.env"


class EmbeddingProvider(StrEnum):
    JINA = "jina"
    VOYAGE = "voyage"
    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class Environment(StrEnum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# 프로바이더별 기본 모델명
_DEFAULT_MODELS: dict[EmbeddingProvider, str] = {
    EmbeddingProvider.JINA: "jina-embeddings-v3",
    EmbeddingProvider.VOYAGE: "voyage-3",
    EmbeddingProvider.OPENAI: "text-embedding-3-small",
    EmbeddingProvider.GEMINI: "text-embedding-004",
    EmbeddingProvider.OLLAMA: "nomic-embed-text",
}

# 프로바이더별 임베딩 벡터 차원
EMBEDDING_DIMENSIONS: dict[str, int] = {
    "jina-embeddings-v3": 1024,
    "voyage-3": 1024,
    "voyage-3-lite": 512,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-004": 768,
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
}


class Settings(BaseSettings):
    """SlotMachine 전체 설정."""

    model_config = SettingsConfigDict(
        env_file=[str(HOME_CONFIG), ".env.local"],  # HOME_CONFIG → .env.local 순서로 로드 (나중이 우선)
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Neo4j ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str

    # --- 임베딩 프로바이더 ---
    embedding_provider: EmbeddingProvider = EmbeddingProvider.JINA
    embedding_model: str = ""  # 빈 문자열이면 프로바이더 기본값 사용

    # 프로바이더별 API Key (사용하는 프로바이더만 설정)
    jina_api_key: str = ""
    voyage_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # --- Obsidian Vault ---
    vault_path: Path
    inbox_folder: str = "INBOX"

    # --- Git ---
    git_repo_url: str = ""
    git_ssh_key_path: Path | None = None

    # --- Webhook 서버 ---
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8000
    webhook_secret: str = ""

    # --- 환경 / 로깅 ---
    env: Environment = Environment.LOCAL
    log_level: LogLevel = LogLevel.INFO

    @field_validator("vault_path")
    @classmethod
    def vault_must_exist(cls, v: Path) -> Path:
        """vault_path가 실제 존재하는 디렉토리인지 검증한다."""
        if not v.exists():
            raise ValueError(f"VAULT_PATH가 존재하지 않습니다: {v}")
        if not v.is_dir():
            raise ValueError(f"VAULT_PATH는 디렉토리여야 합니다: {v}")
        return v

    @model_validator(mode="after")
    def resolve_embedding_model(self) -> "Settings":
        """embedding_model이 비어 있으면 프로바이더 기본값으로 채운다."""
        if not self.embedding_model:
            self.embedding_model = _DEFAULT_MODELS[self.embedding_provider]
        return self

    @model_validator(mode="after")
    def validate_api_key(self) -> "Settings":
        """선택된 프로바이더에 필요한 API Key가 설정되어 있는지 검증한다."""
        required: dict[EmbeddingProvider, tuple[str, str]] = {
            EmbeddingProvider.JINA: (self.jina_api_key, "JINA_API_KEY"),
            EmbeddingProvider.VOYAGE: (self.voyage_api_key, "VOYAGE_API_KEY"),
            EmbeddingProvider.OPENAI: (self.openai_api_key, "OPENAI_API_KEY"),
            EmbeddingProvider.GEMINI: (self.gemini_api_key, "GEMINI_API_KEY"),
        }
        if self.embedding_provider in required:
            value, var_name = required[self.embedding_provider]
            if not value:
                raise ValueError(
                    f"EMBEDDING_PROVIDER={self.embedding_provider} 사용 시 "
                    f"{var_name}를 .env.local에 설정해야 합니다."
                )
        return self

    @property
    def inbox_path(self) -> Path:
        """INBOX 폴더의 절대 경로를 반환한다."""
        return self.vault_path / self.inbox_folder

    @property
    def embedding_dimension(self) -> int:
        """현재 설정된 임베딩 모델의 벡터 차원을 반환한다.

        알 수 없는 모델이면 1024를 기본값으로 반환한다.
        """
        return EMBEDDING_DIMENSIONS.get(self.embedding_model, 1024)


def get_settings() -> Settings:
    """Settings 인스턴스를 반환한다.

    실제 사용 시 이 함수를 통해 설정을 주입받는다.
    """
    return Settings()  # type: ignore[call-arg]


def write_config(values: dict[str, str], config_path: Path | None = None) -> Path:
    """설정값을 env 파일에 저장한다.

    기존 파일이 있으면 키를 업데이트하고, 없으면 새로 생성한다.
    values 중 빈 문자열인 항목은 기존 값을 유지한다 (덮어쓰지 않음).

    Args:
        values: 저장할 KEY=VALUE 쌍. 빈 값("")은 기존 값 유지.
        config_path: 저장할 파일 경로 (None이면 HOME_CONFIG 사용)
    Returns:
        실제 저장된 파일 경로
    """
    target = config_path or HOME_CONFIG
    target.parent.mkdir(parents=True, exist_ok=True)

    # 기존 파일 파싱
    existing: dict[str, str] = {}
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()

    # 빈 값은 무시하고 나머지만 업데이트
    existing.update({k: v for k, v in values.items() if v})

    target.write_text(
        "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n",
        encoding="utf-8",
    )
    return target
