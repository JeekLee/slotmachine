"""PARA 분류 모듈.

INBOX 문서를 로드하고, 파일 이동을 처리한다.
분류 판단 및 템플릿 기반 문서 재작성은 호스트 LLM(Claude Code)이 수행한다.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# 기본 PARA 카테고리 → 폴더명 (Settings 없이 사용할 때의 fallback)
DEFAULT_PARA_FOLDERS: dict[str, str] = {
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
    full_content: str  # 전체 원본 내용 (LLM 재작성용)


@dataclass
class ClassifyResult:
    """apply_classification 결과."""
    moved: int = 0
    skipped: int = 0
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
            full_content = md_file.read_text(encoding="utf-8")
            excerpt = parsed.raw_content[:_EXCERPT_MAX].strip()
            rel_path = md_file.relative_to(vault_path)
            docs.append(InboxDocument(
                path=str(rel_path),
                title=parsed.title,
                tags=parsed.tags,
                excerpt=excerpt,
                full_content=full_content,
            ))
        except Exception as exc:
            logger.warning("파싱 실패 — %s: %s", md_file.name, exc)

    return docs


def load_template(vault_path: Path, template_rel: str) -> str:
    """템플릿 파일 내용을 읽어 반환한다.

    Args:
        vault_path: vault 루트 절대 경로
        template_rel: vault 기준 템플릿 상대경로
    Returns:
        템플릿 파일 내용. 파일이 없거나 읽기 실패 시 빈 문자열.
    """
    if not template_rel:
        return ""
    template_path = vault_path / template_rel
    if not template_path.exists():
        logger.debug("템플릿 파일 없음: %s", template_path)
        return ""
    try:
        return template_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("템플릿 읽기 실패 — %s: %s", template_rel, exc)
        return ""


def apply_classification(
    vault_path: Path,
    classifications: list[dict],
    para_folder_map: dict[str, str] | None = None,
) -> ClassifyResult:
    """승인된 분류 결과에 따라 파일을 이동한다.

    각 항목에 content가 포함된 경우 이동 전 파일을 해당 내용으로 덮어쓴다.
    (LLM이 템플릿에 맞게 재작성한 내용을 적용하는 용도)

    Args:
        vault_path: vault 루트 절대 경로
        classifications: [{path, category, content(optional)}, ...] 목록
            - path: vault 기준 상대 경로
            - category: Projects / Areas / Resources / Archives / Inbox
            - content: LLM이 재작성한 문서 내용 (생략 시 원본 유지)
        para_folder_map: 카테고리 → 폴더명 매핑 (None이면 기본값 사용)
    Returns:
        ClassifyResult
    """
    folders = para_folder_map or DEFAULT_PARA_FOLDERS
    result = ClassifyResult()

    for item in classifications:
        rel_path = item.get("path", "")
        category = item.get("category", "")
        content = item.get("content")  # LLM 재작성 내용 (선택)

        if category not in folders:
            # Inbox 또는 알 수 없는 카테고리 → 이동 안 함
            result.skipped += 1
            continue

        src = vault_path / rel_path
        if not src.exists():
            result.errors.append(f"파일 없음: {rel_path}")
            result.skipped += 1
            continue

        # LLM 재작성 내용이 있으면 이동 전 파일에 씀
        if content:
            try:
                src.write_text(content, encoding="utf-8")
                logger.debug("재작성 내용 적용: %s", src.name)
            except Exception as exc:
                result.errors.append(f"{src.name} 쓰기 실패: {exc}")
                result.skipped += 1
                continue

        target_folder = vault_path / folders[category]
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
