"""Read, write and move decision pages inside the vault."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from ..pages import split_frontmatter
from ..provenance import parse_tag
from ..schemas import Assumption, Decision, Provenance, SourceRef
from ..util import sha256_hex
from ..vault import Vault
from .render import render_decision

REJECTED_FILE = "rejected.json"


@dataclass
class DueAssumption:
    decision: Decision
    index: int
    assumption: Assumption
    path: Path


class DecisionStore:
    def __init__(self, vault: Vault) -> None:
        self.vault = vault

    # ---------------------------------------------------------------- paths
    @property
    def confirmed_dir(self) -> Path:
        return self.vault.root / "decisions"

    @property
    def staged_dir(self) -> Path:
        return self.vault.root / "decisions" / "staged"

    @property
    def rejected_path(self) -> Path:
        return self.vault.state_dir / REJECTED_FILE

    def path_for(self, decision_id: str) -> Path | None:
        for d in (self.confirmed_dir, self.staged_dir):
            p = d / f"{decision_id}.md"
            if p.exists():
                return p
        return None

    # ------------------------------------------------------------------ io
    @staticmethod
    def load(path: Path) -> tuple[Decision, str | None]:
        """Return the decision and the span its model-written lines resolve to."""
        fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
        decision = Decision.model_validate(fm)
        span = None
        for line in body.splitlines():
            tag = parse_tag(line)
            if tag and tag[0] == "llm":
                # strip the numeric suffix added for uniqueness within a page
                base, _, suffix = tag[1].rpartition("-")
                span = base if suffix.isdigit() else tag[1]
                break
        return decision, span

    def save(self, decision: Decision, span: str | None = None) -> Path:
        target_dir = self.staged_dir if decision.status == "staged" else self.confirmed_dir
        path = target_dir / f"{decision.id}.md"
        self.vault.write_text(path, render_decision(decision, span))
        return path

    def get(self, decision_id: str) -> tuple[Decision, str | None, Path]:
        path = self.path_for(decision_id)
        if path is None:
            raise KeyError(f"No decision {decision_id} in {self.vault.root}")
        decision, span = self.load(path)
        return decision, span, path

    def list(self, status: str = "all") -> list[Decision]:
        dirs = {
            "all": [self.confirmed_dir, self.staged_dir],
            "staged": [self.staged_dir],
            "confirmed": [self.confirmed_dir],
        }[status]
        out: list[Decision] = []
        for d in dirs:
            if not d.exists():
                continue
            for p in sorted(d.glob("D-*.md")):
                out.append(self.load(p)[0])
        return sorted(out, key=lambda d: (d.decided_on or date.min, d.id))

    # --------------------------------------------------------------- reject
    def rejected(self) -> set[str]:
        data = self.vault.read_json(self.rejected_path, default={}) or {}
        return set(data.keys())

    def reject(self, decision_id: str, reason: str | None = None) -> bool:
        decision, _, path = self.get(decision_id)
        if decision.status != "staged":
            raise ValueError(f"{decision_id} is {decision.status}; only staged decisions can be rejected")
        data = self.vault.read_json(self.rejected_path, default={}) or {}
        data[decision_id] = {"question": decision.question, "reason": reason}
        self.vault.write_json(self.rejected_path, data)
        path.unlink()
        return True

    # -------------------------------------------------------------- confirm
    def confirm(
        self,
        decision_id: str,
        *,
        decider: str | None = None,
        check_in_days: int | None = None,
        check_by: date | None = None,
        confidences: dict[int, float] | None = None,
        today: date | None = None,
    ) -> tuple[Decision, bool]:
        """Move a staged decision to confirmed. Returns (decision, changed)."""
        decision, span, path = self.get(decision_id)
        if decision.status == "confirmed":
            return decision, False
        today = today or date.today()
        base = decision.decided_on or today
        default_check = check_by or (base + timedelta(days=check_in_days) if check_in_days else None)
        assumptions = []
        for i, a in enumerate(decision.assumptions):
            upd: dict = {}
            if a.check_by is None and default_check:
                upd["check_by"] = default_check
            if confidences and i in confidences:
                upd["confidence"] = confidences[i]
            assumptions.append(a.model_copy(update=upd))
        missing = [a.text for a in assumptions if a.check_by is None]
        if missing:
            raise ValueError(
                "Every assumption needs a check-by date; pass --check-by or --check-in. Missing for: "
                + "; ".join(missing)
            )
        confirmed = decision.model_copy(
            update={
                "status": "confirmed",
                "decider": decider or decision.decider,
                "decided_on": decision.decided_on or today,
                "assumptions": assumptions,
            }
        )
        self.save(confirmed, span)
        path.unlink()
        return confirmed, True

    # ------------------------------------------------------------------ new
    def create(
        self,
        *,
        question: str,
        chosen: str,
        options: list[str],
        reasoning: str,
        assumptions: list[Assumption],
        decider: str | None,
        decided_on: date | None,
        source: SourceRef | None = None,
    ) -> tuple[Decision, bool]:
        did = "D-" + sha256_hex("manual", question, chosen, length=8)
        existing = self.path_for(did)
        if existing:
            return self.load(existing)[0], False
        decision = Decision(
            id=did,
            question=question.strip(),
            options=[o.strip() for o in options if o.strip()],
            chosen=chosen.strip(),
            reasoning=reasoning.strip(),
            assumptions=assumptions,
            decider=decider,
            source=source,
            status="confirmed",
            decided_on=decided_on,
            provenance=Provenance(origin="human", tool="afterthought.decide"),
        )
        self.save(decision)
        return decision, True

    # --------------------------------------------------------------- review
    def due(self, as_of: date | None = None, include_all: bool = False) -> list[DueAssumption]:
        as_of = as_of or date.today()
        out: list[DueAssumption] = []
        for p in sorted(self.confirmed_dir.glob("D-*.md")):
            decision, _ = self.load(p)
            for i, a in enumerate(decision.assumptions):
                if a.status != "open":
                    continue
                if include_all or (a.check_by is not None and a.check_by <= as_of):
                    out.append(DueAssumption(decision, i, a, p))
        return out

    def check(
        self,
        decision_id: str,
        index: int,
        outcome: str,
        *,
        note: str | None = None,
        today: date | None = None,
    ) -> tuple[Decision, bool]:
        if outcome not in {"held", "failed", "unknown"}:
            raise ValueError("outcome must be held, failed or unknown")
        decision, span, _ = self.get(decision_id)
        if not 0 <= index < len(decision.assumptions):
            raise IndexError(f"{decision_id} has {len(decision.assumptions)} assumptions")
        a = decision.assumptions[index]
        if a.status == outcome and (note is None or a.note == note):
            return decision, False
        updated = a.model_copy(update={"status": outcome, "checked_on": today or date.today(), "note": note or a.note})
        assumptions = list(decision.assumptions)
        assumptions[index] = updated
        new = decision.model_copy(update={"assumptions": assumptions})
        self.save(new, span)
        return new, True


def parse_assumption(spec: str) -> Assumption:
    """Parse `text | confidence | YYYY-MM-DD` (confidence and date optional)."""
    parts = [p.strip() for p in spec.split("|")]
    text = parts[0]
    if not text:
        raise ValueError("assumption text is empty")
    confidence = float(parts[1]) if len(parts) > 1 and parts[1] else 0.5
    check_by = date.fromisoformat(parts[2]) if len(parts) > 2 and parts[2] else None
    return Assumption(text=text, confidence=confidence, check_by=check_by)


def to_json(decisions: list[Decision]) -> str:
    return json.dumps([d.model_dump(mode="json") for d in decisions], indent=2, ensure_ascii=False)
