"""Claims table page and annotated copy."""

from __future__ import annotations

from ..pages import render_page
from ..schemas import Claim, Page, Provenance

LEGEND = (
    "SOURCED: matches a fact in this vault that resolves to a source. "
    "INFERRED: follows from vault evidence by the reasoning shown. "
    "UNVERIFIED: no evidence found; the default."
)


def marker(c: Claim) -> str:
    if c.tag == "SOURCED" and c.evidence:
        return f"[SOURCED: {c.evidence}]"
    if c.tag == "INFERRED":
        return "[INFERRED]"
    return "[UNVERIFIED]"


def annotate(text: str, claims: list[Claim]) -> tuple[str, list[Claim]]:
    """Insert a marker after each located quote. Returns the text and the unlocated claims."""
    located = [c for c in claims if c.span != (0, 0)]
    unlocated = [c for c in claims if c.span == (0, 0)]
    out = text
    for c in sorted(located, key=lambda c: c.span[1], reverse=True):
        end = c.span[1]
        out = out[:end] + " " + marker(c) + out[end:]
    return out, unlocated


def render_claims_page(
    slug: str, title: str, source_name: str, claims: list[Claim], model: str | None, demanded: bool
) -> str:
    counts = {t: sum(1 for c in claims if c.tag == t) for t in ("SOURCED", "INFERRED", "UNVERIFIED")}
    lines = [f"# Claims: {title}", "", f"Input: {source_name}", f"Mode: {'demand' if demanded else 'match'}", ""]
    lines.append(
        f"{len(claims)} claims: {counts['SOURCED']} sourced, "
        f"{counts['INFERRED']} inferred, {counts['UNVERIFIED']} unverified."
    )
    lines += ["", LEGEND, "", "| # | Tag | Claim | Evidence |", "|---|---|---|---|"]
    for i, c in enumerate(claims):
        if c.tag == "SOURCED":
            ev = c.evidence or ""
            if c.citation:
                when = c.citation.date.strftime("%Y-%m-%d") if c.citation.date else "undated"
                ev += f" ({c.citation.file}, {c.citation.message_id}, {when})"
        elif c.tag == "INFERRED":
            ev = (c.reasoning or "").replace("|", "\\|")
        else:
            ev = ""
        lines.append(f"| {i} | {c.tag} | {c.text.replace('|', chr(92) + '|')} | {ev} |")
    page = Page(
        id=slug,
        title=f"Claims: {title}",
        kind="claims",
        tags=["afterthought", "claims"],
        provenance=Provenance(origin="llm", tool="afterthought.verify", model=model),
        links=[c.evidence.strip("[]").split("#")[0] for c in claims if c.evidence],
        body="\n".join(lines) + "\n",
    )
    return render_page(page)
