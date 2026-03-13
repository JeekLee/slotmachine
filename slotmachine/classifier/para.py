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

# vault 구조 스캔에서 제외할 최상위 폴더 패턴
_EXCLUDE_PREFIXES = (".", "00_", "90_")


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


def get_vault_structure(
    vault_path: Path,
    para_folder_map: dict[str, str],
) -> dict[str, list[str]]:
    """각 PARA 폴더의 하위 디렉토리 구조와 문서 제목 목록을 반환한다.

    LLM이 적절한 하위 디렉토리를 선택하고 위키링크를 추가할 수 있도록
    vault의 기존 구조 정보를 제공한다.

    Args:
        vault_path: vault 루트 절대 경로
        para_folder_map: 카테고리 → PARA 폴더명 매핑
    Returns:
        카테고리 → {
            "subdirs": [하위 폴더 상대경로, ...],
            "doc_titles": [문서 제목(파일명 stem), ...]
        }
    """
    structure: dict[str, dict] = {}

    for category, folder_name in para_folder_map.items():
        folder_path = vault_path / folder_name
        if not folder_path.exists():
            structure[category] = {"subdirs": [], "doc_titles": []}
            continue

        # 하위 디렉토리 수집 (숨김 제외)
        subdirs: list[str] = []
        for d in sorted(folder_path.rglob("*")):
            if d.is_dir() and not any(p.startswith(".") for p in d.parts):
                rel = str(d.relative_to(vault_path))
                subdirs.append(rel)

        # 문서 제목 수집 (파일명 stem)
        doc_titles: list[str] = [
            f.stem
            for f in sorted(folder_path.rglob("*.md"))
            if not any(p.startswith(".") for p in f.parts)
        ]

        structure[category] = {
            "subdirs": subdirs,
            "doc_titles": doc_titles,
        }

    return structure


def apply_classification(
    vault_path: Path,
    classifications: list[dict],
    para_folder_map: dict[str, str] | None = None,
) -> ClassifyResult:
    """승인된 분류 결과에 따라 파일을 이동한다.

    Args:
        vault_path: vault 루트 절대 경로
        classifications: [{path, category, target_folder?, content?}, ...] 목록
            - path: vault 기준 원본 상대 경로
            - category: Projects / Areas / Resources / Archives / Inbox
            - target_folder: 이동할 폴더 (vault 기준 상대경로, 생략 시 category 폴더 사용)
              예: "20_Projects/CryptoLab/Rocky"
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
        target_folder_rel = item.get("target_folder", "")
        content = item.get("content")

        if category not in folders:
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

        # 목적지 폴더: target_folder > category 폴더
        if target_folder_rel:
            target_folder = vault_path / target_folder_rel
        else:
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
            logger.info("이동: %s → %s", src.name, target_folder)
            result.moved += 1
        except Exception as exc:
            result.errors.append(f"{src.name}: {exc}")
            result.skipped += 1

    return result
