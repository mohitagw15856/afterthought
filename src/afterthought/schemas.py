"""Pydantic schemas for every on-disk object Afterthought writes.

Frontmatter on wiki pages is the model serialised to YAML. All dates are UTC.
Nothing here may be populated with an invented value: when a source date or
id is unknown the field stays None and the content is tagged UNVERIFIED.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Origin = Literal["human", "llm", "import", "system"]
PageKind = Literal[
    "project",
    "person",
    "tool",
    "concept",
    "question",
    "timeline",
    "index",
    "decision",
    "claims",
    "run",
    "coach",
]
ClaimTag = Literal["SOURCED", "INFERRED", "UNVERIFIED"]


class SourceRef(BaseModel):
    """Points at one span of one input file. `span` is the message span hash."""

    file: str
    message_id: str | None = None
    date: datetime | None = None
    span: str
    format: str | None = None
    conversation: str | None = None


class Provenance(BaseModel):
    origin: Origin
    tool: str | None = None
    model: str | None = None
    created: datetime | None = None
    derived_from: list[str] = Field(default_factory=list)


class Page(BaseModel):
    id: str
    title: str
    kind: PageKind
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    provenance: Provenance
    updated: datetime | None = None
    links: list[str] = Field(default_factory=list)
    body: str = ""


class Assumption(BaseModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    check_by: date | None = None
    status: Literal["open", "held", "failed", "unknown"] = "open"
    checked_on: date | None = None
    note: str | None = None


class Decision(BaseModel):
    id: str
    question: str
    options: list[str] = Field(default_factory=list)
    chosen: str
    reasoning: str = ""
    assumptions: list[Assumption] = Field(default_factory=list)
    decider: str | None = None
    source: SourceRef | None = None
    status: Literal["staged", "confirmed", "superseded"] = "staged"
    decided_on: date | None = None
    provenance: Provenance


class Claim(BaseModel):
    id: str
    text: str
    quote: str | None = None
    tag: ClaimTag = "UNVERIFIED"
    citation: SourceRef | None = None
    evidence: str | None = None
    reasoning: str | None = None
    span: tuple[int, int] = (0, 0)
    demanded: bool = False


class Step(BaseModel):
    index: int
    ts: datetime | None = None
    kind: Literal["user", "assistant", "tool_call", "tool_result", "system"]
    name: str | None = None
    ref: str | None = None
    input_hash: str = ""
    output_hash: str = ""
    content: str = ""


class Run(BaseModel):
    id: str
    source: Literal["claude_code", "jsonl_hook"]
    source_file: str | None = None
    title: str | None = None
    started: datetime | None = None
    ended: datetime | None = None
    steps: list[Step] = Field(default_factory=list)
    outcome: str | None = None
    provenance: Provenance


class CurriculumItem(BaseModel):
    id: str
    day: int
    task: str
    skill: str
    why: str = ""
    status: Literal["todo", "done", "skipped"] = "todo"
    evidence: SourceRef | None = None
    completed_on: date | None = None
    note: str | None = None
