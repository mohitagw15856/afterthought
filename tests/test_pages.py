from datetime import UTC, datetime

from afterthought.pages import (
    block_ids,
    extract_wikilinks,
    parse_page,
    render_page,
    split_sections,
    unmanaged_sections,
)
from afterthought.provenance import parse_tag, tag_line, unverified_line
from afterthought.schemas import Page, Provenance, SourceRef
from afterthought.util import slugify


def _page() -> Page:
    return Page(
        id="x",
        title="X",
        kind="concept",
        sources=[SourceRef(file="f.json", message_id="m1", date=datetime(2026, 1, 2, tzinfo=UTC), span="abc")],
        provenance=Provenance(origin="llm", model="m"),
        updated=datetime(2026, 1, 2, tzinfo=UTC),
        body="# X\n\n## Facts\n- one ^at-llm-abc\n\n## Notes\nhuman text\n",
    )


def test_roundtrip() -> None:
    text = render_page(_page())
    assert text.startswith("---\nid: x\n")
    assert "date: '2026-01-02T00:00:00Z'" in text
    back = parse_page(text)
    assert back.model_dump() == _page().model_dump()
    assert render_page(back) == text


def test_sections_and_blocks() -> None:
    body = _page().body
    pre, sections = split_sections(body)
    assert pre.strip() == "# X"
    assert [h for h, _ in sections] == ["Facts", "Notes"]
    assert unmanaged_sections(body) == [("Notes", "human text")]
    assert block_ids(body) == {"at-llm-abc"}
    assert extract_wikilinks("see [[a|A]] and [[b#h]] and [[a]]") == ["a", "b"]


def test_tags() -> None:
    assert tag_line("hello", "llm", "abc") == "hello ^at-llm-abc"
    assert parse_tag(tag_line("hello", "llm", "abc", suffix=2)) == ("llm", "abc-2")
    u = unverified_line("guess")
    assert u.startswith("UNVERIFIED: guess ^at-unverified-")


def test_slugify() -> None:
    assert slugify("Octopus Home Mini") == "octopus-home-mini"
    assert slugify("a-very-long-title-that-keeps-going", max_len=12) == "a-very-long"
    assert slugify("???") == "untitled"
