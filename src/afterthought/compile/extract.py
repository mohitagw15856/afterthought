"""LLM extraction of entities, candidate decisions and open questions from
one conversation. The prompt gives every message an id; the model must cite
one of those ids for every fact. Facts citing an unknown id are kept but
marked UNVERIFIED downstream; they are never silently attached to a source.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..ingest.base import Conversation
from ..llm.base import StructuredRequest
from ..util import iso, sha256_hex, slugify

TASK = "compile.extract"
EntityKind = Literal["project", "person", "tool", "concept"]


class Fact(BaseModel):
    text: str = Field(description="One atomic, self-contained statement about the entity.")
    message_id: str = Field(description="The id of the message this fact comes from.")


class EntityMention(BaseModel):
    name: str
    kind: EntityKind
    aliases: list[str] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)


class CandidateDecision(BaseModel):
    question: str
    options: list[str] = Field(default_factory=list)
    chosen: str
    reasoning: str = ""
    assumptions: list[str] = Field(default_factory=list)
    decider: str | None = None
    message_id: str


class OpenQuestion(BaseModel):
    text: str
    message_id: str


class Extraction(BaseModel):
    summary: str = Field(description="One or two sentences on what the conversation was about.")
    entities: list[EntityMention] = Field(default_factory=list)
    decisions: list[CandidateDecision] = Field(default_factory=list)
    questions: list[OpenQuestion] = Field(default_factory=list)


SYSTEM = """You are the compile step of Afterthought, a tool that turns AI conversations into a maintained wiki.

You will be given one conversation. Every message has an id in square brackets. Extract:

1. entities: projects, people, tools and concepts that the conversation is actually about. Skip generic words. For each entity list atomic facts stated in the conversation. Each fact must cite the id of the single message it comes from. Do not infer facts that are not stated. Do not invent ids.
2. decisions: places where the person weighed options and chose one. Record the question, the options considered, the chosen option, the reasoning given, any assumptions the choice rests on, and the id of the message where the choice was made.
3. questions: open questions the person raised that were not answered in the conversation.
4. summary: one or two sentences.

Use British English. Do not use em dashes. Keep facts short. If nothing of a category is present, return an empty list for it."""


def batch_key(conv: Conversation, new_spans: list[str]) -> str:
    file_slug = slugify(conv.source_file, max_len=30)
    conv_slug = slugify(conv.id, max_len=24) if conv.id else "conv"
    return f"{file_slug}-{conv_slug}-{sha256_hex(*sorted(new_spans), length=8)}"


def render_conversation(conv: Conversation, new_spans: set[str]) -> str:
    lines = [f"Title: {conv.title}", f"Source: {conv.source_file} ({conv.format})"]
    if conv.started:
        lines.append(f"Started: {iso(conv.started)}")
    lines.append("")
    for m in conv.messages:
        who = m.author or m.role
        marker = "" if m.span in new_spans else " (already processed, context only)"
        stamp = f" {iso(m.ts)}" if m.ts else ""
        lines.append(f"[{m.message_id}]{stamp} {who}{marker}:")
        lines.append(m.text)
        lines.append("")
    return "\n".join(lines)


def build_request(conv: Conversation, new_spans: list[str]) -> StructuredRequest:
    return StructuredRequest(
        task=TASK,
        key=batch_key(conv, new_spans),
        system=SYSTEM,
        user=render_conversation(conv, set(new_spans)),
    )
