"""Markdown page read/write with YAML frontmatter, Obsidian-compatible.

A page on disk looks like:

    ---
    id: lantern
    title: Lantern
    kind: project
    ...
    ---
    # Lantern
    ...

Managed sections (`## Facts`, `## Related`, `## Sources`) are regenerated
from data on every compile. Any other section a human adds is preserved
verbatim, in its original order, after the managed ones.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from .schemas import Page

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
BLOCK_ID_RE = re.compile(r"\s\^([A-Za-z0-9-]+)\s*$")
MANAGED_SECTIONS = ("Facts", "Related", "Sources")


class _Dumper(yaml.SafeDumper):
    pass


def _repr_datetime(dumper: yaml.SafeDumper, value: datetime) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))


def _repr_date(dumper: yaml.SafeDumper, value: date) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", value.isoformat())


_Dumper.add_representer(datetime, _repr_datetime)
_Dumper.add_representer(date, _repr_date)


def dump_frontmatter(data: dict[str, Any]) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    data = yaml.safe_load(m.group(1)) or {}
    if not isinstance(data, dict):
        data = {}
    return data, text[m.end() :]


def render_page(page: Page) -> str:
    fm = page.model_dump(mode="json", exclude={"body"}, exclude_none=True)
    body = page.body.rstrip("\n") + "\n"
    return f"---\n{dump_frontmatter(fm)}---\n{body}"


def parse_page(text: str) -> Page:
    fm, body = split_frontmatter(text)
    fm = dict(fm)
    fm["body"] = body
    return Page.model_validate(fm)


def read_page(path: Path) -> Page:
    return parse_page(path.read_text(encoding="utf-8"))


def extract_wikilinks(body: str) -> list[str]:
    seen: list[str] = []
    for m in WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        if target and target not in seen:
            seen.append(target)
    return seen


def split_sections(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a body into (preamble, [(heading, content), ...]) on `## ` headings."""
    lines = body.splitlines()
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    for line in lines:
        if line.startswith("## "):
            current = []
            sections.append((line[3:].strip(), current))
        elif current is None:
            preamble.append(line)
        else:
            current.append(line)
    return "\n".join(preamble), [(h, "\n".join(c).strip("\n")) for h, c in sections]


def unmanaged_sections(body: str) -> list[tuple[str, str]]:
    _, sections = split_sections(body)
    return [(h, c) for h, c in sections if h not in MANAGED_SECTIONS]


def block_ids(body: str) -> set[str]:
    ids: set[str] = set()
    for line in body.splitlines():
        m = BLOCK_ID_RE.search(line)
        if m:
            ids.add(m.group(1))
    return ids
