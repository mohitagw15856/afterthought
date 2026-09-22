"""Upsert extracted material into wiki pages.

Every page write goes through Vault.write_text, which redacts and skips
unchanged content, so calling these functions twice is a no-op.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..decide.render import render_decision
from ..ingest.base import Conversation, Message
from ..pages import (
    extract_wikilinks,
    read_page,
    render_page,
    split_frontmatter,
    unmanaged_sections,
)
from ..provenance import (
    BANNER,
    llm_provenance,
    merge_sources,
    system_provenance,
    tag_line,
    unverified_line,
)
from ..schemas import Assumption, Decision, Page, SourceRef
from ..util import normalise_text, sha256_hex, slugify
from ..vault import Vault
from .extract import CandidateDecision, EntityMention, Extraction, OpenQuestion

KIND_DIR = {"project": "projects", "person": "people", "tool": "tools", "concept": "concepts"}
FACT_TAG_RE = re.compile(r"\s\^at-[A-Za-z0-9-]+$")


@dataclass
class MergeStats:
    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    decisions_staged: int = 0
    questions: int = 0
    unverified_facts: int = 0

    def note(self, vault: Vault, path: Path, changed: bool) -> None:
        rel = vault.rel(path)
        if changed:
            if rel not in self.written:
                self.written.append(rel)
            if rel in self.unchanged:
                self.unchanged.remove(rel)
        elif rel not in self.written and rel not in self.unchanged:
            self.unchanged.append(rel)


# ----------------------------------------------------------------- helpers
def source_ref(m: Message) -> SourceRef:
    return SourceRef(
        file=m.source_file,
        message_id=m.message_id,
        date=m.ts,
        span=m.span,
        format=m.format,
        conversation=m.conversation_id,
    )


def timeline_name(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "undated"


def conversation_source_line(conv: Conversation) -> str:
    day = timeline_name(conv.started)
    return f"- [[timeline/{day}|{day}]] {conv.title} ({conv.format}, {conv.source_file})"


def _strip_tag(line: str) -> str:
    line = FACT_TAG_RE.sub("", line.rstrip())
    return line[2:] if line.startswith("- ") else line


def _existing_bullets(body: str, heading: str) -> list[str]:
    from ..pages import split_sections

    _, sections = split_sections(body)
    for h, content in sections:
        if h == heading:
            return [ln for ln in content.splitlines() if ln.startswith("- ")]
    return []


def wikilink(name: str) -> str:
    """Obsidian link that resolves by file name and displays the title."""
    return f"[[{slugify(name)}|{name}]]"


def wikilink_names(text: str, names: list[str], self_name: str) -> str:
    """Wrap known entity names in [[slug|Name]] (longest first, whole word, once each)."""
    for name in sorted(names, key=len, reverse=True):
        if len(name) < 3 or name.lower() == self_name.lower():
            continue
        pattern = re.compile(rf"(?<![\[|])\b({re.escape(name)})\b(?![\]|])", re.IGNORECASE)
        text = pattern.sub(lambda m, nm=name: wikilink(nm), text, count=1)
    return text


def _max_date(refs: list[SourceRef]) -> datetime | None:
    dates = [r.date for r in refs if r.date]
    return max(dates) if dates else None


def _min_date(refs: list[SourceRef]) -> datetime | None:
    dates = [r.date for r in refs if r.date]
    return min(dates) if dates else None


# ---------------------------------------------------------------- entities
def entity_path(vault: Vault, kind: str, name: str) -> Path:
    return vault.root / "entities" / KIND_DIR[kind] / f"{slugify(name)}.md"


def upsert_entity(
    vault: Vault,
    mention: EntityMention,
    conv: Conversation,
    by_message_id: dict[str, Message],
    all_names: list[str],
    model: str | None,
    stats: MergeStats,
) -> None:
    path = entity_path(vault, mention.kind, mention.name)
    page = read_page(path) if path.exists() else None

    new_refs: list[SourceRef] = []
    new_fact_lines: list[str] = []
    for fact in mention.facts:
        text = wikilink_names(fact.text.strip(), all_names, mention.name)
        msg = by_message_id.get(fact.message_id)
        if msg is None:
            new_fact_lines.append(f"- {unverified_line(text)}")
            stats.unverified_facts += 1
            continue
        new_refs.append(source_ref(msg))
        new_fact_lines.append(f"- {tag_line(text, 'llm', msg.span)}")

    old_body = page.body if page else ""
    old_facts = _existing_bullets(old_body, "Facts")
    seen = {normalise_text(_strip_tag(ln)) for ln in old_facts}
    facts = list(old_facts)
    for ln in new_fact_lines:
        key = normalise_text(_strip_tag(ln))
        if key not in seen:
            seen.add(key)
            facts.append(ln)
    # make block ids unique within the page
    used: set[str] = set()
    deduped: list[str] = []
    for ln in facts:
        m = re.search(r"\^(at-[A-Za-z0-9-]+)$", ln)
        if not m:
            deduped.append(ln)
            continue
        bid = m.group(1)
        base, n = bid, 1
        while bid in used:
            n += 1
            bid = f"{base}-{n}"
        used.add(bid)
        deduped.append(ln[: m.start(1)] + bid)
    facts = deduped

    related = {ln for ln in _existing_bullets(old_body, "Related")}
    for name in all_names:
        if name.lower() != mention.name.lower():
            related.add(f"- {wikilink(name)}")
    sources_lines = {ln for ln in _existing_bullets(old_body, "Sources")}
    sources_lines.add(conversation_source_line(conv))

    body_parts = [f"# {mention.name}", "", BANNER, "", "## Facts"]
    body_parts += facts or ["- (no facts extracted yet)"]
    body_parts += ["", "## Related"] + sorted(related) + ["", "## Sources"] + sorted(sources_lines)
    for heading, content in unmanaged_sections(old_body):
        body_parts += ["", f"## {heading}", content]
    body = "\n".join(body_parts) + "\n"

    refs = merge_sources(page.sources if page else [], new_refs)
    aliases = sorted({*(page.aliases if page else []), *mention.aliases} - {mention.name})
    prov = page.provenance if page else llm_provenance(model)
    if prov.created is None:
        prov = prov.model_copy(update={"created": _min_date(refs)})
    if model and model not in (prov.derived_from or []):
        prov = prov.model_copy(update={"derived_from": sorted({*prov.derived_from, model})})
    new_page = Page(
        id=slugify(mention.name),
        title=page.title if page else mention.name,
        kind=mention.kind,
        aliases=aliases,
        tags=sorted({"afterthought", mention.kind, *(page.tags if page else [])}),
        sources=refs,
        provenance=prov,
        updated=_max_date(refs),
        links=extract_wikilinks(body),
        body=body,
    )
    res = vault.write_text(path, render_page(new_page))
    stats.note(vault, path, res.changed)


# --------------------------------------------------------------- decisions
def decision_id(conv: Conversation, cand: CandidateDecision) -> str:
    return "D-" + sha256_hex(conv.source_file, conv.id, cand.message_id, cand.question, length=8)


def stage_decision(
    vault: Vault,
    cand: CandidateDecision,
    conv: Conversation,
    by_message_id: dict[str, Message],
    model: str | None,
    stats: MergeStats,
) -> None:
    from ..decide.store import DecisionStore

    store = DecisionStore(vault)
    did = decision_id(conv, cand)
    if (store.confirmed_dir / f"{did}.md").exists() or did in store.rejected():
        return  # confirmed, superseded or rejected by a person; never re-stage
    msg = by_message_id.get(cand.message_id)
    decision = Decision(
        id=did,
        question=cand.question.strip(),
        options=[o.strip() for o in cand.options],
        chosen=cand.chosen.strip(),
        reasoning=cand.reasoning.strip(),
        assumptions=[Assumption(text=a.strip()) for a in cand.assumptions],
        decider=cand.decider,
        source=source_ref(msg) if msg else None,
        status="staged",
        decided_on=msg.ts.date() if msg and msg.ts else None,
        provenance=llm_provenance(model),
    )
    path = store.staged_dir / f"{did}.md"
    res = vault.write_text(path, render_decision(decision, msg.span if msg else None))
    if res.created:
        stats.decisions_staged += 1
    stats.note(vault, path, res.changed)


# --------------------------------------------------------------- questions
def upsert_question(
    vault: Vault,
    q: OpenQuestion,
    conv: Conversation,
    by_message_id: dict[str, Message],
    model: str | None,
    stats: MergeStats,
) -> None:
    slug = slugify(q.text, max_len=80)
    path = vault.root / "questions" / f"{slug}.md"
    if path.exists():
        stats.note(vault, path, False)
        return
    msg = by_message_id.get(q.message_id)
    refs = [source_ref(msg)] if msg else []
    line = tag_line(q.text.strip(), "llm", msg.span) if msg else unverified_line(q.text.strip())
    body = (
        "\n".join(
            [
                f"# {q.text.strip()}",
                "",
                BANNER,
                "",
                "Status: open",
                "",
                f"- {line}",
                "",
                "## Sources",
                conversation_source_line(conv),
            ]
        )
        + "\n"
    )
    page = Page(
        id=slug,
        title=q.text.strip(),
        kind="question",
        tags=["afterthought", "question", "open"],
        sources=refs,
        provenance=llm_provenance(model).model_copy(update={"created": _min_date(refs)}),
        updated=_max_date(refs),
        links=extract_wikilinks(body),
        body=body,
    )
    res = vault.write_text(path, render_page(page))
    stats.questions += 1
    stats.note(vault, path, res.changed)


# ---------------------------------------------------------------- timeline
def upsert_timeline(
    vault: Vault,
    conv: Conversation,
    extraction: Extraction,
    new_messages: list[Message],
    entity_names: list[str],
    decision_ids: list[str],
    model: str | None,
    stats: MergeStats,
) -> None:
    day = timeline_name(conv.started)
    path = vault.root / "timeline" / f"{day}.md"
    page = read_page(path) if path.exists() else None
    heading = f"{conv.title} ({slugify(conv.id, max_len=24) or 'conv'})"
    first = new_messages[0] if new_messages else None
    summary = (
        tag_line(extraction.summary.strip(), "llm", first.span)
        if first
        else unverified_line(extraction.summary)
    )
    section = [
        f"## {heading}",
        f"- {summary}",
        f"- Source: {conv.source_file} ({conv.format}), {len(conv.messages)} messages",
    ]
    if entity_names:
        section.append("- Entities: " + ", ".join(wikilink(n) for n in sorted(entity_names)))
    if decision_ids:
        section.append("- Decisions: " + ", ".join(f"[[{d}]]" for d in sorted(decision_ids)))

    from ..pages import split_sections

    _, sections = split_sections(page.body if page else "")
    kept = [(h, c) for h, c in sections if h != heading]
    kept.append((heading, "\n".join(section[1:])))
    kept.sort(key=lambda hc: hc[0].lower())
    body_parts = [f"# {day}", "", BANNER]
    for h, c in kept:
        body_parts += ["", f"## {h}", c]
    body = "\n".join(body_parts) + "\n"
    refs = merge_sources(page.sources if page else [], [source_ref(m) for m in new_messages])
    new_page = Page(
        id=day,
        title=day,
        kind="timeline",
        tags=["afterthought", "timeline"],
        sources=refs,
        provenance=(page.provenance if page else llm_provenance(model)).model_copy(
            update={"created": _min_date(refs)}
        ),
        updated=_max_date(refs),
        links=extract_wikilinks(body),
        body=body,
    )
    res = vault.write_text(path, render_page(new_page))
    stats.note(vault, path, res.changed)


# ------------------------------------------------------------------- index
def rebuild_index(vault: Vault, stats: MergeStats) -> None:
    groups: dict[str, list[str]] = {}
    for p in vault.pages():
        rel = vault.rel(p)
        top = rel.split("/")[0]
        if top == "entities":
            top = rel.split("/")[1]
        if rel.startswith("decisions/staged/"):
            top = "decisions (staged)"
        fm, _ = split_frontmatter(p.read_text(encoding="utf-8"))
        title = str(fm.get("title") or p.stem)
        groups.setdefault(top, []).append(f"- [[{rel[:-3]}|{title}]]")
    lines = [
        "# Afterthought vault",
        "",
        "Generated by `afterthought compile`. Edit pages freely; "
        "managed sections are rebuilt on the next run.",
        "",
    ]
    for top in sorted(groups):
        lines += [f"## {top.capitalize()}"] + sorted(groups[top]) + [""]
    page = Page(
        id="index",
        title="Afterthought vault",
        kind="index",
        tags=["afterthought", "index"],
        provenance=system_provenance(),
        links=[ln.split("[[")[1].split("|")[0] for g in groups.values() for ln in g],
        body="\n".join(lines).rstrip("\n") + "\n",
    )
    path = vault.root / "index.md"
    res = vault.write_text(path, render_page(page))
    stats.note(vault, path, res.changed)
