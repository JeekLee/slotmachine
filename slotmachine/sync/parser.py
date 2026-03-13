"""Markdown 파서 모듈.

Obsidian vault의 .md 파일을 파싱해 제목, 태그, 위키링크, 프론트매터를 추출한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter


# [[링크]] 또는 [[링크|별칭]] 패턴
_WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# 인라인 #태그 패턴 — 단어 경계 앞에 #, 태그명은 영문/한글/숫자/하이픈/언더스코어
_INLINE_TAG_RE = re.compile(r"(?<![&/\w])#([\w가-힣][/\w가-힣-]*)")

# H1 제목 패턴
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


@dataclass
class ParsedDocument:
    path: Path
    title: str
    frontmatter: dict
    tags: list[str] = field(default_factory=list)
    wiki_links: list[str] = field(default_factory=list)
    raw_content: str = ""


def parse_document(path: Path) -> ParsedDocument:
    """단일 Markdown 파일을 파싱해 ParsedDocument를 반환한다.

    Args:
        path: 파싱할 .md 파일 경로

    Returns:
        제목·프론트매터·태그·위키링크·본문이 담긴 ParsedDocument

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        ValueError: .md 파일이 아닐 때
    """
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
    if path.suffix.lower() != ".md":
        raise ValueError(f".md 파일이 아닙니다: {path}")

    raw = path.read_text(encoding="utf-8")
    post = frontmatter.loads(raw)

    fm: dict = dict(post.metadata)
    body: str = post.content  # 프론트매터 제거된 본문

    title = _extract_title(body, fm, path)
    tags = _extract_tags(body, fm)
    wiki_links = _extract_wiki_links(body)

    return ParsedDocument(
        path=path,
        title=title,
        frontmatter=fm,
        tags=tags,
        wiki_links=wiki_links,
        raw_content=body,
    )


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _extract_title(body: str, fm: dict, path: Path) -> str:
    """제목 추출 우선순위: frontmatter title → H1 → 파일명."""
    if fm.get("title"):
        return str(fm["title"])
    m = _H1_RE.search(body)
    if m:
        return m.group(1).strip()
    return path.stem


def _extract_tags(body: str, fm: dict) -> list[str]:
    """frontmatter tags + 본문 인라인 #태그를 병합해 중복 제거 후 반환."""
    tags: list[str] = []

    # frontmatter tags (문자열 또는 리스트)
    fm_tags = fm.get("tags", [])
    if isinstance(fm_tags, str):
        fm_tags = [t.strip() for t in fm_tags.split(",") if t.strip()]
    tags.extend(str(t) for t in fm_tags)

    # 인라인 #태그
    tags.extend(_INLINE_TAG_RE.findall(body))

    # 중복 제거, 순서 유지
    seen: set[str] = set()
    result: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _extract_wiki_links(body: str) -> list[str]:
    """본문에서 [[위키링크]] 대상 목록을 중복 제거 후 반환."""
    seen: set[str] = set()
    result: list[str] = []
    for target in _WIKI_LINK_RE.findall(body):
        target = target.strip()
        if target not in seen:
            seen.add(target)
            result.append(target)
    return result
