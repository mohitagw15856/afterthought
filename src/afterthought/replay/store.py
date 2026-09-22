"""Runs on disk: runs/<id>/run.json, steps.jsonl, run.md, viewer.html."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..pages import render_page
from ..schemas import Page, Provenance, Run
from ..util import iso
from ..vault import Vault
from .diff import RunDiff, diff_runs
from .html import render_diff_html, render_run_html
from .parse import parse_run


@dataclass
class CaptureReport:
    run: Run
    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.written)


def run_page(run: Run) -> str:
    tools: dict[str, int] = {}
    for s in run.steps:
        if s.kind == "tool_call" and s.name:
            tools[s.name] = tools.get(s.name, 0) + 1
    counts = {
        k: sum(1 for s in run.steps if s.kind == k) for k in ("user", "assistant", "tool_call", "tool_result", "system")
    }
    lines = [f"# Run: {run.title or run.id}", "", f"Source: {run.source_file} ({run.source})"]
    lines.append(f"Started: {iso(run.started) or 'unknown'}; ended: {iso(run.ended) or 'unknown'}")
    lines.append(
        f"Steps: {len(run.steps)} (" + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in counts.items() if v) + ")"
    )
    if tools:
        lines.append("Tools: " + ", ".join(f"{n} x{c}" for n, c in sorted(tools.items())))
    lines += [
        "",
        "Open `viewer.html` in this folder to step through the run.",
        "",
        "## Outcome",
        run.outcome or "(no assistant output)",
        "",
        "## Steps",
        "",
        "| # | Kind | Tool | Preview |",
        "|---|---|---|---|",
    ]
    for s in run.steps:
        preview = s.content.replace("\n", " ").replace("|", "\\|")[:80]
        lines.append(f"| {s.index} | {s.kind} | {s.name or ''} | {preview} |")
    page = Page(
        id=run.id,
        title=f"Run: {run.title or run.id}",
        kind="run",
        tags=["afterthought", "run", run.source],
        provenance=Provenance(origin="import", tool="afterthought.replay", derived_from=run.provenance.derived_from),
        updated=run.ended,
        body="\n".join(lines) + "\n",
    )
    return render_page(page)


class RunStore:
    def __init__(self, vault: Vault) -> None:
        self.vault = vault

    @property
    def root(self) -> Path:
        return self.vault.root / "runs"

    def dir(self, run_id: str) -> Path:
        return self.root / run_id

    def list(self) -> list[Run]:
        if not self.root.exists():
            return []
        out = []
        for p in sorted(self.root.glob("*/run.json")):
            out.append(Run.model_validate_json(p.read_text(encoding="utf-8")))
        return sorted(out, key=lambda r: (r.started is None, r.started or 0, r.id))

    def get(self, run_id: str) -> Run:
        p = self.dir(run_id) / "run.json"
        if not p.exists():
            matches = (
                [d for d in self.root.glob(f"{run_id}*") if (d / "run.json").exists()] if self.root.exists() else []
            )
            if len(matches) == 1:
                p = matches[0] / "run.json"
            else:
                raise KeyError(f"No run {run_id!r} in {self.root}" + (f" ({len(matches)} matches)" if matches else ""))
        return Run.model_validate_json(p.read_text(encoding="utf-8"))

    def capture(self, path: Path, fmt: str | None = None, run_id: str | None = None) -> CaptureReport:
        run = parse_run(path, fmt, run_id)
        report = CaptureReport(run=run)
        d = self.dir(run.id)
        writes = [
            self.vault.write_text(d / "run.json", run.model_dump_json(indent=2) + "\n", redact_output=False),
            self.vault.write_text(
                d / "steps.jsonl", "".join(s.model_dump_json() + "\n" for s in run.steps), redact_output=False
            ),
            self.vault.write_text(d / "run.md", run_page(run)),
            self.vault.write_text(d / "viewer.html", render_run_html(run), redact_output=False),
        ]
        for w in writes:
            (report.written if w.changed else report.unchanged).append(self.vault.rel(w.path))
        return report

    def diff(self, a_id: str, b_id: str, write: bool = True) -> tuple[RunDiff, list[str]]:
        a, b = self.get(a_id), self.get(b_id)
        d = diff_runs(a, b)
        written: list[str] = []
        if write:
            out = self.root / f"{a.id}__vs__{b.id}"
            lines = [
                f"# Diff: {a.id} vs {b.id}",
                "",
                d.summary(),
                "",
                "Open `diff.html` in this folder to step through both runs side by side.",
                "",
                "## Changes",
            ]
            lines += [f"- {c.describe()}" for c in d.changes] or ["- none"]
            lines += ["", "## Outcomes", f"- A: {a.outcome or '(none)'}", f"- B: {b.outcome or '(none)'}"]
            page = Page(
                id=out.name,
                title=f"Diff: {a.id} vs {b.id}",
                kind="run",
                tags=["afterthought", "run", "diff"],
                provenance=Provenance(origin="system", tool="afterthought.replay", derived_from=[a.id, b.id]),
                body="\n".join(lines) + "\n",
            )
            for w in (
                self.vault.write_text(out / "diff.md", render_page(page)),
                self.vault.write_text(out / "diff.html", render_diff_html(d), redact_output=False),
                self.vault.write_text(
                    out / "diff.json",
                    json.dumps(
                        {
                            "pairs": d.pairs,
                            "changes": [c.describe() for c in d.changes],
                            "same_outcome": d.same_outcome,
                        },
                        indent=2,
                    )
                    + "\n",
                    redact_output=False,
                ),
            ):
                if w.changed:
                    written.append(self.vault.rel(w.path))
        return d, written
