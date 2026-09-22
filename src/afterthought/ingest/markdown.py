"""Plain markdown transcripts.

Recognised turn markers (case-insensitive, at line start):
`**User:**`, `**Assistant:**`, `User:`, `Assistant:`, `## User`, `## Assistant`,
`> **User**`. A file without markers becomes one `user` message. Optional
frontmatter keys `title`, `date` and `author` are honoured.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ..pages import split_frontmatter
from ..util import parse_ts, sha256_hex
from .base import Message, clean_text

MARKER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*|>\s*)?\**\s*(user|assistant|human|ai|me|claude|chatgpt)\s*\**\s*:?\s*\**\s*$",
    re.IGNORECASE,
)
ROLE_FOR = {
    "user": "user",
    "human": "user",
    "me": "user",
    "assistant": "assistant",
    "ai": "assistant",
    "claude": "assistant",
    "chatgpt": "assistant",
}
INLINE_RE = re.compile(r"^\s*\**\s*(user|assistant|human|ai)\s*\**\s*:\s*\**\s*(.+)$", re.IGNORECASE)


def parse(path: Path) -> Iterator[Message]:
    fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
    title = str(fm.get("title") or path.stem)
    ts = parse_ts(str(fm["date"])) if fm.get("date") else None
    author = fm.get("author")
    turns: list[tuple[str, list[str]]] = []
    current_role = None
    buf: list[str] = []
    for line in body.splitlines():
        m = MARKER_RE.match(line)
        im = INLINE_RE.match(line) if not m else None
        if m or im:
            if current_role and "\n".join(buf).strip():
                turns.append((current_role, buf))
            key = (m or im).group(1).lower()
            current_role = ROLE_FOR[key]
            buf = [im.group(2)] if im else []
            continue
        if current_role is None and line.strip():
            current_role = "user"
        buf.append(line)
    if current_role and "\n".join(buf).strip():
        turns.append((current_role, buf))
    conv_id = sha256_hex(path.name, length=10)
    for i, (role, lines) in enumerate(turns, start=1):
        text = clean_text("\n".join(lines))
        if not text:
            continue
        yield Message(
            source_file=path.name,
            format="markdown",
            conversation_id=conv_id,
            conversation_title=title,
            message_id=f"turn-{i}",
            role=role,  # type: ignore[arg-type]
            author=str(author) if author and role == "user" else None,
            ts=ts,
            text=text,
        )
