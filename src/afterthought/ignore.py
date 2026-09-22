"""`.afterthoughtignore`: gitignore-style patterns applied to inputs and to
pages before publishing. Deliberately small; supports comments, `dir/`
prefixes, `*`, `**` and negation with `!`.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path, PurePosixPath

IGNORE_FILENAME = ".afterthoughtignore"

DEFAULT_IGNORE = """# Afterthought ignore rules (gitignore syntax, matched against relative paths)
# Files and pages matching these patterns are never ingested or published.
*.env
*.pem
*.key
**/secrets/**
private/**
"""


class IgnoreRules:
    def __init__(self, patterns: list[str]) -> None:
        self.patterns = [p.strip() for p in patterns if p.strip() and not p.startswith("#")]

    @classmethod
    def load(cls, root: Path) -> IgnoreRules:
        f = root / IGNORE_FILENAME
        if not f.exists():
            return cls([])
        return cls(f.read_text(encoding="utf-8").splitlines())

    def _match_one(self, pattern: str, rel: str) -> bool:
        parts = PurePosixPath(rel).parts
        if pattern.endswith("/"):
            pattern = pattern.rstrip("/") + "/**"
        if "/" not in pattern.rstrip("/"):
            # bare name matches any path component or the basename
            return any(fnmatch.fnmatchcase(p, pattern) for p in parts)
        pattern = pattern.lstrip("/")
        if fnmatch.fnmatchcase(rel, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatchcase(rel, pattern[3:]):
            return True
        # `dir/**` should also match `dir/file`
        if pattern.endswith("/**") and rel.startswith(pattern[:-3] + "/"):
            return True
        return False

    def is_ignored(self, rel_path: str | Path) -> bool:
        rel = PurePosixPath(str(rel_path)).as_posix().lstrip("./")
        ignored = False
        for pat in self.patterns:
            negate = pat.startswith("!")
            p = pat[1:] if negate else pat
            if self._match_one(p, rel):
                ignored = not negate
        return ignored
