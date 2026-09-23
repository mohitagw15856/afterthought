"""Eight questions about real work. Answers are the only input to the plan."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from ..pages import render_page
from ..schemas import Page, Provenance
from ..util import sha256_hex
from ..vault import Vault

QUESTIONS: list[tuple[str, str]] = [
    ("role", "What is your job or main role right now?"),
    ("tasks", "What are the three tasks you spend the most time on in a typical week?"),
    ("tools", "Which tools and file types do you work in most (spreadsheets, code, documents, email, slides)?"),
    ("slow", "What is one task that takes far longer than it should?"),
    ("tried", "What have you already tried doing with AI, and how did it go?"),
    ("worries", "What worries you about using AI for real work (accuracy, privacy, anything else)?"),
    ("minutes", "How many minutes a day can you realistically give this for the next 30 days?"),
    ("goal", "In 30 days, what would you like to be able to do that you cannot do today?"),
]


class Profile(BaseModel):
    name: str | None = None
    answers: dict[str, str] = Field(default_factory=dict)

    @property
    def hash(self) -> str:
        return sha256_hex(json.dumps(self.answers, sort_keys=True), length=12)

    def minutes(self) -> int:
        digits = "".join(ch for ch in self.answers.get("minutes", "") if ch.isdigit())
        return int(digits) if digits else 20


def profile_dir(vault: Vault) -> Path:
    return vault.root / "coach"


def load_profile(vault: Vault) -> Profile | None:
    p = profile_dir(vault) / "profile.json"
    if not p.exists():
        return None
    return Profile.model_validate_json(p.read_text(encoding="utf-8"))


def save_profile(vault: Vault, profile: Profile) -> list[str]:
    d = profile_dir(vault)
    written = []
    r = vault.write_json(d / "profile.json", profile.model_dump(mode="json"))
    if r.changed:
        written.append(vault.rel(r.path))
    lines = [f"# Coaching profile{': ' + profile.name if profile.name else ''}", ""]
    lines.append("Answers given to `afterthought coach interview`. Written by a person, so no block ids.")
    for key, question in QUESTIONS:
        lines += ["", f"## {question}", profile.answers.get(key, "(not answered)")]
    page = Page(
        id="profile",
        title="Coaching profile",
        kind="coach",
        tags=["afterthought", "coach", "profile"],
        provenance=Provenance(origin="human", tool="afterthought.coach"),
        body="\n".join(lines) + "\n",
    )
    r = vault.write_text(d / "profile.md", render_page(page))
    if r.changed:
        written.append(vault.rel(r.path))
    return written


def answers_from_file(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("answers file must be a JSON object keyed by question id")
    known = {k for k, _ in QUESTIONS}
    return {k: str(v).strip() for k, v in data.items() if k in known and str(v).strip()}
