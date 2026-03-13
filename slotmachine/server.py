"""MCP 서버 진입점 — SlotMachine.

fastmcp를 사용해 툴을 MCP 프로토콜로 노출한다.
슬래시 커맨드는 .claude/commands/*.md 에서 정의한다.

툴 (Claude가 자동 호출):
  - save_vault   : git add+commit+push 후 GraphDB 증분 업데이트
  - sync_vault   : git pull 후 GraphDB 증분 업데이트
  - config_vault : ~/.slotmachine/settings.env 설정 저장
  - init_vault   : Neo4j 스키마 초기화 + vault full sync
  - recall       : GraphDB 벡터/키워드 검색 → RAG 컨텍스트 반환
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastmcp import FastMCP

from slotmachine.config import HOME_CONFIG, Settings, get_settings, write_config
from slotmachine.sync.graphdb import GraphDB
from slotmachine.sync.pipelines import LiveSyncResult, SaveResult, live_sync, save
from slotmachine.sync.sync_history import SyncHistory

logger = logging.getLogger(__name__)

mcp = FastMCP("SlotMachine 🎰")


def _make_db(settings: Settings) -> GraphDB:
    return GraphDB(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)


def _make_embedding_provider(settings: Settings):
    """설정에서 임베딩 프로바이더를 생성한다. 실패 시 None 반환."""
    try:
        from slotmachine.sync.embedding import get_provider
        return get_provider(settings)
    except (ValueError, ImportError) as exc:
        logger.warning("임베딩 프로바이더 초기화 실패 — 임베딩 없이 진행: %s", exc)
        return None


def _make_history(settings: Settings) -> SyncHistory:
    db_path = settings.vault_path / ".slotmachine" / "sync_history.db"
    return SyncHistory(db_path)


@mcp.tool()
def save_vault(commit_message: str = "") -> dict:
    """Obsidian vault 변경사항을 저장하고 GraphDB를 업데이트한다.

    git add + commit + push to main 후 변경된 문서만 증분 동기화한다.

    Args:
        commit_message: 커밋 메시지 (빈 문자열이면 자동 생성)
    Returns:
        실행 결과 딕셔너리
    """
    settings = get_settings()
    db = _make_db(settings)
    embedding_provider = _make_embedding_provider(settings)
    history = _make_history(settings)

    result: SaveResult = save(
        settings.vault_path,
        db,
        embedding_provider=embedding_provider,
        commit_message=commit_message or None,
        sync_history=history,
    )
    return {
        "success": result.success,
        "commit_hash": result.commit_hash,
        "nothing_to_commit": result.nothing_to_commit,
        "added": result.sync_result.added,
        "modified": result.sync_result.modified,
        "deleted": result.sync_result.deleted,
        "failed": result.sync_result.failed,
        "error": result.error,
    }


@mcp.tool()
def sync_vault() -> dict:
    """원격 저장소의 변경사항을 로컬 GraphDB에 동기화한다.

    git pull origin main 후 변경된 문서만 증분 동기화한다.

    Returns:
        실행 결과 딕셔너리
    """
    settings = get_settings()
    db = _make_db(settings)
    embedding_provider = _make_embedding_provider(settings)
    history = _make_history(settings)

    result: LiveSyncResult = live_sync(
        settings.vault_path,
        db,
        embedding_provider=embedding_provider,
        sync_history=history,
    )
    return {
        "success": result.success,
        "previous_head": result.previous_head,
        "new_head": result.new_head,
        "nothing_to_sync": result.nothing_to_sync,
        "added": result.sync_result.added,
        "modified": result.sync_result.modified,
        "deleted": result.sync_result.deleted,
        "failed": result.sync_result.failed,
        "error": result.error,
    }


@mcp.tool()
def config_vault(
    vault_path: str,
    neo4j_password: str,
    git_repo_url: str = "",
    git_ssh_key_path: str = "",
    embedding_provider: str = "jina",
    jina_api_key: str = "",
    openai_api_key: str = "",
    voyage_api_key: str = "",
    gemini_api_key: str = "",
    ollama_base_url: str = "",
    neo4j_uri: str = "",
    neo4j_username: str = "",
    embedding_model: str = "",
) -> dict:
    """SlotMachine 설정을 저장한다.

    ~/.slotmachine/settings.env 에 설정을 기록한다.
    최초 1회 실행 후 MCP 서버를 재시작하면 설정이 적용된다.

    Args:
        vault_path: Obsidian vault 절대 경로 (필수)
        neo4j_password: Neo4j 비밀번호 (필수)
        git_repo_url: git remote URL (HTTPS 또는 SSH)
        git_ssh_key_path: SSH 개인키 경로 (SSH 인증 사용 시)
        embedding_provider: 임베딩 프로바이더 — jina/openai/voyage/gemini/ollama (기본: jina)
        jina_api_key: Jina AI API key
        openai_api_key: OpenAI API key
        voyage_api_key: Voyage AI API key
        gemini_api_key: Gemini API key
        ollama_base_url: Ollama 서버 URL (기본: http://localhost:11434)
        neo4j_uri: Neo4j URI (기본: bolt://localhost:7687)
        neo4j_username: Neo4j 사용자명 (기본: neo4j)
        embedding_model: 임베딩 모델명 (기본: 프로바이더 기본값)
    Returns:
        저장 결과 및 다음 단계 안내
    """
    # Neo4j 설정이 없으면 Docker 자동 관리 모드로 전환
    docker_mode = not neo4j_password and not neo4j_uri
    if docker_mode:
        neo4j_uri = "bolt://localhost:7687"
        neo4j_username = neo4j_username or "neo4j"
        neo4j_password = "slotmachine"
        neo4j_mode = "docker"
    else:
        neo4j_mode = "external"

    config_path = write_config({
        "VAULT_PATH": vault_path,
        "NEO4J_PASSWORD": neo4j_password,
        "NEO4J_MODE": neo4j_mode,
        "GIT_REPO_URL": git_repo_url,
        "GIT_SSH_KEY_PATH": git_ssh_key_path,
        "EMBEDDING_PROVIDER": embedding_provider,
        "JINA_API_KEY": jina_api_key,
        "OPENAI_API_KEY": openai_api_key,
        "VOYAGE_API_KEY": voyage_api_key,
        "GEMINI_API_KEY": gemini_api_key,
        "OLLAMA_BASE_URL": ollama_base_url,
        "NEO4J_URI": neo4j_uri,
        "NEO4J_USERNAME": neo4j_username,
        "EMBEDDING_MODEL": embedding_model,
    })

    neo4j_note = (
        "\nNeo4j 설정이 없어 Docker 자동 관리 모드로 설정되었습니다.\n"
        "MCP 서버 시작 시 Docker로 Neo4j가 자동 실행됩니다 (Docker 필요)."
        if docker_mode else ""
    )
    return {
        "success": True,
        "config_path": str(config_path),
        "neo4j_mode": neo4j_mode,
        "message": (
            f"설정이 저장되었습니다.{neo4j_note}\n"
            f"저장 경로: {config_path}\n"
            f"다음 단계: MCP 서버를 재시작한 뒤 init_vault를 실행하세요."
        ),
    }


@mcp.tool()
def init_vault() -> dict:
    """Neo4j 스키마를 초기화하고 vault 전체를 GraphDB에 적재한다.

    config_vault 실행 후 최초 1회 실행한다.
    이미 데이터가 있어도 upsert 방식이므로 안전하게 재실행할 수 있다.

    Returns:
        적재 결과 통계
    """
    settings = get_settings()
    db = _make_db(settings)
    embedding_provider = _make_embedding_provider(settings)

    db.init_schema()

    from slotmachine.sync.full_sync import full_sync
    result = full_sync(
        settings.vault_path,
        db,
        embedding_provider=embedding_provider,
        show_progress=False,
    )
    return {
        "success": result.failed == 0,
        "total": result.total,
        "success_count": result.success,
        "failed": result.failed,
        "vault_path": str(settings.vault_path),
        "embedding_enabled": embedding_provider is not None,
        "errors": [f"{p.name}: {msg}" for p, msg in result.errors[:5]],
    }


@mcp.tool()
def recall(query: str, top_k: int = 5) -> dict:
    """개인 지식베이스에서 쿼리와 관련된 문서를 검색해 컨텍스트를 반환한다.

    GraphDB에서 관련 문서를 검색하고 Claude Code가 답변 생성에 활용할 컨텍스트를 구성한다.
    이 툴은 Claude API를 직접 호출하지 않으며, 검색된 컨텍스트를 기반으로
    호스트 LLM(Claude Code)이 답변을 생성한다.

    Args:
        query: 검색할 질문 또는 키워드
        top_k: 검색할 최대 문서 수 (기본: 5)
    Returns:
        관련 문서 목록 및 Claude가 사용할 컨텍스트 텍스트
    """
    settings = get_settings()
    db = _make_db(settings)
    embedding_provider = _make_embedding_provider(settings)
    vault_name = settings.vault_path.name

    from slotmachine.rag.retriever import retrieve
    docs = retrieve(query, db, embedding_provider=embedding_provider, top_k=top_k)

    if not docs:
        return {
            "query": query,
            "found": 0,
            "documents": [],
            "context": "개인 지식베이스에서 관련 문서를 찾지 못했습니다.",
            "note": "vault에 문서가 없거나 init_vault가 실행되지 않았을 수 있습니다.",
        }

    documents = [
        {
            "rank": i + 1,
            "title": doc.title,
            "path": doc.path,
            "obsidian_uri": doc.obsidian_uri(vault_name),
            "score": round(doc.score, 4) if doc.score is not None else None,
            "para_category": doc.para_category,
            "tags": doc.tags,
            "excerpt": doc.excerpt,
        }
        for i, doc in enumerate(docs)
    ]

    # Claude Code가 답변 생성에 사용할 컨텍스트
    context_parts = [f"# 개인 지식베이스 검색 결과 — '{query}'\n"]
    for i, doc in enumerate(docs):
        score_str = f" (유사도: {doc.score:.3f})" if doc.score is not None else ""
        context_parts.append(
            f"## [{i + 1}] {doc.title}{score_str}\n"
            f"- 카테고리: {doc.para_category}\n\n"
            f"{doc.content}\n"
        )
    context_parts.append(
        "\n---\n📎 참조 문서:\n"
        + "\n".join(
            f"  - [[{doc.title}]] {doc.obsidian_uri(vault_name)}" for doc in docs
        )
    )

    return {
        "query": query,
        "found": len(docs),
        "documents": documents,
        "context": "\n".join(context_parts),
    }


def main() -> None:
    """MCP 서버를 시작한다."""
    logging.basicConfig(level=logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()
