"""Turn a Claude Code transcript or a generic JSONL hook log into a Run.

Generic hook format, one JSON object per line:

    {"ts": "2026-05-01T10:00:00Z", "kind": "user", "content": "Fix the failing test"}
    {"ts": "...", "kind": "assistant", "content": "I will run the tests first."}
    {"ts": "...", "kind": "tool_call", "name": "bash", "id": "t1", "content": {"cmd": "pytest -q"}}
    {"ts": "...", "kind": "tool_result", "name": "bash", "ref": "t1", "content": "1 failed"}
    {"ts": "...", "kind": "system", "content": "context compacted"}

`type` is accepted as an alias for `kind`, `tool` for `name`, `tool_use_id` for `ref`.
Content may be a string or any JSON value; values are serialised deterministically.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..redact import redact
from ..schemas import Provenance, Run, Step
from ..util import parse_ts, sha256_hex, slugify

KINDS = {"user", "assistant", "tool_call", "tool_result", "system"}
ALIASES = {"tool_use": "tool_call", "tool": "tool_call", "result": "tool_result", "human": "user", "ai": "assistant"}


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2)


def _step(index: int, kind: str, content: str, *, ts: datetime | None, name: str | None, ref: str | None) -> Step:
    content, _ = redact(content)
    h = sha256_hex(content, length=12)
    return Step(
        index=index,
        ts=ts,
        kind=kind,  # type: ignore[arg-type]
        name=name,
        ref=ref,
        input_hash=h if kind in {"user", "tool_call", "system"} else "",
        output_hash=h if kind in {"assistant", "tool_result"} else "",
        content=content,
    )


def parse_hook_jsonl(path: Path) -> list[Step]:
    steps: list[Step] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(ev, dict):
                continue
            kind = str(ev.get("kind") or ev.get("type") or "").lower()
            kind = ALIASES.get(kind, kind)
            if kind not in KINDS:
                continue
            name = ev.get("name") or ev.get("tool") or ev.get("tool_name")
            ref = ev.get("ref") or ev.get("tool_use_id") or (ev.get("id") if kind == "tool_call" else None)
            steps.append(
                _step(
                    len(steps),
                    kind,
                    _text(ev.get("content")),
                    ts=parse_ts(ev.get("ts") or ev.get("timestamp")),
                    name=name,
                    ref=ref,
                )
            )
    return steps


def parse_claude_code(path: Path) -> list[Step]:
    steps: list[Step] = []
    names: dict[str, str] = {}
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
            ts = parse_ts(ev.get("timestamp"))
            if etype == "system" and isinstance(ev.get("content"), str):
                steps.append(_step(len(steps), "system", ev["content"], ts=ts, name=None, ref=None))
                continue
            if etype not in {"user", "assistant"}:
                continue
            content = (ev.get("message") or {}).get("content")
            if isinstance(content, str):
                steps.append(_step(len(steps), etype, content, ts=ts, name=None, ref=None))
                continue
            for block in content or []:
                if not isinstance(block, dict):
                    continue
                bt = block.get("type")
                if bt == "text" and block.get("text", "").strip():
                    steps.append(_step(len(steps), etype, block["text"], ts=ts, name=None, ref=None))
                elif bt == "tool_use":
                    names[block.get("id", "")] = block.get("name", "tool")
                    steps.append(
                        _step(
                            len(steps),
                            "tool_call",
                            _text(block.get("input", {})),
                            ts=ts,
                            name=block.get("name"),
                            ref=block.get("id"),
                        )
                    )
                elif bt == "tool_result":
                    inner = block.get("content")
                    if isinstance(inner, list):
                        inner = "\n".join(b.get("text", "") for b in inner if isinstance(b, dict))
                    ref = block.get("tool_use_id")
                    steps.append(
                        _step(len(steps), "tool_result", _text(inner), ts=ts, name=names.get(ref or ""), ref=ref)
                    )
    return steps


def detect_run_format(path: Path) -> str | None:
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                if not isinstance(ev, dict):
                    return None
                if "message" in ev and ev.get("type") in {"user", "assistant", "summary", "system"}:
                    return "claude_code"
                if ev.get("type") == "summary":
                    continue
                if "kind" in ev or "type" in ev:
                    return "jsonl_hook"
                return None
    except (OSError, json.JSONDecodeError):
        return None
    return None


def parse_run(path: Path, fmt: str | None = None, run_id: str | None = None) -> Run:
    fmt = fmt or detect_run_format(path)
    if fmt not in {"claude_code", "jsonl_hook"}:
        raise ValueError(f"Cannot detect run format of {path}; pass --format claude_code or jsonl_hook")
    steps = parse_claude_code(path) if fmt == "claude_code" else parse_hook_jsonl(path)
    content_hash = sha256_hex(*(s.content for s in steps), length=8)
    rid = run_id or f"{slugify(path.stem, max_len=40)}-{content_hash}"
    stamps = [s.ts for s in steps if s.ts]
    first_user = next((s.content for s in steps if s.kind == "user" and not s.content.startswith("[")), None)
    last_assistant = next((s.content for s in reversed(steps) if s.kind == "assistant"), None)
    return Run(
        id=rid,
        source=fmt,  # type: ignore[arg-type]
        source_file=path.name,
        title=(first_user or path.stem).splitlines()[0][:100],
        started=min(stamps) if stamps else None,
        ended=max(stamps) if stamps else None,
        steps=steps,
        outcome=last_assistant.strip()[:500] if last_assistant else None,
        provenance=Provenance(origin="import", tool="afterthought.replay", derived_from=[path.name]),
    )
