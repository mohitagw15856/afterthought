"""Generate a curriculum from the profile with one structured model call."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from ..llm.base import LLMProvider, StructuredRequest
from ..pages import render_page
from ..provenance import tag_line
from ..schemas import CurriculumItem, Page, Provenance, SourceRef
from ..util import sha256_hex
from ..vault import Vault
from .interview import QUESTIONS, Profile

TASK = "coach.plan"


class DraftItem(BaseModel):
    day: int = Field(ge=1)
    task: str = Field(
        description="One concrete thing to try today, in the person's own tools, doable in their minutes."
    )
    skill: str = Field(description="The short name of the skill this builds, reused across days.")
    why: str = Field(default="", description="One sentence on why this matters for their goal.")


class CurriculumDraft(BaseModel):
    items: list[DraftItem] = Field(default_factory=list)


SYSTEM = """You are the coach step of Afterthought. Design a day-by-day curriculum of concrete tasks for one person to try with an AI assistant, based only on their interview answers.

Rules:
- Exactly one task per day, days 1 to N, each doable within the minutes they said they have.
- Every task names a real artefact from their own work: a document they have, a spreadsheet, a message, a piece of code. No toy exercises.
- Build up: first days are safe and small, later days chain skills together. Revisit each skill at least twice.
- Respect their worries. If they worry about accuracy, include tasks that check the model's output against a source. If they worry about privacy, include tasks that redact or use non-sensitive material.
- `skill` is a short reusable label such as "summarise a document", "draft then edit", "verify a claim", "structured extraction".
- British English. No em dashes."""


def _render_profile(profile: Profile) -> str:
    lines = []
    for key, question in QUESTIONS:
        lines.append(f"{question}\n{profile.answers.get(key, '(not answered)')}\n")
    return "\n".join(lines)


def build_request(profile: Profile, days: int) -> StructuredRequest:
    user = f"Days: {days}\nMinutes per day: {profile.minutes()}\n\nInterview answers:\n\n{_render_profile(profile)}"
    return StructuredRequest(task=TASK, key=f"{profile.hash}-{days}", system=SYSTEM, user=user)


def item_id(day: int, task: str) -> str:
    return f"L-{day:02d}-{sha256_hex(task, length=6)}"


def curriculum_path(vault: Vault) -> Path:
    return vault.root / "coach" / "curriculum.json"


def render_curriculum(items: list[CurriculumItem], profile_hash: str, model: str | None, started: date | None) -> str:
    box = {"todo": "[ ]", "done": "[x]", "skipped": "[-]"}
    total = len(items)
    done = sum(1 for i in items if i.status == "done")
    lines = [f"# {total}-day curriculum", ""]
    lines.append(
        f"Generated from [[coach/profile|the coaching profile]]; started {started.isoformat() if started else 'not yet'}; {done} of {total} done."
    )
    lines.append(
        "Tick items with `afterthought coach done <id>`. Every line below was proposed by a model from the profile."
    )
    week = 0
    for it in sorted(items, key=lambda i: i.day):
        w = (it.day - 1) // 7 + 1
        if w != week:
            week = w
            lines += ["", f"## Week {week}"]
        extra = f" (done {it.completed_on})" if it.completed_on else ""
        note = f" Note: {it.note}" if it.note else ""
        text = f"{box[it.status]} Day {it.day}: {it.task} [{it.skill}]{extra}{note}  `{it.id}`"
        lines.append(f"- {tag_line(text, 'llm', profile_hash, suffix=it.day)}")
    page = Page(
        id="curriculum",
        title=f"{total}-day curriculum",
        kind="coach",
        tags=["afterthought", "coach", "curriculum"],
        sources=[SourceRef(file="coach/profile.json", span=profile_hash)],
        provenance=Provenance(origin="llm", tool="afterthought.coach", model=model),
        links=["coach/profile"],
        body="\n".join(lines) + "\n",
    )
    return render_page(page)


def make_plan(
    vault: Vault, profile: Profile, provider: LLMProvider, days: int = 30, started: date | None = None
) -> tuple[list[CurriculumItem], list[str]]:
    draft = provider.complete_structured(build_request(profile, days), CurriculumDraft)
    by_day: dict[int, DraftItem] = {}
    for d in sorted(draft.items, key=lambda d: d.day):
        if 1 <= d.day <= days and d.day not in by_day:
            by_day[d.day] = d
    items = [
        CurriculumItem(
            id=item_id(d.day, d.task), day=d.day, task=d.task.strip(), skill=d.skill.strip(), why=d.why.strip()
        )
        for d in by_day.values()
    ]
    data = {
        "profile_hash": profile.hash,
        "model": provider.model,
        "days": days,
        "started": started.isoformat() if started else None,
        "items": [i.model_dump(mode="json") for i in items],
    }
    written = []
    r = vault.write_json(curriculum_path(vault), data)
    if r.changed:
        written.append(vault.rel(r.path))
    r = vault.write_text(
        vault.root / "coach" / "curriculum.md", render_curriculum(items, profile.hash, provider.model, started)
    )
    if r.changed:
        written.append(vault.rel(r.path))
    return items, written


def load_curriculum(vault: Vault) -> dict | None:
    p = curriculum_path(vault)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
