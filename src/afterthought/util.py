"""Small pure helpers shared across modules."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 60) -> str:
    """Lower-case ASCII slug safe for file names and wikilinks."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = _SLUG_RE.sub("-", norm.lower()).strip("-")
    if len(slug) > max_len:
        cut = slug[:max_len]
        slug = cut[: cut.rfind("-")] if "-" in cut else cut
    return slug.rstrip("-") or "untitled"


def sha256_hex(*parts: str, length: int = 12) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:length]


def parse_ts(value: float | int | str | None) -> datetime | None:
    """Best-effort timestamp parsing. Returns None rather than guessing."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(float(value), tz=UTC)
        s = str(value).strip()
        if re.fullmatch(r"\d{10}(\.\d+)?", s):
            return datetime.fromtimestamp(float(s), tz=UTC)
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, OverflowError, OSError):
        return None


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def normalise_text(text: str) -> str:
    """Whitespace and case folded form used for de-duplication."""
    return re.sub(r"\s+", " ", text).strip().lower()
