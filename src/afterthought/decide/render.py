"""Render a Decision to a markdown page. Frontmatter is the source of truth;
the body is regenerated from it every time.

Model-extracted decisions (`provenance.origin == "llm"`) get a block id on
every model-written line, resolving to `span`. Human-recorded decisions carry
no tags.
"""

from __future__ import annotations

from ..pages import dump_frontmatter
from ..provenance import BANNER, tag_line, unverified_line
from ..schemas import Assumption, Decision

STATUS_BOX = {"open": "[ ]", "held": "[x]", "failed": "[!]", "unknown": "[?]"}
STATUS_HINT = {
    "staged": "staged (run `afterthought decide confirm <id>` to accept it, or `reject`)",
    "confirmed": "confirmed",
    "superseded": "superseded",
}


def assumption_line(a: Assumption) -> str:
    check = a.check_by.isoformat() if a.check_by else "unset"
    parts = [f"{STATUS_BOX[a.status]} {a.text} (confidence {a.confidence:.2f}, check by {check}"]
    if a.checked_on:
        parts.append(f", checked {a.checked_on.isoformat()}")
    parts.append(")")
    line = "".join(parts)
    if a.note:
        line += f" Note: {a.note}"
    return line


def render_decision(decision: Decision, span: str | None = None) -> str:
    llm = decision.provenance.origin == "llm"
    counter = {"n": 0}

    def tag(text: str) -> str:
        if not llm:
            return text
        if span is None:
            return unverified_line(text)
        counter["n"] += 1
        return tag_line(text, "llm", span, suffix=counter["n"] - 1)

    lines = [f"# {decision.question}", ""]
    if llm:
        lines += [BANNER, ""]
    lines.append(f"Status: {STATUS_HINT[decision.status]}")
    lines.append(f"Decided on: {decision.decided_on.isoformat() if decision.decided_on else 'unknown'}")
    lines.append(f"Decider: {decision.decider or 'unknown'}")
    lines += ["", "## Options"]
    lines += [f"- {tag(o)}" for o in decision.options] or ["- (none recorded)"]
    lines += ["", "## Chosen", f"- {tag(decision.chosen)}", "", "## Reasoning"]
    lines.append(tag(decision.reasoning) if decision.reasoning else "(none given)")
    lines += ["", "## Assumptions"]
    lines += [f"- {tag(assumption_line(a))}" for a in decision.assumptions] or ["- (none recorded)"]
    lines += ["", "## Source"]
    if decision.source:
        s = decision.source
        day = s.date.strftime("%Y-%m-%d") if s.date else "undated"
        lines.append(f"- [[timeline/{day}|{day}]] {s.file}, message {s.message_id or 'unknown'}")
    else:
        lines.append("- recorded by hand, no source conversation")

    fm = decision.model_dump(mode="json", exclude_none=True)
    fm = {
        "title": decision.question,
        "kind": "decision",
        **fm,
        "tags": ["afterthought", "decision", decision.status],
    }
    return f"---\n{dump_frontmatter(fm)}---\n" + "\n".join(lines) + "\n"
