"""Read-only subscriptions: clone a shared repo and mirror its pages into vault/shared/<name>/."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from ..vault import Vault
from . import git

MIRRORED = ("canonical", "conflicts", "by")


@dataclass
class PullReport:
    name: str
    action: str
    head: str | None
    files: int = 0
    removed: int = 0
    changed: list[str] = field(default_factory=list)


def clone_dir(vault: Vault, name: str) -> Path:
    return vault.meta / "subscriptions" / name


def mirror_dir(vault: Vault, name: str) -> Path:
    return vault.root / "shared" / name


def subscribe(vault: Vault, url: str, name: str | None = None) -> PullReport:
    name = name or Path(url.rstrip("/")).stem.removesuffix(".git") or "team"
    cfg = vault.config()
    subs = cfg.setdefault("share", {}).setdefault("subscriptions", {})
    subs[name] = url
    vault.save_config(cfg)
    return pull_one(vault, name, url)


def pull_one(vault: Vault, name: str, url: str) -> PullReport:
    clone = clone_dir(vault, name)
    action = git.clone_or_pull(url, clone)
    report = PullReport(name=name, action=action, head=git.head(clone))
    mirror = mirror_dir(vault, name)
    wanted: dict[Path, Path] = {}
    for top in MIRRORED:
        src_top = clone / top
        if not src_top.exists():
            continue
        for src in src_top.rglob("*.md"):
            wanted[mirror / src.relative_to(clone)] = src
    # remove files that vanished upstream
    if mirror.exists():
        for existing in mirror.rglob("*.md"):
            if existing not in wanted:
                existing.chmod(0o644)
                existing.unlink()
                report.removed += 1
    for dest, src in sorted(wanted.items()):
        text = src.read_text(encoding="utf-8")
        if dest.exists() and dest.read_text(encoding="utf-8") == text:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.chmod(0o644)
        dest.write_text(text, encoding="utf-8")
        report.changed.append(vault.rel(dest))
    for dest in wanted:
        os.chmod(dest, 0o444)
    report.files = len(wanted)
    # tidy empty folders
    if mirror.exists():
        for d in sorted((p for p in mirror.rglob("*") if p.is_dir()), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
    return report


def pull_subscriptions(vault: Vault, only: str | None = None) -> list[PullReport]:
    subs = vault.config().get("share", {}).get("subscriptions", {})
    out = []
    for name, url in sorted(subs.items()):
        if only and name != only:
            continue
        out.append(pull_one(vault, name, url))
    return out


def unsubscribe(vault: Vault, name: str) -> bool:
    cfg = vault.config()
    subs = cfg.get("share", {}).get("subscriptions", {})
    if name not in subs:
        return False
    del subs[name]
    vault.save_config(cfg)
    for d in (mirror_dir(vault, name), clone_dir(vault, name)):
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file():
                    f.chmod(0o644)
            shutil.rmtree(d)
    return True
