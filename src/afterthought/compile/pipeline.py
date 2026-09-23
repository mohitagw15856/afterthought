"""compile pipeline: inputs -> messages -> redaction -> extraction -> pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..ignore import IgnoreRules
from ..ingest import Message, detect_format, group_conversations, load
from ..llm.base import LLMProvider
from ..redact import redact
from ..vault import Vault
from .extract import Extraction, build_request
from .merge import (
    MergeStats,
    decision_id,
    rebuild_index,
    stage_decision,
    upsert_entity,
    upsert_question,
    upsert_timeline,
)
from .state import CompileState

SOURCES_INDEX = "sources/index.json"


@dataclass
class CompileReport:
    files: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    conversations: int = 0
    conversations_with_new: int = 0
    new_messages: int = 0
    skipped_messages: int = 0
    redactions: int = 0
    llm_calls: int = 0
    stats: MergeStats = field(default_factory=MergeStats)
    state_changed: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.stats.written) or self.state_changed


def resolve_inputs(inputs: list[Path], rules: IgnoreRules, fmt: str | None) -> tuple[list[tuple[Path, str]], list[str]]:
    found: list[tuple[Path, str]] = []
    ignored: list[str] = []
    for inp in inputs:
        inp = Path(inp)
        # explicit inputs are matched by name only; absolute paths would match unrelated rules
        if rules.is_ignored(inp.name):
            ignored.append(str(inp))
            continue
        if inp.is_dir():
            f = fmt or detect_format(inp)
            if f == "slack":
                found.append((inp, "slack"))
                continue
            for child in sorted(inp.rglob("*")):
                if not child.is_file():
                    continue
                rel = child.relative_to(inp).as_posix()
                if rules.is_ignored(rel):
                    ignored.append(rel)
                    continue
                cf = fmt or detect_format(child)
                if cf:
                    found.append((child, cf))
        else:
            f = fmt or detect_format(inp)
            if f is None:
                raise ValueError(f"Cannot detect format of {inp}; pass --format")
            found.append((inp, f))
    return found, ignored


def compile_inputs(
    vault: Vault,
    inputs: list[Path],
    *,
    provider: LLMProvider,
    fmt: str | None = None,
) -> CompileReport:
    if not vault.exists():
        vault.init()
    report = CompileReport()
    rules = vault.ignore_rules()
    allow = tuple(vault.config().get("redact", {}).get("allow_emails", []))
    state = CompileState(vault)
    stats = report.stats

    files, report.ignored = resolve_inputs(inputs, rules, fmt)
    messages: list[Message] = []
    source_index = vault.read_json(vault.root / SOURCES_INDEX, default={}) or {}
    for path, f in files:
        report.files.append(f"{path.name} ({f})")
        count = 0
        for m in load(path, f):
            text, rep = redact(m.text, allow_emails=allow)
            report.redactions += rep.total
            messages.append(m.model_copy(update={"text": text}))
            count += 1
        entry = source_index.get(path.name, {})
        entry.update({"format": f, "path": str(path.resolve()), "messages": count})
        source_index[path.name] = entry

    conversations = group_conversations(messages)
    conversations.sort(key=lambda c: (c.started is None, c.started or 0, c.id))
    report.conversations = len(conversations)

    for conv in conversations:
        new = [m for m in conv.messages if not state.is_processed(m.span)]
        report.skipped_messages += len(conv.messages) - len(new)
        if not new:
            continue
        report.conversations_with_new += 1
        report.new_messages += len(new)
        new_spans = [m.span for m in new]
        req = build_request(conv, new_spans)
        extraction = provider.complete_structured(req, Extraction)
        report.llm_calls += 1
        model = provider.model

        by_id = {m.message_id: m for m in conv.messages}
        names = [e.name for e in extraction.entities]
        for ent in extraction.entities:
            upsert_entity(vault, ent, conv, by_id, names, model, stats)
        dids = []
        for cand in extraction.decisions:
            stage_decision(vault, cand, conv, by_id, model, stats)
            dids.append(decision_id(conv, cand))
        for q in extraction.questions:
            upsert_question(vault, q, conv, by_id, model, stats)
        upsert_timeline(vault, conv, extraction, new, names, dids, model, stats)

        for m in conv.messages:
            state.mark(m.span, file=m.source_file, message_id=m.message_id, conversation=conv.id)
        state.record_batch(req.key, conversation=conv.id, spans=new_spans, model=model)

    # what the person has learned to do, from coach progress, lands on their own page
    from ..coach.progress import sync_to_wiki

    for rel in sync_to_wiki(vault):
        if rel not in stats.written:
            stats.written.append(rel)
    rebuild_index(vault, stats)
    report.state_changed = state.save()
    if files:
        vault.write_json(vault.root / SOURCES_INDEX, source_index)
    return report
