"""Origin tagging for every line the model wrote.

Rule: a line derived from a model ends with an Obsidian block id of the form
`^at-<origin>-<span>` where `<span>` is the span hash of the source message
that the line was extracted from. The page's frontmatter `sources` list maps
each span hash back to (file, message id, date). A line whose source cannot
be resolved is tagged `^at-unverified-<hash>` and prefixed with UNVERIFIED.

Block ids are alphanumeric plus hyphen, which is what Obsidian accepts.
"""

from __future__ import annotations

import re

from .schemas import Provenance, SourceRef
from .util import sha256_hex

TAG_RE = re.compile(r"\^at-(llm|human|import|system|unverified)-([A-Za-z0-9-]+)$")
BANNER = (
    "<!-- afterthought: lines ending in ^at-llm-<span> were written by a model from the "
    "source listed under that span in the frontmatter. UNVERIFIED lines have no resolvable "
    "source. -->"
)


def block_id(origin: str, span: str, suffix: int = 0) -> str:
    base = f"at-{origin}-{span}"
    return f"{base}-{suffix}" if suffix else base


def tag_line(text: str, origin: str, span: str, suffix: int = 0) -> str:
    return f"{text.rstrip()} ^{block_id(origin, span, suffix)}"


def unverified_line(text: str) -> str:
    h = sha256_hex(text, length=10)
    return f"UNVERIFIED: {text.rstrip()} ^{block_id('unverified', h)}"


def parse_tag(line: str) -> tuple[str, str] | None:
    m = TAG_RE.search(line.rstrip())
    return (m.group(1), m.group(2)) if m else None


def llm_provenance(model: str | None, tool: str = "afterthought.compile") -> Provenance:
    return Provenance(origin="llm", tool=tool, model=model)


def system_provenance(tool: str = "afterthought") -> Provenance:
    return Provenance(origin="system", tool=tool)


def merge_sources(existing: list[SourceRef], new: list[SourceRef]) -> list[SourceRef]:
    by_span = {s.span: s for s in existing}
    for s in new:
        by_span.setdefault(s.span, s)
    return sorted(by_span.values(), key=lambda s: (s.date is None, s.date or 0, s.span))
