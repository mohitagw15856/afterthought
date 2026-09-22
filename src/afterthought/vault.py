"""Vault on disk: layout, discovery, atomic and idempotent writes."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ignore import DEFAULT_IGNORE, IGNORE_FILENAME, IgnoreRules
from .redact import redact

ENV_VAR = "AFTERTHOUGHT_VAULT"
CONFIG_NAME = "config.json"

LAYOUT = {
    "entities/projects": "One page per project.",
    "entities/people": "One page per person.",
    "entities/tools": "One page per tool or library.",
    "entities/concepts": "One page per concept.",
    "decisions": "Confirmed decisions.",
    "decisions/staged": "Decisions extracted from chats, awaiting confirmation.",
    "questions": "Open questions surfaced from conversations.",
    "timeline": "One page per day of activity.",
    "sources": "Index of ingested inputs.",
    "claims": "Verify outputs.",
    "runs": "Replay recordings.",
    "coach": "Curriculum and progress.",
    "shared": "Read-only subscriptions to other people's published pages.",
}

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "user": None,
    "llm": {"provider": "anthropic", "model": "claude-opus-5", "fixtures": None},
    "redact": {"allow_emails": []},
}


@dataclass
class WriteResult:
    path: Path
    changed: bool
    created: bool


class Vault:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # ------------------------------------------------------------ discovery
    @classmethod
    def resolve(cls, explicit: Path | None = None) -> Vault:
        if explicit is not None:
            return cls(explicit)
        env = os.environ.get(ENV_VAR)
        if env:
            return cls(Path(env))
        return cls(Path.cwd() / "vault")

    @property
    def meta(self) -> Path:
        return self.root / ".afterthought"

    @property
    def config_path(self) -> Path:
        return self.meta / CONFIG_NAME

    @property
    def state_dir(self) -> Path:
        return self.meta / "state"

    @property
    def cache_dir(self) -> Path:
        return self.meta / "cache" / "llm"

    def exists(self) -> bool:
        return self.config_path.exists()

    # ------------------------------------------------------------------ init
    def init(self, user: str | None = None) -> list[Path]:
        created: list[Path] = []
        for rel in LAYOUT:
            d = self.root / rel
            if not d.exists():
                d.mkdir(parents=True)
                created.append(d)
        for d in (self.state_dir, self.cache_dir):
            d.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            cfg = json.loads(json.dumps(DEFAULT_CONFIG))
            cfg["user"] = user
            self.write_json(self.config_path, cfg)
            created.append(self.config_path)
        ignore = self.root / IGNORE_FILENAME
        if not ignore.exists():
            ignore.write_text(DEFAULT_IGNORE, encoding="utf-8")
            created.append(ignore)
        return created

    # ---------------------------------------------------------------- config
    def config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return json.loads(json.dumps(DEFAULT_CONFIG))
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def ignore_rules(self) -> IgnoreRules:
        return IgnoreRules.load(self.root)

    # ---------------------------------------------------------------- writes
    def write_text(self, path: Path, text: str, *, redact_output: bool = True) -> WriteResult:
        """Write only if content differs. Redacts before writing."""
        if redact_output:
            allow = tuple(self.config().get("redact", {}).get("allow_emails", []))
            text, _ = redact(text, allow_emails=allow)
        path.parent.mkdir(parents=True, exist_ok=True)
        created = not path.exists()
        if not created and path.read_text(encoding="utf-8") == text:
            return WriteResult(path, changed=False, created=False)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        return WriteResult(path, changed=True, created=created)

    def write_json(self, path: Path, data: Any) -> WriteResult:
        text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        return self.write_text(path, text, redact_output=False)

    def read_json(self, path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- lookup
    def pages(self, subdir: str = "") -> list[Path]:
        base = self.root / subdir if subdir else self.root
        if not base.exists():
            return []
        return sorted(p for p in base.rglob("*.md") if ".afterthought" not in p.parts and p.name != "index.md")

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()
