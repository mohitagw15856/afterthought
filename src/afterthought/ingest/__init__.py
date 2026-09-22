"""Ingest parsers. Each turns one export into a stream of `Message`s."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from . import chatgpt, claude_code, claude_export, markdown, slack
from .base import Conversation, Message, group_conversations

FORMATS = {
    "chatgpt": chatgpt,
    "claude": claude_export,
    "claude_code": claude_code,
    "slack": slack,
    "markdown": markdown,
}

__all__ = ["Conversation", "FORMATS", "Message", "detect_format", "group_conversations", "load"]


def detect_format(path: Path) -> str | None:
    """Sniff the export format. Returns None rather than guessing."""
    if path.is_dir():
        if (path / "channels.json").exists() or (path / "users.json").exists():
            return "slack"
        if (path / "conversations.json").exists():
            return detect_format(path / "conversations.json")
        return None
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return "markdown"
    if suffix == ".jsonl":
        return "claude_code"
    if suffix != ".json":
        return None
    try:
        head = path.read_text(encoding="utf-8")[:20000]
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            if "mapping" in first:
                return "chatgpt"
            if "chat_messages" in first:
                return "claude"
            if first.get("type") == "message" and "ts" in first:
                return "slack"
    if isinstance(data, dict) and "mapping" in data:
        return "chatgpt"
    if "chat_messages" in head:
        return "claude"
    return None


def load(path: Path, fmt: str | None = None) -> Iterator[Message]:
    fmt = fmt or detect_format(path)
    if fmt is None:
        raise ValueError(f"Cannot detect export format for {path}")
    if fmt not in FORMATS:
        raise ValueError(f"Unknown format {fmt!r}; known: {', '.join(FORMATS)}")
    yield from FORMATS[fmt].parse(path)
