"""Full Sync 파이프라인.

vault 내 모든 .md 파일을 파싱해 GraphDB에 일괄 적재한다.
진행률은 tqdm으로 표시하고, 결과를 SyncResult로 반환한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from tqdm import tqdm

from slotmachine.sync.embedding import BaseEmbeddingProvider
from slotmachine.sync.graphdb import GraphDB
from slotmachine.sync.parser import ParsedDocument, parse_document

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    total: int = 0
    success: int = 0
    failed: int = 0
    errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def skipped(self) -> int:
        return self.total - self.success - self.failed


def full_sync(
    vault_path: Path,
    db: GraphDB,
    *,
    embedding_provider: BaseEmbeddingProvider | None = None,
    para_category: str = "Inbox",
    show_progress: bool = True,
) -> SyncResult:
    """vault 내 모든 .md 파일을 GraphDB에 동기화한다.

    Args:
        vault_path: Obsidian vault 루트 경로
        db: 초기화된 GraphDB 인스턴스
        embedding_provider: 임베딩 생성 프로바이더 (None이면 임베딩 생략)
        para_category: 신규 노드에 부여할 기본 PARA 카테고리
        show_progress: tqdm 진행률 표시 여부

    Returns:
        동기화 결과 통계 (SyncResult)
    """
    md_files = _collect_md_files(vault_path)
    result = SyncResult(total=len(md_files))

    logger.info("Full Sync 시작 — %d개 파일 대상 (%s)", result.total, vault_path)

    with tqdm(
        md_files,
        desc="Syncing",
        unit="file",
        disable=not show_progress,
    ) as progress:
        for path in progress:
            progress.set_postfix_str(path.name, refresh=False)
            try:
                doc = parse_document(path)
                embedding = (
                    embedding_provider.embed_one(doc.raw_content)
                    if embedding_provider
                    else None
                )
                db.upsert_document(doc, embedding=embedding, para_category=para_category)
                result.success += 1
            except Exception as exc:
                result.failed += 1
                result.errors.append((path, str(exc)))
                logger.warning("파싱/저장 실패: %s — %s", path, exc)

    logger.info(
        "Full Sync 완료 — 성공: %d / 실패: %d / 전체: %d",
        result.success,
        result.failed,
        result.total,
    )
    return result


def _collect_md_files(vault_path: Path) -> list[Path]:
    """vault 내 모든 .md 파일을 재귀 탐색해 정렬된 리스트로 반환한다."""
    return sorted(vault_path.rglob("*.md"))
