"""증분 동기화 모듈.

DiffResult를 받아 변경된 .md 파일만 GraphDB에 반영한다.
생성/수정 파일은 parse → embed → upsert, 삭제 파일은 GraphDB에서 제거한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from slotmachine.sync.embedding import BaseEmbeddingProvider, embed_one_safe
from slotmachine.sync.git_manager import DiffResult
from slotmachine.sync.graphdb import GraphDB
from slotmachine.sync.para_utils import resolve_para_category
from slotmachine.sync.parser import parse_document

logger = logging.getLogger(__name__)


def _is_hidden(path: Path, vault_path: Path) -> bool:
    """.으로 시작하는 숨김 디렉토리(.git, .obsidian 등) 하위 파일이면 True."""
    try:
        rel = path.relative_to(vault_path)
        return any(part.startswith(".") for part in rel.parts)
    except ValueError:
        return False


@dataclass
class IncrementalSyncResult:
    """증분 동기화 결과 통계."""

    added: int = 0
    modified: int = 0
    deleted: int = 0
    failed: int = 0
    oversized_docs: list[str] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def total_changed(self) -> int:
        """성공한 변경 수 합계."""
        return self.added + self.modified + self.deleted

    @property
    def success(self) -> int:
        """성공 처리 수 (total_changed와 동일)."""
        return self.total_changed


def incremental_sync(
    diff: DiffResult,
    vault_path: Path,
    db: GraphDB,
    *,
    embedding_provider: BaseEmbeddingProvider | None = None,
    para_folder_map: dict[str, str] | None = None,
    inbox_folder: str = "INBOX",
) -> IncrementalSyncResult:
    """DiffResult를 기반으로 GraphDB를 증분 업데이트한다.

    생성/수정 파일은 parse → embed → upsert 처리하고,
    삭제 파일은 GraphDB에서 노드 및 관련 엣지를 제거한다.
    각 파일의 경로에서 PARA 카테고리를 자동으로 추론한다.

    Args:
        diff: git diff 분석 결과
        vault_path: Obsidian vault 루트 경로
        db: 초기화된 GraphDB 인스턴스
        embedding_provider: 임베딩 프로바이더 (None이면 임베딩 생략)
        para_folder_map: {"Projects": "20_Projects", ...} — None이면 기본값 사용
        inbox_folder: INBOX 폴더명 (기본: "INBOX")
    Returns:
        IncrementalSyncResult — 변경 통계
    """
    folder_map = para_folder_map or {
        "Projects": "Projects",
        "Areas": "Areas",
        "Resources": "Resources",
        "Archives": "Archives",
    }
    result = IncrementalSyncResult()

    if diff.is_empty:
        logger.info("증분 Sync: 변경 파일 없음")
        return result

    logger.info(
        "증분 Sync 시작 — 추가 %d / 수정 %d / 삭제 %d",
        len(diff.added), len(diff.modified), len(diff.deleted),
    )

    # 생성/수정 파일 처리 (.으로 시작하는 숨김 디렉토리 제외)
    for path in diff.added + diff.modified:
        if _is_hidden(path, vault_path):
            logger.debug("숨김 디렉토리 파일 스킵: %s", path)
            continue
        is_added = path in diff.added
        try:
            category = resolve_para_category(path, vault_path, folder_map, inbox_folder)
            if category == "Inbox":
                logger.debug("Inbox 스킵: %s", path)
                continue
            doc = parse_document(path)
            if embedding_provider:
                embedding, is_oversized = embed_one_safe(
                    embedding_provider, doc.raw_content, path
                )
                if is_oversized:
                    result.oversized_docs.append(str(path.relative_to(vault_path)))
            else:
                embedding, is_oversized = None, False
            db.upsert_document(doc, vault_path=vault_path, embedding=embedding, para_category=category)
            if is_added:
                result.added += 1
            else:
                result.modified += 1
        except Exception as exc:
            result.failed += 1
            result.errors.append((path, str(exc)))
            logger.warning("파싱/저장 실패: %s — %s", path, exc)

    # 삭제 파일 처리
    for path in diff.deleted:
        if _is_hidden(path, vault_path):
            continue
        try:
            # 삭제 전 제목 조회 — dead link 정리(F2-09)에 사용
            try:
                rel_path = path.relative_to(vault_path).as_posix()
            except ValueError:
                rel_path = path.as_posix()
            doc_data = db.get_document(rel_path)
            old_title = doc_data.get("title") if doc_data else None

            db.delete_document(path, vault_path=vault_path)
            result.deleted += 1

            # 다른 문서 본문의 [[old_title]] 위키링크 제거 (F2-09)
            if old_title:
                from slotmachine.linker.linker import remove_wikilinks_in_vault
                remove_wikilinks_in_vault(vault_path, old_title)
        except Exception as exc:
            result.failed += 1
            result.errors.append((path, str(exc)))
            logger.warning("삭제 실패: %s — %s", path, exc)

    logger.info(
        "증분 Sync 완료 — 추가 %d / 수정 %d / 삭제 %d / 실패 %d",
        result.added, result.modified, result.deleted, result.failed,
    )
    return result
