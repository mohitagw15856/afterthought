"""Progress on the curriculum, and the feedback loop into the wiki."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from ..pages import extract_wikilinks, read_page, render_page, split_sections, unmanaged_sections
from ..provenance import BANNER, tag_line
from ..schemas import CurriculumItem, Page, Provenance, SourceRef
from ..util import slugify
from ..vault import Vault
from .plan import curriculum_path, load_curriculum, render_curriculum


@dataclass
class Progress:
    vault: Vault

    def load(self) -> tuple[dict, list[CurriculumItem]]:
        data = load_curriculum(self.vault)
        if data is None:
            raise FileNotFoundError(
                "No curriculum yet. Run `afterthought coach interview` then `afterthought coach plan`."
            )
        return data, [CurriculumItem.model_validate(i) for i in data["items"]]

    def save(self, data: dict, items: list[CurriculumItem]) -> list[str]:
        data["items"] = [i.model_dump(mode="json") for i in items]
        written = []
        r = self.vault.write_json(curriculum_path(self.vault), data)
        if r.changed:
            written.append(self.vault.rel(r.path))
        started = date.fromisoformat(data["started"]) if data.get("started") else None
        r = self.vault.write_text(
            self.vault.root / "coach" / "curriculum.md",
            render_curriculum(items, data["profile_hash"], data.get("model"), started),
        )
        if r.changed:
            written.append(self.vault.rel(r.path))
        written += sync_to_wiki(self.vault)
        return written

    def find(self, items: list[CurriculumItem], ref: str) -> CurriculumItem:
        ref = ref.strip()
        for it in items:
            if it.id == ref:
                return it
        if ref.isdigit():
            for it in items:
                if it.day == int(ref):
                    return it
        matches = [it for it in items if it.id.startswith(ref)]
        if len(matches) == 1:
            return matches[0]
        raise KeyError(f"No curriculum item {ref!r}; use an id like L-03-abc123 or a day number")

    def mark(
        self, ref: str, status: str, *, note: str | None = None, evidence: str | None = None, today: date | None = None
    ) -> tuple[CurriculumItem, list[str]]:
        data, items = self.load()
        it = self.find(items, ref)
        today = today or date.today()
        if data.get("started") is None:
            data["started"] = today.isoformat()
        upd: dict = {"status": status, "note": note or it.note}
        upd["completed_on"] = today if status == "done" else None
        if evidence:
            upd["evidence"] = SourceRef(file=evidence, span=slugify(evidence))
        new = it.model_copy(update=upd)
        if new == it:
            return it, []
        items[items.index(it)] = new
        return new, self.save(data, items)

    def due(self, today: date | None = None) -> list[CurriculumItem]:
        data, items = self.load()
        today = today or date.today()
        if data.get("started") is None:
            return [i for i in sorted(items, key=lambda i: i.day) if i.status == "todo"][:1]
        elapsed = (today - date.fromisoformat(data["started"])).days + 1
        return [i for i in sorted(items, key=lambda i: i.day) if i.status == "todo" and i.day <= max(elapsed, 1)]

    def summary(self) -> dict:
        data, items = self.load()
        done = [i for i in items if i.status == "done"]
        skills: dict[str, int] = {}
        for i in done:
            skills[i.skill] = skills.get(i.skill, 0) + 1
        return {
            "days": data.get("days", len(items)),
            "started": data.get("started"),
            "done": len(done),
            "skipped": sum(1 for i in items if i.status == "skipped"),
            "todo": sum(1 for i in items if i.status == "todo"),
            "skills": dict(sorted(skills.items())),
            "last_done": max((i.completed_on for i in done if i.completed_on), default=None),
        }


def learned_lines(items: list[CurriculumItem]) -> list[str]:
    """One line per skill with at least one completed task, tagged to the item that proved it."""
    first: dict[str, CurriculumItem] = {}
    counts: dict[str, int] = {}
    for it in sorted(items, key=lambda i: (i.completed_on or date.max, i.day)):
        if it.status != "done":
            continue
        counts[it.skill] = counts.get(it.skill, 0) + 1
        first.setdefault(it.skill, it)
    out = []
    for skill, it in first.items():
        when = it.completed_on.isoformat() if it.completed_on else "undated"
        text = f"Can {skill} (first done {when}, {counts[skill]} task{'s' if counts[skill] > 1 else ''}, see [[coach/curriculum]])"
        out.append(f"- {tag_line(text, 'system', it.id.lower())}")
    return out


def sync_to_wiki(vault: Vault) -> list[str]:
    """Write coach/skills.md and the Learned section on the user's person page.

    Called after progress changes and at the end of every compile, so the wiki
    always reflects what the person has shown they can do.
    """
    data = load_curriculum(vault)
    if data is None:
        return []
    items = [CurriculumItem.model_validate(i) for i in data["items"]]
    lines = learned_lines(items)
    written = []
    body = (
        "\n".join(["# Skills learned with AI", "", BANNER, "", "## Learned", *(lines or ["- (nothing completed yet)"])])
        + "\n"
    )
    page = Page(
        id="skills",
        title="Skills learned with AI",
        kind="coach",
        tags=["afterthought", "coach", "skills"],
        provenance=Provenance(origin="system", tool="afterthought.coach", derived_from=["coach/curriculum.json"]),
        links=extract_wikilinks(body),
        body=body,
    )
    r = vault.write_text(vault.root / "coach" / "skills.md", render_page(page))
    if r.changed:
        written.append(vault.rel(r.path))

    user = vault.config().get("user")
    if not user or not lines:
        return written
    path = vault.root / "entities" / "people" / f"{slugify(user)}.md"
    if path.exists():
        existing = read_page(path)
        _, sections = split_sections(existing.body)
        kept = [(h, c) for h, c in sections if h != "Learned"]
        preamble = existing.body.split("\n## ", 1)[0].rstrip("\n")
        parts = [preamble]
        for h, c in kept:
            parts += ["", f"## {h}", c]
        parts += ["", "## Learned", *lines]
        new_body = "\n".join(parts) + "\n"
        new_page = existing.model_copy(update={"body": new_body, "links": extract_wikilinks(new_body)})
    else:
        new_body = "\n".join([f"# {user}", "", BANNER, "", "## Learned", *lines]) + "\n"
        new_page = Page(
            id=slugify(user),
            title=user,
            kind="person",
            tags=["afterthought", "person"],
            provenance=Provenance(origin="system", tool="afterthought.coach"),
            links=extract_wikilinks(new_body),
            body=new_body,
        )
    r = vault.write_text(path, render_page(new_page))
    if r.changed:
        written.append(vault.rel(r.path))
    return written


def to_json(items: list[CurriculumItem]) -> str:
    return json.dumps([i.model_dump(mode="json") for i in items], indent=2, ensure_ascii=False)


__all__ = ["Progress", "learned_lines", "sync_to_wiki", "to_json", "unmanaged_sections"]
