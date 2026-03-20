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

    result: SaveResult = save(
        settings.vault_path,
        db,
        embedding_provider=embedding_provider,
        commit_message=commit_message or None,
        para_folder_map=settings.para_folder_map,
        inbox_folder=settings.inbox_folder,
    )
    return {
        "success": result.success,
        "commit_hash": result.commit_hash,
        "nothing_to_commit": result.nothing_to_commit,
        "added": result.sync_result.added,
        "modified": result.sync_result.modified,
        "deleted": result.sync_result.deleted,
        "failed": result.sync_result.failed,
        "oversized_docs": result.sync_result.oversized_docs,
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

    result: LiveSyncResult = live_sync(
        settings.vault_path,
        db,
        embedding_provider=embedding_provider,
        para_folder_map=settings.para_folder_map,
        inbox_folder=settings.inbox_folder,
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
        "oversized_docs": result.sync_result.oversized_docs,
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
    inbox_folder: str = "",
    para_projects: str = "",
    para_areas: str = "",
    para_resources: str = "",
    para_archives: str = "",
    template_inbox: str = "",
    template_projects: str = "",
    template_areas: str = "",
    template_resources: str = "",
    template_archives: str = "",
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
        inbox_folder: INBOX 폴더명 (기본: INBOX)
        para_projects: Projects 폴더명 (기본: Projects)
        para_areas: Areas 폴더명 (기본: Areas)
        para_resources: Resources 폴더명 (기본: Resources)
        para_archives: Archives 폴더명 (기본: Archives)
        template_inbox: Inbox 템플릿 상대경로 (생략 가능)
        template_projects: Projects 템플릿 상대경로 (생략 가능)
        template_areas: Areas 템플릿 상대경로 (생략 가능)
        template_resources: Resources 템플릿 상대경로 (생략 가능)
        template_archives: Archives 템플릿 상대경로 (생략 가능)
    Returns:
        저장 결과 및 다음 단계 안내
    """
    config_path = write_config({
        "VAULT_PATH": vault_path,
        "NEO4J_PASSWORD": neo4j_password,
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
        "INBOX_FOLDER": inbox_folder,
        "PARA_PROJECTS": para_projects,
        "PARA_AREAS": para_areas,
        "PARA_RESOURCES": para_resources,
        "PARA_ARCHIVES": para_archives,
        "TEMPLATE_INBOX": template_inbox,
        "TEMPLATE_PROJECTS": template_projects,
        "TEMPLATE_AREAS": template_areas,
        "TEMPLATE_RESOURCES": template_resources,
        "TEMPLATE_ARCHIVES": template_archives,
    })

    return {
        "success": True,
        "config_path": str(config_path),
        "message": (
            f"설정이 저장되었습니다.\n"
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
        para_folder_map=settings.para_folder_map,
        inbox_folder=settings.inbox_folder,
        show_progress=False,
    )
    return {
        "success": result.failed == 0,
        "total": result.total,
        "success_count": result.success,
        "failed": result.failed,
        "oversized_docs": result.oversized_docs,
        "vault_path": str(settings.vault_path),
        "embedding_enabled": embedding_provider is not None,
        "errors": [f"{p.name}: {msg}" for p, msg in result.errors[:5]],
    }


@mcp.tool()
def recall(
    query: str,
    top_k: int = 5,
    para_filter: list[str] | None = None,
) -> dict:
    """개인 지식베이스에서 쿼리와 관련된 문서를 검색해 컨텍스트를 반환한다.

    GraphDB에서 관련 문서를 검색하고 Claude Code가 답변 생성에 활용할 컨텍스트를 구성한다.
    이 툴은 Claude API를 직접 호출하지 않으며, 검색된 컨텍스트를 기반으로
    호스트 LLM(Claude Code)이 답변을 생성한다.

    Args:
        query: 검색할 질문 또는 키워드
        top_k: 검색할 최대 문서 수 (기본: 5)
        para_filter: 검색 범위를 제한할 PARA 카테고리 목록
                     예: ["Projects", "Areas"] — None이면 전체 카테고리 검색
    Returns:
        관련 문서 목록 및 Claude가 사용할 컨텍스트 텍스트
    """
    settings = get_settings()
    db = _make_db(settings)
    embedding_provider = _make_embedding_provider(settings)
    vault_name = settings.vault_path.name

    from slotmachine.rag.retriever import retrieve
    docs = retrieve(
        query,
        db,
        embedding_provider=embedding_provider,
        top_k=top_k,
        para_filter=para_filter,
    )

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


@mcp.tool()
def classify_inbox() -> dict:
    """INBOX 폴더의 문서를 로드해 분류에 필요한 정보를 반환한다.

    분류 판단은 호스트 LLM(Claude Code)이 excerpt 기반으로 수행한다.
    full_content와 templates는 이 툴에서 반환하지 않는다.
    - 문서 전체 내용: get_document_contents() 로 별도 요청
    - 카테고리 템플릿: get_templates() 로 별도 요청

    Returns:
        inbox_path, 문서 목록(path/title/tags/excerpt), vault_structure, 총 문서 수
    """
    settings = get_settings()

    from slotmachine.classifier.para import load_inbox, get_vault_structure
    docs = load_inbox(settings.inbox_path, settings.vault_path)

    # vault 하위 디렉토리 구조 + 기존 문서 목록
    vault_structure = get_vault_structure(settings.vault_path, settings.para_folder_map)

    return {
        "inbox_path": str(settings.inbox_path),
        "count": len(docs),
        "documents": [
            {
                "path": doc.path,
                "title": doc.title,
                "tags": doc.tags,
                "excerpt": doc.excerpt,
                "oversized": doc.oversized,
            }
            for doc in docs
        ],
        "oversized_count": sum(1 for doc in docs if doc.oversized),
        "vault_structure": vault_structure,
    }


@mcp.tool()
def get_document_contents(paths: list[str]) -> dict:
    """지정한 문서들의 전체 내용을 반환한다.

    분류 승인 후 재작성 단계에서 필요한 문서만 선택적으로 로드한다.
    배치 단위(예: 5개씩)로 호출해 컨텍스트 토큰을 분산할 수 있다.

    Args:
        paths: vault 기준 상대경로 목록 (예: ["INBOX/문서A.md", "INBOX/문서B.md"])
    Returns:
        {path: full_content} 딕셔너리 및 로드 성공/실패 수
    """
    settings = get_settings()

    from slotmachine.classifier.para import load_document_contents
    contents = load_document_contents(settings.vault_path, paths)

    return {
        "loaded": len(contents),
        "failed": len(paths) - len(contents),
        "contents": contents,
    }


@mcp.tool()
def get_templates(categories: list[str]) -> dict:
    """지정한 카테고리의 템플릿 내용을 반환한다.

    분류 승인 후 실제 사용된 카테고리의 템플릿만 선택적으로 로드한다.

    Args:
        categories: 템플릿이 필요한 카테고리 목록 (예: ["Projects", "Resources"])
    Returns:
        {category: template_content} 딕셔너리. 템플릿이 없는 카테고리는 포함되지 않는다.
    """
    settings = get_settings()

    from slotmachine.classifier.para import load_template
    templates = {}
    for category in categories:
        tmpl_rel = settings.template_map.get(category, "")
        if tmpl_rel:
            content = load_template(settings.vault_path, tmpl_rel)
            if content:
                templates[category] = content

    return {
        "templates": templates,
        "loaded": len(templates),
        "missing": [c for c in categories if c not in templates],
    }


@mcp.tool()
def apply_classification(
    classifications: list[dict],
    commit_message: str = "",
) -> dict:
    """승인된 PARA 분류 결과에 따라 파일을 이동하고 git commit한다.

    Args:
        classifications: 이동할 문서 목록
            각 항목: {
                "path": "00_Inbox/파일명.md",       (필수)
                "category": "Projects",              (필수)
                "target_folder": "20_Projects/CryptoLab/Rocky",  (선택 — 생략 시 category 폴더)
                "content": "재작성된 전체 문서 내용"  (선택 — 생략 시 원본 유지)
                "new_filename": "새파일명.md"        (선택 — 생략 시 원본 파일명 유지)
            }
            category 값: Projects / Areas / Resources / Archives / Inbox
            (Inbox는 이동하지 않고 건너뜀)
        commit_message: 커밋 메시지 (생략 시 자동 생성)
    Returns:
        이동된 수, 건너뛴 수, 커밋 해시, 오류 목록
    """
    settings = get_settings()

    from slotmachine.classifier.para import apply_classification as _apply
    from slotmachine.sync.git_manager import GitManager

    result = _apply(
        settings.vault_path,
        classifications,
        para_folder_map=settings.para_folder_map,
    )

    if result.moved == 0:
        return {
            "success": True,
            "moved": 0,
            "skipped": result.skipped,
            "commit_hash": "",
            "errors": result.errors,
            "message": "이동할 파일이 없습니다.",
        }

    try:
        gm = GitManager(settings.vault_path)
        staged = gm.add_all()
        msg = commit_message or (
            f"chore: PARA classify {result.moved} inbox items [SlotMachine]"
        )
        commit_hash = gm.commit(msg)
    except Exception as exc:
        return {
            "success": False,
            "moved": result.moved,
            "skipped": result.skipped,
            "commit_hash": "",
            "errors": result.errors + [f"git 오류: {exc}"],
        }

    return {
        "success": True,
        "moved": result.moved,
        "skipped": result.skipped,
        "commit_hash": commit_hash[:8],
        "errors": result.errors,
    }


@mcp.tool()
def apply_split(
    original_path: str,
    split_docs: list[dict],
    commit_message: str = "",
) -> dict:
    """사용자가 승인한 문서 분할 결과를 vault에 적용한다.

    맥락 기반 분할은 호스트 LLM(Claude Code)이 수행하며,
    이 툴은 분할 파일 생성 → 원본 삭제 → GraphDB 업데이트 → git commit을 담당한다.

    Inbox 문서의 경우 GraphDB 업데이트는 생략된다 (Inbox는 GraphDB 적재 제외).
    분할된 Inbox 문서는 이후 classify_inbox / apply_classification으로 분류한다.

    Args:
        original_path: vault 기준 원본 파일 상대경로
                       예: "00_Inbox/긴문서.md" 또는 "Resources/긴참고자료.md"
        split_docs: 분할 문서 목록
                    [{"filename": "분할_파트1.md", "content": "전체 마크다운 내용"}, ...]
        commit_message: 커밋 메시지 (생략 시 자동 생성)
    Returns:
        생성된 파일 목록, 삭제된 원본, 커밋 해시, 오류 목록
    """
    settings = get_settings()
    db = _make_db(settings)
    embedding_provider = _make_embedding_provider(settings)

    from slotmachine.classifier.splitter import apply_split as _apply_split
    from slotmachine.sync.git_manager import GitManager

    result = _apply_split(
        settings.vault_path,
        original_path,
        split_docs,
        db,
        embedding_provider=embedding_provider,
        para_folder_map=settings.para_folder_map,
        inbox_folder=settings.inbox_folder,
    )
    db.close()

    if not result.created:
        return {
            "success": False,
            "created": [],
            "deleted": "",
            "commit_hash": "",
            "errors": result.errors,
            "message": "생성된 분할 파일이 없습니다.",
        }

    try:
        gm = GitManager(settings.vault_path)
        gm.add_all()
        original_stem = original_path.split("/")[-1].replace(".md", "")
        msg = commit_message or (
            f"refactor: split '{original_stem}' into {len(result.created)} docs [SlotMachine]"
        )
        commit_hash = gm.commit(msg)
    except Exception as exc:
        return {
            "success": result.success,
            "created": result.created,
            "deleted": result.deleted,
            "commit_hash": "",
            "errors": result.errors + [f"git 오류: {exc}"],
        }

    return {
        "success": result.success,
        "created": result.created,
        "deleted": result.deleted,
        "commit_hash": commit_hash[:8],
        "errors": result.errors,
    }


@mcp.tool()
def suggest_links(
    path: str,
    top_k: int = 10,
    threshold: float = 0.65,
) -> dict:
    """대상 문서와 관련된 문서를 탐색하고 위키링크 후보를 반환한다.

    벡터 유사도(임베딩 기반)에 그래프 근접성(공통 태그·링크)을 더해 순위를 결정한다.
    이미 위키링크로 연결된 문서와 자기 자신은 결과에서 제외된다.
    탐색된 관련 문서는 GraphDB에 RELATED_TO 엣지로 기록된다.

    Args:
        path: vault 기준 대상 문서 상대 경로 (예: "Projects/my_project.md")
        top_k: 반환할 최대 후보 수 (기본: 10)
        threshold: 최소 관련도 점수 (0~1, 기본: 0.5)
    Returns:
        후보 문서 목록 및 총 수
    """
    settings = get_settings()
    db = _make_db(settings)
    embedding_provider = _make_embedding_provider(settings)

    from slotmachine.linker.linker import find_related

    candidates = find_related(
        path,
        db,
        embedding_provider=embedding_provider,
        top_k=top_k,
        threshold=threshold,
    )

    # GraphDB에 RELATED_TO 엣지 기록
    if candidates:
        db.upsert_related_edges(path, [(c.path, c.final_score) for c in candidates])

    db.close()

    return {
        "target_path": path,
        "found": len(candidates),
        "threshold": threshold,
        "candidates": [
            {
                "title": c.title,
                "path": c.path,
                "final_score": c.final_score,
                "vector_score": c.vector_score,
                "proximity_boost": c.proximity_boost,
                "para_category": c.para_category,
                "tags": c.tags,
                "excerpt": c.excerpt,
            }
            for c in candidates
        ],
        "note": (
            "candidates 목록을 사용자에게 보여주고 승인을 받은 뒤 "
            "apply_links 툴로 파일에 삽입하세요."
        ),
    }


@mcp.tool()
def apply_links(
    path: str,
    link_titles: list[str],
    commit_message: str = "",
) -> dict:
    """승인된 위키링크를 문서에 삽입하고 git commit한다.

    문서에 '## Related' 섹션이 있으면 해당 섹션 끝에 추가하고,
    없으면 파일 끝에 새 '## Related' 섹션을 만들어 삽입한다.
    이미 존재하는 위키링크는 자동으로 중복 제외된다.

    Args:
        path: vault 기준 대상 문서 상대 경로 (예: "Projects/my_project.md")
        link_titles: 삽입할 위키링크 제목 목록 (suggest_links 결과에서 선택)
        commit_message: 커밋 메시지 (생략 시 자동 생성)
    Returns:
        삽입된 링크 수, 커밋 해시, 오류 정보
    """
    settings = get_settings()

    from slotmachine.linker.linker import get_wikilinks_from_content, insert_wiki_links
    from slotmachine.sync.git_manager import GitManager

    file_path = settings.vault_path / path
    try:
        original_content = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "success": False,
            "inserted": 0,
            "commit_hash": "",
            "error": f"파일 없음: {path}",
        }

    before_links = get_wikilinks_from_content(original_content)

    try:
        new_content = insert_wiki_links(settings.vault_path, path, link_titles)
    except Exception as exc:
        return {
            "success": False,
            "inserted": 0,
            "commit_hash": "",
            "error": str(exc),
        }

    after_links = get_wikilinks_from_content(new_content)
    inserted_count = len(after_links - before_links)

    if inserted_count == 0:
        return {
            "success": True,
            "inserted": 0,
            "commit_hash": "",
            "message": "삽입할 새 링크가 없습니다 (모두 이미 존재하는 링크입니다).",
        }

    try:
        gm = GitManager(settings.vault_path)
        gm.add_all()
        msg = commit_message or (
            f"chore: add {inserted_count} wiki links to {Path(path).stem} [SlotMachine]"
        )
        commit_hash = gm.commit(msg)
    except Exception as exc:
        return {
            "success": False,
            "inserted": inserted_count,
            "commit_hash": "",
            "error": f"git 오류: {exc}",
        }

    # links_evaluated_at 갱신 (F4-08-01)
    try:
        db = _make_db(settings)
        db.update_links_evaluated_at(path)
        db.close()
    except Exception:
        pass  # timestamp 갱신 실패는 치명적 오류가 아니므로 무시

    return {
        "success": True,
        "inserted": inserted_count,
        "commit_hash": commit_hash[:8],
        "path": path,
    }


@mcp.tool()
def relink(
    mode: str = "delta",
    para_filter: list[str] | None = None,
) -> dict:
    """링크 재판단을 실행한다.

    신규/변경 문서를 피벗으로 관련 문서를 탐색하고 위키링크 후보를 반환한다.
    Archives 카테고리는 피벗 및 후보에서 자동 제외된다.
    임베딩은 GraphDB에 저장된 벡터를 재사용하므로 임베딩 API 호출이 없다.

    Args:
        mode: "delta" — links_evaluated_at 기준 변경 문서만 (기본)
              "all"   — Archives 제외 전체 vault
        para_filter: 피벗 범위를 제한할 PARA 카테고리 목록
                     예: ["Projects", "Resources"] — None이면 Archives 외 전체
    Returns:
        피벗 문서별 링크 후보 목록. 각 항목을 apply_links로 삽입한다.
    """
    settings = get_settings()
    db = _make_db(settings)
    embedding_provider = _make_embedding_provider(settings)

    from slotmachine.linker.linker import find_related

    if mode == "all":
        pivot_docs = db.get_all_linkable_documents(para_filter)
    else:
        pivot_docs = db.get_delta_documents(para_filter)

    if not pivot_docs:
        db.close()
        return {
            "mode": mode,
            "pivots_found": 0,
            "results": [],
            "note": "재판단 대상 문서가 없습니다. vault가 최신 상태입니다.",
        }

    results = []
    for doc in pivot_docs:
        candidates = find_related(
            doc["path"],
            db,
            embedding_provider=embedding_provider,
        )
        if candidates:
            results.append({
                "pivot_path": doc["path"],
                "pivot_title": doc["title"],
                "candidates": [
                    {
                        "title": c.title,
                        "path": c.path,
                        "final_score": c.final_score,
                        "para_category": c.para_category,
                        "excerpt": c.excerpt,
                    }
                    for c in candidates
                ],
            })

    db.close()

    return {
        "mode": mode,
        "pivots_found": len(pivot_docs),
        "pivots_with_candidates": len(results),
        "results": results,
        "note": (
            "각 pivot_path에 대해 apply_links 툴로 원하는 링크를 삽입하세요. "
            "apply_links 실행 후 links_evaluated_at이 자동 갱신됩니다."
        ),
    }


@mcp.tool()
def status_check() -> dict:
    """SlotMachine 전체 컴포넌트 상태를 점검한다.

    점검 항목:
      - MCP 서버: 이 툴이 실행되면 정상
      - 설정 파일: ~/.slotmachine/settings.env 존재 여부 및 주요 설정값
      - Vault: 경로 존재 여부, 마크다운 파일 수
      - Neo4j: 연결 가능 여부 및 노드 수
      - Git: 원격 URL 설정 여부
      - 임베딩: 프로바이더 및 API Key 설정 여부

    Returns:
        각 컴포넌트의 상태 딕셔너리
    """
    import shutil
    from datetime import datetime, timezone

    results: dict = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "mcp_server": {"ok": True, "message": "MCP 서버 실행 중"},
        "config": {},
        "vault": {},
        "neo4j": {},
        "git": {},
        "embedding": {},
    }

    # --- 설정 파일 ---
    config_exists = HOME_CONFIG.exists()
    if not config_exists:
        results["config"] = {
            "ok": False,
            "message": f"설정 파일 없음: {HOME_CONFIG}",
            "hint": "/slotmachine:config 를 실행하세요",
        }
        # 설정 없으면 이후 항목 점검 불가
        for key in ("vault", "neo4j", "git", "embedding"):
            results[key] = {"ok": False, "message": "설정 파일이 없어 점검 불가"}
        return results

    results["config"] = {"ok": True, "path": str(HOME_CONFIG)}

    # --- Settings 로드 ---
    try:
        settings = get_settings()
        settings_ok = True
    except Exception as exc:
        settings_ok = False
        settings_load_error = str(exc)

    if not settings_ok:
        results["config"]["ok"] = False
        results["config"]["message"] = f"설정 로드 실패: {settings_load_error}"
        for key in ("vault", "neo4j", "git", "embedding"):
            results[key] = {"ok": False, "message": "설정 로드 실패로 점검 불가"}
        return results

    # --- Vault ---
    vault_path = settings.vault_path
    vault_exists = vault_path.exists() and vault_path.is_dir()
    if vault_exists:
        md_count = sum(1 for _ in vault_path.rglob("*.md"))
        inbox_count = sum(1 for _ in settings.inbox_path.rglob("*.md")) if settings.inbox_path.exists() else 0
        results["vault"] = {
            "ok": True,
            "path": str(vault_path),
            "markdown_files": md_count,
            "inbox_files": inbox_count,
        }
    else:
        results["vault"] = {
            "ok": False,
            "message": f"Vault 경로 없음: {vault_path}",
        }

    # --- Neo4j ---
    try:
        db = _make_db(settings)
        db.verify_connectivity()
        # 노드 수 조회
        with db._driver.session() as session:
            doc_count = session.run("MATCH (d:Document) RETURN count(d) AS n").single()["n"]
        db.close()
        results["neo4j"] = {
            "ok": True,
            "uri": settings.neo4j_uri,
            "document_nodes": doc_count,
        }
    except Exception as exc:
        results["neo4j"] = {
            "ok": False,
            "uri": settings.neo4j_uri,
            "message": str(exc),
            "hint": "Neo4j 서버가 실행 중인지 확인하세요.",
        }

    # --- Git ---
    git_url = settings.git_repo_url
    if git_url:
        git_status: dict = {"ok": True, "remote_url": git_url}
        try:
            import git as gitlib
            repo = gitlib.Repo(settings.vault_path)
            git_status["branch"] = repo.active_branch.name
            git_status["dirty"] = repo.is_dirty(untracked_files=True)
        except Exception as exc:
            git_status["warning"] = str(exc)
        results["git"] = git_status
    else:
        results["git"] = {
            "ok": False,
            "message": "git_repo_url 미설정 — save/sync 시 원격 push/pull 불가",
            "hint": "/slotmachine:config 로 git_repo_url을 설정하세요",
        }

    # --- 임베딩 ---
    provider = settings.embedding_provider
    api_key_map = {
        "jina": settings.jina_api_key,
        "openai": settings.openai_api_key,
        "voyage": settings.voyage_api_key,
        "gemini": settings.gemini_api_key,
        "ollama": None,  # API Key 불필요
    }
    api_key = api_key_map.get(str(provider))
    key_ok = api_key is None or bool(api_key)  # ollama는 항상 True
    results["embedding"] = {
        "ok": key_ok,
        "provider": str(provider),
        "model": settings.embedding_model,
        "api_key_set": "설정됨" if key_ok else "미설정",
    }
    if not key_ok:
        results["embedding"]["hint"] = f"{str(provider).upper()}_API_KEY 를 설정하세요"

    return results


def main() -> None:
    """MCP 서버를 시작한다."""
    logging.basicConfig(level=logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()
