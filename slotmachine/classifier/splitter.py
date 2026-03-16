"""문서 분할 적용 모듈 (F1-08 / F3-08).

맥락 기반 분할은 호스트 LLM(Claude Code)이 수행한다.
이 모듈은 LLM이 결정한 분할 결과를 vault에 실제로 적용하는 파일 I/O만 담당한다.

분할 승인 흐름:
  1. sync / classify_inbox → embedding 실패(oversized) 문서 목록 반환
  2. 호스트 LLM → 문서 전체 내용 기반으로 맥락 분할 제안
  3. 사용자 승인
  4. apply_split MCP tool → 이 모듈 호출
     - 분할 파일 생성 (원본과 같은 폴더)
     - 원본 파일 삭제
     - GraphDB 업데이트 (원본 노드 삭제, 분할 문서 upsert)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from slotmachine.sync.embedding import BaseEmbeddingProvider, embed_one_safe
from slotmachine.sync.graphdb import GraphDB
from slotmachine.sync.para_utils import resolve_para_category
from slotmachine.sync.parser import parse_document

logger = logging.getLogger(__name__)


@dataclass
class SplitResult:
    """apply_split 실행 결과."""

    created: list[str] = field(default_factory=list)   # 생성된 파일 상대경로
    deleted: str = ""                                   # 삭제된 원본 파일 상대경로
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0 and bool(self.created)


def apply_split(
    vault_path: Path,
    original_rel_path: str,
    split_docs: list[dict],
    db: GraphDB,
    *,
    embedding_provider: BaseEmbeddingProvider | None = None,
    para_folder_map: dict[str, str] | None = None,
    inbox_folder: str = "INBOX",
) -> SplitResult:
    """분할 결과를 vault에 적용하고 GraphDB를 업데이트한다.

    분할 파일을 원본과 같은 폴더에 생성한 뒤 원본을 삭제한다.
    INBOX 하위 파일은 GraphDB 업데이트를 생략한다 (Inbox는 GraphDB 적재 제외).
    PARA 카테고리 파일은 GraphDB에서 원본 노드를 삭제하고 분할 노드를 upsert한다.

    Args:
        vault_path: Obsidian vault 루트 절대 경로
        original_rel_path: vault 기준 원본 파일 상대경로
        split_docs: 분할 문서 목록 — [{"filename": "이름.md", "content": "..."}, ...]
        db: GraphDB 인스턴스
        embedding_provider: 임베딩 프로바이더 (None이면 임베딩 생략)
        para_folder_map: 카테고리 → 폴더명 매핑
        inbox_folder: INBOX 폴더명
    Returns:
        SplitResult
    """
    result = SplitResult()
    folder_map = para_folder_map or {
        "Projects": "Projects",
        "Areas": "Areas",
        "Resources": "Resources",
        "Archives": "Archives",
    }

    original_path = vault_path / original_rel_path
    target_dir = original_path.parent

    # 원본의 PARA 카테고리 확인 (Inbox는 GraphDB 업데이트 생략)
    original_category = resolve_para_category(
        original_path, vault_path, folder_map, inbox_folder
    )
    update_graphdb = original_category != "Inbox"

    # 1. 분할 파일 생성
    for item in split_docs:
        filename = item.get("filename", "").strip()
        content = item.get("content", "")

        if not filename or not content:
            result.failed += 1
            result.errors.append(f"빈 파일명 또는 내용: {item}")
            continue

        # .md 확장자 보장
        if not filename.endswith(".md"):
            filename += ".md"

        dest = target_dir / filename

        # 파일명 충돌 처리
        if dest.exists():
            stem = Path(filename).stem
            counter = 1
            while dest.exists():
                dest = target_dir / f"{stem}_{counter}.md"
                counter += 1

        try:
            dest.write_text(content, encoding="utf-8")
            rel = str(dest.relative_to(vault_path))
            result.created.append(rel)
            logger.info("분할 파일 생성: %s", rel)
        except Exception as exc:
            result.failed += 1
            result.errors.append(f"{filename} 생성 실패: {exc}")
            continue

        # GraphDB upsert (Inbox가 아닌 경우)
        if update_graphdb:
            try:
                parsed = parse_document(dest)
                if embedding_provider:
                    embedding, _ = embed_one_safe(embedding_provider, parsed.raw_content, dest)
                else:
                    embedding = None
                category = resolve_para_category(dest, vault_path, folder_map, inbox_folder)
                db.upsert_document(
                    parsed, vault_path=vault_path, embedding=embedding, para_category=category
                )
            except Exception as exc:
                logger.warning("GraphDB upsert 실패: %s — %s", filename, exc)
                result.errors.append(f"{filename} GraphDB upsert 실패: {exc}")

    # 2. 원본 삭제
    if original_path.exists():
        try:
            original_path.unlink()
            result.deleted = original_rel_path
            logger.info("원본 삭제: %s", original_rel_path)
        except Exception as exc:
            result.failed += 1
            result.errors.append(f"원본 삭제 실패: {exc}")

    # 3. GraphDB에서 원본 노드 삭제 (Inbox가 아닌 경우)
    if update_graphdb and result.deleted:
        try:
            db.delete_document(original_path, vault_path=vault_path)
        except Exception as exc:
            logger.warning("GraphDB 원본 노드 삭제 실패: %s — %s", original_rel_path, exc)
            result.errors.append(f"원본 노드 삭제 실패: {exc}")

    return result
