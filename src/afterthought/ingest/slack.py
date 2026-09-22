"""Slack workspace export: a directory with users.json, channels.json and
<channel>/<date>.json files, or a single JSON list of messages."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..util import parse_ts
from .base import Message, clean_text


def _users(root: Path) -> dict[str, str]:
    f = root / "users.json"
    if not f.exists():
        return {}
    try:
        return {
            u["id"]: (u.get("real_name") or u.get("name") or u["id"])
            for u in json.loads(f.read_text(encoding="utf-8"))
            if isinstance(u, dict) and "id" in u
        }
    except (json.JSONDecodeError, KeyError):
        return {}


def _messages(
    file: Path, channel: str, users: dict[str, str], source_name: str
) -> Iterator[Message]:
    try:
        items = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        if item.get("subtype") in {"channel_join", "channel_leave", "bot_message"}:
            continue
        text = clean_text(item.get("text") or "")
        if not text:
            continue
        uid = item.get("user") or item.get("username") or "unknown"
        ts = item.get("ts") or ""
        yield Message(
            source_file=source_name,
            format="slack",
            conversation_id=channel,
            conversation_title=f"#{channel}",
            message_id=item.get("client_msg_id") or ts,
            role="user",
            author=users.get(uid, uid),
            ts=parse_ts(ts),
            text=text,
        )


def parse(path: Path) -> Iterator[Message]:
    if path.is_file():
        yield from _messages(path, path.stem, {}, path.name)
        return
    users = _users(path)
    for channel_dir in sorted(p for p in path.iterdir() if p.is_dir()):
        for day_file in sorted(channel_dir.glob("*.json")):
            rel = f"{path.name}/{channel_dir.name}/{day_file.name}"
            yield from _messages(day_file, channel_dir.name, users, rel)
