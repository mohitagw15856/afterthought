"""ChatGPT data export: conversations.json (list of conversations with a
`mapping` tree). Nodes are linearised from the root along `children[0]`
after sorting children by create_time, so branches are followed in order."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..util import parse_ts
from .base import Message, clean_text

ROLE_MAP = {"user": "user", "assistant": "assistant", "system": "system", "tool": "tool"}


def _text_of(content: dict | None) -> str:
    if not content:
        return ""
    ctype = content.get("content_type")
    if ctype in {"text", "multimodal_text"}:
        parts = content.get("parts") or []
        return "\n".join(p for p in parts if isinstance(p, str))
    if ctype == "code":
        return content.get("text", "")
    return ""


def _linearise(mapping: dict) -> list[dict]:
    roots = [n for n in mapping.values() if not n.get("parent")]
    if not roots:
        return []
    ordered: list[dict] = []
    stack = list(reversed(roots))
    while stack:
        node = stack.pop()
        ordered.append(node)
        children = [mapping[c] for c in node.get("children", []) if c in mapping]
        children.sort(key=lambda n: (n.get("message") or {}).get("create_time") or 0)
        stack.extend(reversed(children))
    return ordered


def parse(path: Path) -> Iterator[Message]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    for conv in data:
        conv_id = conv.get("conversation_id") or conv.get("id") or ""
        title = conv.get("title") or "Untitled conversation"
        for node in _linearise(conv.get("mapping", {})):
            msg = node.get("message")
            if not msg:
                continue
            role = ROLE_MAP.get((msg.get("author") or {}).get("role", ""))
            if role is None:
                continue
            text = clean_text(_text_of(msg.get("content")))
            if not text or role == "system" and not text.strip():
                continue
            if (msg.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
                continue
            yield Message(
                source_file=path.name,
                format="chatgpt",
                conversation_id=conv_id,
                conversation_title=title,
                message_id=msg.get("id") or node.get("id") or "",
                role=role,
                author=None,
                ts=parse_ts(msg.get("create_time")),
                text=text,
            )
