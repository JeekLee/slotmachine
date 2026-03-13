"""PARA 분류 모듈.

INBOX 문서를 로드하고, 파일 이동 및 git commit을 처리한다.
분류 판단 자체는 호스트 LLM(Claude Code)이 수행한다.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# PARA 카테고리 → 대상 폴더명 매핑
PARA_FOLDERS: dict[str, str] = {
    "Projects": "Projects",
    "Areas": "Areas",
    "Resources": "Resources",
    "Archives": "Archives",
}

# 분류 결과 미리보기 최대 길이
_EXCERPT_MAX = 300


@dataclass
class InboxDocument:
    """INBOX 문서 정보."""
    path: str          # vault 기준 상대 경로
    title: str
    tags: list[str]
    excerpt: str       # 본문 앞부분 (분류 판단용)


@dataclass
class ClassifyResult:
    """apply_classification 결과."""
    moved: int = 0
    skipped: int = 0
    commit_hash: str = ""
    errors: list[str] = field(default_factory=list)


def load_inbox(inbox_path: Path, vault_path: Path) -> list[InboxDocument]:
    """INBOX 폴더의 .md 파일을 로드해 반환한다.

    Args:
        inbox_path: INBOX 폴더 절대 경로
        vault_path: vault 루트 절대 경로 (상대경로 계산용)
    Returns:
        InboxDocument 목록 (재귀 포함, 숨김 폴더 제외)
    """
    from slotmachine.sync.parser import parse_document

    if not inbox_path.exists():
        logger.warning("INBOX 폴더가 없습니다: %s", inbox_path)
        return []

    docs: list[InboxDocument] = []
    for md_file in sorted(inbox_path.rglob("*.md")):
        # 숨김 폴더(.obsidian 등) 제외
        if any(part.startswith(".") for part in md_file.parts):
            continue
        try:
            parsed = parse_document(md_file)
            excerpt = parsed.raw_content[:_EXCERPT_MAX].strip()
            rel_path = md_file.relative_to(vault_path)
            docs.append(InboxDocument(
                path=str(rel_path),
                title=parsed.title,
                tags=parsed.tags,
                excerpt=excerpt,
            ))
        except Exception as exc:
            logger.warning("파싱 실패 — %s: %s", md_file.name, exc)

    return docs


def apply_classification(
    vault_path: Path,
    classifications: list[dict],
) -> ClassifyResult:
    """승인된 분류 결과에 따라 파일을 이동한다.

    Args:
        vault_path: vault 루트 절대 경로
        classifications: [{path: str, category: str}, ...] 목록
            - path: vault 기준 상대 경로
            - category: Projects / Areas / Resources / Archives / Inbox
    Returns:
        ClassifyResult
    """
    result = ClassifyResult()

    for item in classifications:
        rel_path = item.get("path", "")
        category = item.get("category", "")

        if category not in PARA_FOLDERS:
            # Inbox 또는 알 수 없는 카테고리 → 이동 안 함
            result.skipped += 1
            continue

        src = vault_path / rel_path
        if not src.exists():
            result.errors.append(f"파일 없음: {rel_path}")
            result.skipped += 1
            continue

        target_folder = vault_path / PARA_FOLDERS[category]
        target_folder.mkdir(parents=True, exist_ok=True)
        dst = target_folder / src.name

        # 파일명 충돌 시 번호 추가
        if dst.exists() and dst != src:
            stem, suffix = src.stem, src.suffix
            counter = 1
            while dst.exists():
                dst = target_folder / f"{stem}_{counter}{suffix}"
                counter += 1

        try:
            shutil.move(str(src), str(dst))
            logger.info("이동: %s → %s", src.name, target_folder.name)
            result.moved += 1
        except Exception as exc:
            result.errors.append(f"{src.name}: {exc}")
            result.skipped += 1

    return result
