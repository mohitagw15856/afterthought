"""Claude Code session transcripts: JSONL, one event per line.

Handles the shapes seen in ~/.claude/projects/<project>/<session>.jsonl:
`{"type": "user"|"assistant", "uuid", "timestamp", "sessionId",
  "message": {"role", "content": str | [blocks]}}`.
Tool calls and results are kept as short text so the conversation reads
sensibly; replay (module 5) parses the same file at full fidelity.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..util import parse_ts
from .base import Message, clean_text


def _blocks_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    out: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        t = block.get("type")
        if t == "text":
            out.append(block.get("text", ""))
        elif t == "tool_use":
            out.append(f"[tool_use {block.get('name')}] {json.dumps(block.get('input', {}), ensure_ascii=False)[:500]}")
        elif t == "tool_result":
            inner = block.get("content")
            if isinstance(inner, list):
                inner = "\n".join(b.get("text", "") for b in inner if isinstance(b, dict))
            out.append(f"[tool_result] {str(inner or '')[:500]}")
    return "\n".join(o for o in out if o)


def parse(path: Path) -> Iterator[Message]:
    session_id = path.stem
    title = f"Claude Code session {session_id[:8]}"
    first_user_seen = False
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = ev.get("type")
            if etype not in {"user", "assistant"}:
                continue
            msg = ev.get("message") or {}
            text = clean_text(_blocks_to_text(msg.get("content")))
            if not text:
                continue
            if etype == "user" and not first_user_seen and not text.startswith("["):
                title = text.splitlines()[0][:80]
                first_user_seen = True
            yield Message(
                source_file=path.name,
                format="claude_code",
                conversation_id=ev.get("sessionId") or session_id,
                conversation_title=title,
                message_id=ev.get("uuid") or "",
                role="user" if etype == "user" else "assistant",
                ts=parse_ts(ev.get("timestamp")),
                text=text,
            )
