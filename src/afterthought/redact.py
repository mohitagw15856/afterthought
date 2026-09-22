"""Redaction pass for secrets and personal data.

Runs before extraction (so no model ever sees the raw value) and again on
every vault write and publish. Replacement markers are stable so re-running
is idempotent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])")
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
TOKEN_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"[sp]k_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[abpr]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-.=]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(?i)(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{12,})"
    ),
]
MARKER_RE = re.compile(r"\[REDACTED:(email|card|token)\]")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


@dataclass
class RedactionReport:
    emails: int = 0
    cards: int = 0
    tokens: int = 0
    samples: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.emails + self.cards + self.tokens


def redact(text: str, allow_emails: tuple[str, ...] = ()) -> tuple[str, RedactionReport]:
    """Return redacted text and a count of what was replaced."""
    report = RedactionReport()
    if not text:
        return text, report

    def _email(m: re.Match[str]) -> str:
        if m.group(0).lower() in {a.lower() for a in allow_emails}:
            return m.group(0)
        report.emails += 1
        return "[REDACTED:email]"

    def _card(m: re.Match[str]) -> str:
        digits = re.sub(r"[ -]", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            report.cards += 1
            return "[REDACTED:card]"
        return m.group(0)

    def _token(m: re.Match[str]) -> str:
        report.tokens += 1
        if m.lastindex:
            # keep the key name, drop the value
            return m.group(0)[: m.start(1) - m.start(0)] + "[REDACTED:token]"
        return "[REDACTED:token]"

    for pat in TOKEN_PATTERNS:
        text = pat.sub(_token, text)
    text = EMAIL_RE.sub(_email, text)
    text = CARD_RE.sub(_card, text)
    return text, report


def contains_unredacted(text: str) -> bool:
    """True if a redaction pass would still change the text."""
    redacted, report = redact(text)
    return report.total > 0
