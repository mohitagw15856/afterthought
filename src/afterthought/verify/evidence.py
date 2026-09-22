"""Evidence index built from the vault: every model-written line that resolves
to a source, and every line a person wrote on a page they own."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..pages import WIKILINK_RE, split_frontmatter
from ..provenance import parse_tag
from ..schemas import SourceRef
from ..vault import Vault

STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "it",
    "its",
    "this",
    "that",
    "as",
    "at",
    "by",
    "from",
    "will",
    "has",
    "have",
    "had",
    "not",
    "than",
    "then",
    "so",
    "but",
    "if",
    "into",
    "per",
    "about",
    "which",
    "who",
    "her",
    "his",
    "their",
    "user",
    "users",
    "s",
}
TOKEN_RE = re.compile(r"[a-z0-9]+")
TAG_RE = re.compile(r"\s\^at-[A-Za-z0-9-]+$")


def plain_text(line: str) -> str:
    """Bullet line to plain sentence: drop the bullet, the block id and wikilink syntax."""
    line = line.strip()
    if line.startswith("- "):
        line = line[2:]
    line = re.sub(r"^\[[ x!?]\] ", "", line)
    line = TAG_RE.sub("", line)
    line = WIKILINK_RE.sub(lambda m: m.group(0).split("|")[-1].rstrip("]") if "|" in m.group(0) else m.group(1), line)
    return line.strip()


def tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 1}


@dataclass
class Evidence:
    page: str  # vault-relative path without .md
    block: str | None  # block id, without the caret
    text: str
    source: SourceRef | None
    origin: str  # llm | human

    @property
    def link(self) -> str:
        return f"[[{self.page}#^{self.block}]]" if self.block else f"[[{self.page}]]"

    def describe(self) -> str:
        if self.source:
            when = self.source.date.strftime("%Y-%m-%d") if self.source.date else "undated"
            return f"{self.link} ({self.source.file}, message {self.source.message_id}, {when})"
        return f"{self.link} (written by a person)"


def build_index(vault: Vault) -> list[Evidence]:
    out: list[Evidence] = []
    for path in vault.pages():
        rel = vault.rel(path)
        if rel.startswith(("claims/", "timeline/", "shared/", "coach/", "runs/")):
            continue
        fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
        spans: dict[str, SourceRef] = {}
        for s in fm.get("sources") or []:
            try:
                ref = SourceRef.model_validate(s)
                spans[ref.span] = ref
            except Exception:
                continue
        if fm.get("source"):
            try:
                ref = SourceRef.model_validate(fm["source"])
                spans[ref.span] = ref
            except Exception:
                pass
        origin = (fm.get("provenance") or {}).get("origin", "llm")
        page = rel[:-3]
        for line in body.splitlines():
            if not line.startswith("- ") or line.startswith("- (") or line.startswith("- [["):
                continue
            tag = parse_tag(line)
            text = plain_text(line)
            if not text or text.startswith("UNVERIFIED:"):
                continue
            if tag:
                kind, rest = tag
                if kind != "llm":
                    continue
                base, _, suffix = rest.rpartition("-")
                span = base if suffix.isdigit() else rest
                source = spans.get(span)
                if source is None:
                    continue
                out.append(Evidence(page, f"at-{kind}-{rest}", text, source, "llm"))
            elif origin == "human":
                out.append(Evidence(page, None, text, None, "human"))
    return out


def score(claim: str, evidence: str) -> float:
    a, b = tokens(claim), tokens(evidence)
    if not a or not b:
        return 0.0
    shared = a & b
    if len(shared) < 3:
        return 0.0
    return len(shared) / len(a | b)


def best_match(claim: str, index: list[Evidence], threshold: float = 0.5) -> Evidence | None:
    ranked = sorted(((score(claim, e.text), e) for e in index), key=lambda t: t[0], reverse=True)
    if ranked and ranked[0][0] >= threshold:
        return ranked[0][1]
    return None


def candidates(claim: str, index: list[Evidence], k: int = 8) -> list[Evidence]:
    ranked = sorted(((score(claim, e.text), e) for e in index), key=lambda t: t[0], reverse=True)
    return [e for s, e in ranked[:k] if s > 0]
