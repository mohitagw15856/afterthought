"""Claude.ai data export: conversations.json with `chat_messages`."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..util import parse_ts
from .base import Message, clean_text

SENDER_MAP = {"human": "user", "assistant": "assistant"}


def _text_of(msg: dict) -> str:
    if msg.get("text"):
        return msg["text"]
    parts = []
    for block in msg.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def parse(path: Path) -> Iterator[Message]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    for conv in data:
        conv_id = conv.get("uuid") or ""
        title = conv.get("name") or "Untitled conversation"
        for msg in conv.get("chat_messages") or []:
            role = SENDER_MAP.get(msg.get("sender", ""))
            if role is None:
                continue
            text = clean_text(_text_of(msg))
            if not text:
                continue
            yield Message(
                source_file=path.name,
                format="claude",
                conversation_id=conv_id,
                conversation_title=title,
                message_id=msg.get("uuid") or "",
                role=role,
                ts=parse_ts(msg.get("created_at")),
                text=text,
            )
