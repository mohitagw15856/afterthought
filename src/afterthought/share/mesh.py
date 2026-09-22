"""The shared repository layout and the publish algorithm.

    shared-repo/
      by/<publisher>/<vault path>.md   every publisher's own version; only they overwrite it
      canonical/<vault path>.md        the first publisher's version, kept until reconciled
      conflicts/<vault path>.md        diff page, present while publishers' versions differ
      manifest.json                    what is published, by whom, when, from what
      README.md

A published page keeps its original frontmatter and gains a `shared` block:
publisher, tool, published (UTC), source_hash and derived_from (the original
provenance). Re-publishing an unchanged page changes nothing.
"""

from __future__ import annotations

import difflib
import fnmatch
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import __version__
from ..pages import dump_frontmatter, split_frontmatter
from ..redact import redact
from ..util import sha256_hex, slugify
from ..vault import Vault
from . import git

NEVER_PUBLISH = ("claims/", "runs/", "coach/", "shared/", "decisions/staged/", "sources/", ".afterthought/")
README = """# Shared Afterthought pages

Published with `afterthought share publish`. Layout:

- `by/<publisher>/...` each person's own version of a page. Only they change it.
- `canonical/...` the first published version of each page. It is never overwritten by someone else.
- `conflicts/...` a diff page for every path where publishers disagree. Reconcile by publishing matching versions.
- `manifest.json` who published what, when, and from which tool.

Pull these into your own vault with `afterthought share subscribe <this repo>`.
"""


@dataclass
class PublishReport:
    published: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)
    commit: str | None = None
    pushed: bool = False


def stamp_text(text: str, stamp: dict[str, Any]) -> str:
    fm, body = split_frontmatter(text)
    fm = dict(fm)
    fm["shared"] = stamp
    return f"---\n{dump_frontmatter(fm)}---\n{body}"


def unstamped(text: str) -> str:
    fm, body = split_frontmatter(text)
    fm = {k: v for k, v in fm.items() if k != "shared"}
    return (f"---\n{dump_frontmatter(fm)}---\n" if fm else "") + body


def content_hash(text: str) -> str:
    return sha256_hex(unstamped(text), length=16)


class SharedRepo:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    # ---------------------------------------------------------------- setup
    @classmethod
    def init(cls, path: Path, user: str) -> SharedRepo:
        repo = cls(path)
        git.init(repo.path)
        readme = repo.path / "README.md"
        if not readme.exists():
            readme.write_text(README, encoding="utf-8")
        if not repo.manifest_path.exists():
            repo.write_manifest({"version": 1, "pages": {}})
        git.commit_all(repo.path, "share: initialise shared repository", user)
        return repo

    @property
    def manifest_path(self) -> Path:
        return self.path / "manifest.json"

    def manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"version": 1, "pages": {}}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def write_manifest(self, data: dict[str, Any]) -> None:
        self.manifest_path.write_text(
            json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    # ---------------------------------------------------------------- paths
    def by_path(self, publisher: str, rel: str) -> Path:
        return self.path / "by" / slugify(publisher) / rel

    def canonical_path(self, rel: str) -> Path:
        return self.path / "canonical" / rel

    def conflict_path(self, rel: str) -> Path:
        return self.path / "conflicts" / rel

    def versions(self, rel: str) -> list[tuple[str, Path]]:
        by = self.path / "by"
        if not by.exists():
            return []
        out = []
        for d in sorted(p for p in by.iterdir() if p.is_dir()):
            p = d / rel
            if p.exists():
                out.append((d.name, p))
        return out

    # -------------------------------------------------------------- publish
    def publish(
        self,
        vault: Vault,
        rels: list[str],
        *,
        user: str,
        push: bool = False,
        now: datetime | None = None,
    ) -> PublishReport:
        report = PublishReport()
        rules = vault.ignore_rules()
        allow = tuple(vault.config().get("redact", {}).get("allow_emails", []))
        manifest = self.manifest()
        pages = manifest.setdefault("pages", {})
        now = now or datetime.now(UTC)

        for rel in rels:
            if rel.startswith(NEVER_PUBLISH) or rules.is_ignored(rel):
                report.skipped.append(rel)
                continue
            src = vault.root / rel
            if not src.exists():
                report.skipped.append(rel)
                continue
            text, _ = redact(src.read_text(encoding="utf-8"), allow_emails=allow)
            h = content_hash(text)
            fm, _ = split_frontmatter(text)
            mine = self.by_path(user, rel)
            if mine.exists() and content_hash(mine.read_text(encoding="utf-8")) == h:
                report.unchanged.append(rel)
                continue
            stamp = {
                "publisher": user,
                "tool": f"afterthought {__version__}",
                "published": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_hash": h,
                "derived_from": fm.get("provenance") or {"origin": "unknown"},
            }
            mine.parent.mkdir(parents=True, exist_ok=True)
            mine.write_text(stamp_text(text, stamp), encoding="utf-8")
            entry = pages.setdefault(rel, {"versions": {}})
            entry["versions"][slugify(user)] = {k: v for k, v in stamp.items() if k != "derived_from"} | {
                "derived_from": stamp["derived_from"]
            }
            report.published.append(rel)
            self._reconcile(rel, entry, report)

        if report.published:
            self.write_manifest(manifest)
            report.commit = git.commit_all(self.path, f"share: {user} published {len(report.published)} page(s)", user)
            if push and git.has_remote(self.path):
                git.push(self.path)
                report.pushed = True
        return report

    def _reconcile(self, rel: str, entry: dict[str, Any], report: PublishReport) -> None:
        versions = self.versions(rel)
        canonical = self.canonical_path(rel)
        conflict = self.conflict_path(rel)
        if not versions:
            return
        # earliest publisher owns canonical
        stamps = {pub: split_frontmatter(p.read_text(encoding="utf-8"))[0].get("shared", {}) for pub, p in versions}
        earliest = min(versions, key=lambda v: (stamps[v[0]].get("published", ""), v[0]))
        hashes = {pub: content_hash(p.read_text(encoding="utf-8")) for pub, p in versions}
        distinct = set(hashes.values())
        canonical.parent.mkdir(parents=True, exist_ok=True)
        if not canonical.exists() or content_hash(canonical.read_text(encoding="utf-8")) not in distinct:
            canonical.write_text(earliest[1].read_text(encoding="utf-8"), encoding="utf-8")
        entry["canonical"] = earliest[0]
        if len(distinct) > 1:
            conflict.parent.mkdir(parents=True, exist_ok=True)
            conflict.write_text(self._conflict_page(rel, versions, stamps, hashes, earliest[0]), encoding="utf-8")
            entry["conflict"] = True
            report.conflicts.append(rel)
        else:
            if conflict.exists():
                conflict.unlink()
                report.resolved.append(rel)
            entry.pop("conflict", None)
            # everyone agrees: canonical follows the agreed content
            canonical.write_text(earliest[1].read_text(encoding="utf-8"), encoding="utf-8")

    def _conflict_page(self, rel: str, versions, stamps, hashes, base_pub: str) -> str:
        base_text = unstamped(next(p for pub, p in versions if pub == base_pub).read_text(encoding="utf-8"))
        fm = {
            "title": f"Conflict: {rel}",
            "kind": "conflict",
            "path": rel,
            "canonical": base_pub,
            "versions": [
                {"publisher": pub, "published": stamps[pub].get("published"), "hash": hashes[pub]}
                for pub, _ in versions
            ],
            "tags": ["afterthought", "conflict"],
        }
        lines = [
            f"# Conflict on {rel}",
            "",
            "Publishers hold different versions of this page. The canonical copy stays with the earliest publisher "
            "until the others publish a matching version or a person merges them by hand.",
            "",
            "## Versions",
        ]
        for pub, _ in versions:
            mark = " (canonical)" if pub == base_pub else ""
            lines.append(f"- [[by/{pub}/{rel[:-3]}|{pub}]] published {stamps[pub].get('published', 'unknown')}{mark}")
        for pub, p in versions:
            if pub == base_pub:
                continue
            other = unstamped(p.read_text(encoding="utf-8"))
            diff = difflib.unified_diff(
                base_text.splitlines(),
                other.splitlines(),
                fromfile=f"by/{base_pub}/{rel}",
                tofile=f"by/{pub}/{rel}",
                lineterm="",
                n=2,
            )
            lines += ["", f"## Diff: {base_pub} vs {pub}", "", "```diff", *diff, "```"]
        return f"---\n{dump_frontmatter(fm)}---\n" + "\n".join(lines) + "\n"

    # --------------------------------------------------------------- status
    def status(self) -> dict[str, Any]:
        m = self.manifest()
        pages = m.get("pages", {})
        publishers: dict[str, int] = {}
        for entry in pages.values():
            for pub in entry.get("versions", {}):
                publishers[pub] = publishers.get(pub, 0) + 1
        return {
            "path": str(self.path),
            "head": git.head(self.path),
            "pages": len(pages),
            "conflicts": sorted(rel for rel, e in pages.items() if e.get("conflict")),
            "publishers": publishers,
        }


def select_pages(vault: Vault, patterns: list[str], all_pages: bool) -> list[str]:
    rels = [vault.rel(p) for p in vault.pages()]
    rels.append("index.md") if (vault.root / "index.md").exists() else None
    if all_pages:
        return sorted(r for r in rels if not r.startswith(NEVER_PUBLISH))
    chosen: list[str] = []
    for pat in patterns:
        pat = pat.rstrip("/")
        matched = [r for r in rels if r == pat or fnmatch.fnmatch(r, pat) or r.startswith(pat + "/")]
        if not matched and (vault.root / pat).exists():
            matched = [pat]
        chosen += matched
    return sorted(set(chosen))
