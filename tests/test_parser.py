"""parse_document() 단위 테스트."""
from pathlib import Path

import pytest

from slotmachine.sync.parser import ParsedDocument, parse_document


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def md_file(tmp_path: Path):
    """tmp_path에 .md 파일을 생성하는 팩토리 픽스처."""
    def _make(filename: str, content: str) -> Path:
        p = tmp_path / filename
        p.write_text(content, encoding="utf-8")
        return p
    return _make


# ---------------------------------------------------------------------------
# 기본 반환 타입
# ---------------------------------------------------------------------------

def test_returns_parsed_document(md_file):
    p = md_file("note.md", "# Hello\n")
    result = parse_document(p)
    assert isinstance(result, ParsedDocument)


# ---------------------------------------------------------------------------
# 제목 추출
# ---------------------------------------------------------------------------

def test_title_from_h1(md_file):
    p = md_file("note.md", "# My Title\n\nsome content")
    assert parse_document(p).title == "My Title"


def test_title_from_frontmatter(md_file):
    p = md_file("note.md", "---\ntitle: FM Title\n---\n# H1 Title\n")
    assert parse_document(p).title == "FM Title"


def test_title_fallback_to_filename(md_file):
    p = md_file("my-note.md", "no heading here")
    assert parse_document(p).title == "my-note"


# ---------------------------------------------------------------------------
# 프론트매터 추출
# ---------------------------------------------------------------------------

def test_frontmatter_parsed(md_file):
    p = md_file("note.md", "---\nalias: foo\nstatus: draft\n---\n")
    fm = parse_document(p).frontmatter
    assert fm["alias"] == "foo"
    assert fm["status"] == "draft"


def test_frontmatter_empty_when_absent(md_file):
    p = md_file("note.md", "# No FM\n")
    assert parse_document(p).frontmatter == {}


# ---------------------------------------------------------------------------
# 태그 추출
# ---------------------------------------------------------------------------

def test_tags_from_frontmatter_list(md_file):
    p = md_file("note.md", "---\ntags:\n  - project\n  - idea\n---\n")
    assert parse_document(p).tags == ["project", "idea"]


def test_tags_from_frontmatter_string(md_file):
    p = md_file("note.md", "---\ntags: project, idea\n---\n")
    assert parse_document(p).tags == ["project", "idea"]


def test_inline_tags(md_file):
    p = md_file("note.md", "내용 #project #아이디어 끝\n")
    tags = parse_document(p).tags
    assert "project" in tags
    assert "아이디어" in tags


def test_tags_deduplicated(md_file):
    p = md_file("note.md", "---\ntags:\n  - project\n---\n#project\n")
    assert parse_document(p).tags.count("project") == 1


def test_url_hash_not_treated_as_tag(md_file):
    p = md_file("note.md", "https://example.com/#section\n")
    assert parse_document(p).tags == []


# ---------------------------------------------------------------------------
# 위키링크 추출
# ---------------------------------------------------------------------------

def test_wiki_links_basic(md_file):
    p = md_file("note.md", "참고: [[다른노트]] 와 [[두번째노트]]\n")
    assert parse_document(p).wiki_links == ["다른노트", "두번째노트"]


def test_wiki_links_with_alias(md_file):
    p = md_file("note.md", "[[노트이름|표시텍스트]]\n")
    assert parse_document(p).wiki_links == ["노트이름"]


def test_wiki_links_deduplicated(md_file):
    p = md_file("note.md", "[[노트]] [[노트]]\n")
    assert parse_document(p).wiki_links.count("노트") == 1


def test_wiki_links_empty_when_absent(md_file):
    p = md_file("note.md", "링크 없는 문서\n")
    assert parse_document(p).wiki_links == []


# ---------------------------------------------------------------------------
# raw_content
# ---------------------------------------------------------------------------

def test_raw_content_excludes_frontmatter(md_file):
    p = md_file("note.md", "---\ntitle: T\n---\n# Body\n")
    content = parse_document(p).raw_content
    assert "title: T" not in content
    assert "Body" in content


# ---------------------------------------------------------------------------
# 에러 케이스
# ---------------------------------------------------------------------------

def test_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_document(tmp_path / "ghost.md")


def test_not_md_extension(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_document(p)
