"""Align two runs step by step and explain where and why they diverged."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ..schemas import Run, Step


def _key(s: Step) -> tuple[str, str, str]:
    """Steps align on kind, tool name and input; outputs are compared afterwards."""
    return (s.kind, s.name or "", s.input_hash)


@dataclass
class Change:
    kind: str  # changed_result | changed_context | changed_assistant | added | removed
    a: Step | None
    b: Step | None

    def describe(self) -> str:
        if self.kind == "changed_result":
            return f"tool result of {self.a.name or 'tool'} differs (step {self.a.index} vs {self.b.index})"
        if self.kind == "changed_context":
            return f"context differs at step {self.a.index} vs {self.b.index} ({self.a.kind})"
        if self.kind == "changed_assistant":
            return f"assistant output differs at step {self.a.index} vs {self.b.index}"
        if self.kind == "added":
            return f"only in B: step {self.b.index} ({self.b.kind}{' ' + self.b.name if self.b.name else ''})"
        return f"only in A: step {self.a.index} ({self.a.kind}{' ' + self.a.name if self.a.name else ''})"


@dataclass
class RunDiff:
    a: Run
    b: Run
    pairs: list[tuple[int | None, int | None]] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    first_divergence: tuple[int | None, int | None] | None = None
    same_outcome: bool = True

    @property
    def likely_cause(self) -> Change | None:
        """The earliest change that is a tool result or context, since those feed the model."""
        for c in self.changes:
            if c.kind in {"changed_result", "changed_context", "added", "removed"}:
                return c
        return self.changes[0] if self.changes else None

    def summary(self) -> str:
        if not self.changes:
            return "Runs are identical step for step."
        cause = self.likely_cause
        head = f"{len(self.changes)} difference(s); outcome {'same' if self.same_outcome else 'differs'}."
        if cause:
            head += f" First diverges at {cause.describe()}."
        return head


def diff_runs(a: Run, b: Run) -> RunDiff:
    ka = [_key(s) for s in a.steps]
    kb = [_key(s) for s in b.steps]
    sm = SequenceMatcher(a=ka, b=kb, autojunk=False)
    diff = RunDiff(a=a, b=b)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2), strict=True):
                diff.pairs.append((i, j))
                sa, sb = a.steps[i], b.steps[j]
                if sa.output_hash != sb.output_hash:
                    kind = "changed_result" if sa.kind == "tool_result" else "changed_assistant"
                    diff.changes.append(Change(kind, sa, sb))
        elif tag == "replace":
            # try to pair same-kind steps positionally and report what changed
            for offset in range(max(i2 - i1, j2 - j1)):
                i = i1 + offset if i1 + offset < i2 else None
                j = j1 + offset if j1 + offset < j2 else None
                diff.pairs.append((i, j))
                if i is not None and j is not None and a.steps[i].kind == b.steps[j].kind:
                    sa, sb = a.steps[i], b.steps[j]
                    kind = {"tool_result": "changed_result", "assistant": "changed_assistant"}.get(
                        sa.kind, "changed_context"
                    )
                    diff.changes.append(Change(kind, sa, sb))
                elif i is not None:
                    diff.changes.append(Change("removed", a.steps[i], None))
                else:
                    diff.changes.append(Change("added", None, b.steps[j]))
        elif tag == "delete":
            for i in range(i1, i2):
                diff.pairs.append((i, None))
                diff.changes.append(Change("removed", a.steps[i], None))
        elif tag == "insert":
            for j in range(j1, j2):
                diff.pairs.append((None, j))
                diff.changes.append(Change("added", None, b.steps[j]))
    diff.changes.sort(key=lambda c: c.a.index if c.a else c.b.index if c.b else 0)
    if diff.changes:
        c = diff.changes[0]
        diff.first_divergence = (c.a.index if c.a else None, c.b.index if c.b else None)
    diff.same_outcome = (a.outcome or "") == (b.outcome or "")
    return diff
