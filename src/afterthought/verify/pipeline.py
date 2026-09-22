"""verify pipeline: text -> claims -> tags -> claims page, annotated copy, JSON."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..llm.base import LLMProvider
from ..pages import split_frontmatter
from ..redact import redact
from ..schemas import Claim
from ..util import sha256_hex, slugify
from ..vault import Vault
from .evidence import Evidence, best_match, build_index, candidates
from .extract import ClaimExtraction, DemandResult, demand_request, extract_request
from .render import annotate, render_claims_page


@dataclass
class VerifyReport:
    slug: str
    claims: list[Claim] = field(default_factory=list)
    unlocated: list[Claim] = field(default_factory=list)
    llm_calls: int = 0
    evidence_items: int = 0
    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    redactions: int = 0
    annotated: str = ""

    def counts(self) -> dict[str, int]:
        return {t: sum(1 for c in self.claims if c.tag == t) for t in ("SOURCED", "INFERRED", "UNVERIFIED")}


def locate(text: str, quote: str) -> tuple[int, int]:
    if not quote:
        return (0, 0)
    i = text.find(quote)
    if i < 0:
        i = text.lower().find(quote.lower())
    if i < 0:
        pattern = r"\s+".join(re.escape(w) for w in quote.split())
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return (m.start(), m.end())
        return (0, 0)
    return (i, i + len(quote))


def read_input(path: Path | None, stdin_text: str | None) -> tuple[str, str, str]:
    """Return (text, slug, display name). Frontmatter is stripped from pages."""
    if path is None:
        text = stdin_text or ""
        return text, f"stdin-{sha256_hex(text, length=8)}", "stdin"
    raw = path.read_text(encoding="utf-8")
    _, body = split_frontmatter(raw)
    return body, slugify(path.stem), path.name


def verify_text(
    vault: Vault,
    text: str,
    *,
    slug: str,
    source_name: str,
    provider: LLMProvider,
    demand: bool = False,
    write: bool = True,
) -> VerifyReport:
    if not vault.exists():
        vault.init()
    report = VerifyReport(slug=slug)
    text, rep = redact(text, allow_emails=tuple(vault.config().get("redact", {}).get("allow_emails", [])))
    report.redactions = rep.total
    text_hash = sha256_hex(text)

    extraction = provider.complete_structured(extract_request(text, slug), ClaimExtraction)
    report.llm_calls += 1
    model = provider.model

    index = build_index(vault)
    report.evidence_items = len(index)
    claims: list[Claim] = []
    for i, ec in enumerate(e for e in extraction.claims if e.kind == "factual"):
        claim = Claim(
            id=f"C-{sha256_hex(text_hash, str(i), length=8)}",
            text=ec.text.strip(),
            quote=ec.quote,
            span=locate(text, ec.quote),
        )
        match = best_match(claim.text, index)
        if match is not None:
            claim = claim.model_copy(update={"tag": "SOURCED", "evidence": match.link, "citation": match.source})
        claims.append(claim)

    if demand and claims:
        cand_lists: list[list[Evidence]] = [candidates(c.text, index) for c in claims]
        flat: list[Evidence] = []
        seen: set[str] = set()
        for lst in cand_lists:
            for e in lst:
                if e.link not in seen:
                    seen.add(e.link)
                    flat.append(e)
        result = provider.complete_structured(
            demand_request([c.text for c in claims], [f"{e.text} ({e.link})" for e in flat], slug),
            DemandResult,
        )
        report.llm_calls += 1
        by_claim = {v.claim_index: v for v in result.verdicts}
        for i, c in enumerate(claims):
            v = by_claim.get(i)
            upd: dict = {"demanded": True}
            if v is None:
                pass
            elif v.verdict == "sourced" and v.evidence_index is not None and 0 <= v.evidence_index < len(flat):
                e = flat[v.evidence_index]
                upd.update({"tag": "SOURCED", "evidence": e.link, "citation": e.source, "reasoning": None})
            elif v.verdict == "inferred" and v.reasoning and v.reasoning.strip():
                if c.tag != "SOURCED":
                    upd.update({"tag": "INFERRED", "reasoning": v.reasoning.strip()})
            # anything else stays as matched (SOURCED) or UNVERIFIED; an invalid citation never counts
            claims[i] = c.model_copy(update=upd)

    report.claims = claims
    annotated, report.unlocated = annotate(text, claims)
    if report.unlocated:
        annotated = (
            annotated.rstrip("\n")
            + "\n\nClaims not located in the text:\n"
            + "\n".join(f"- {c.text} [{c.tag}]" for c in report.unlocated)
            + "\n"
        )

    if write:
        base = vault.root / "claims" / slug
        results = [
            vault.write_text(
                base.with_suffix(".claims.md"),
                render_claims_page(slug, source_name, source_name, claims, model, demand),
            ),
            vault.write_text(base.with_suffix(".annotated.md"), annotated),
            vault.write_json(base.with_suffix(".claims.json"), [c.model_dump(mode="json") for c in claims]),
        ]
        for r in results:
            (report.written if r.changed else report.unchanged).append(vault.rel(r.path))
    report.annotated = annotated
    return report


def claims_json(claims: list[Claim]) -> str:
    return json.dumps([c.model_dump(mode="json") for c in claims], indent=2, ensure_ascii=False)
