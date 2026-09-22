"""Prompts and schemas for claim extraction and evidence demands."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..llm.base import StructuredRequest
from ..util import sha256_hex

EXTRACT_TASK = "verify.extract"
DEMAND_TASK = "verify.demand"


class ExtractedClaim(BaseModel):
    text: str = Field(description="The claim as one self-contained factual sentence.")
    quote: str = Field(description="The exact substring of the input that states this claim, copied verbatim.")
    kind: Literal["factual", "opinion", "instruction", "question"] = "factual"


class ClaimExtraction(BaseModel):
    claims: list[ExtractedClaim] = Field(default_factory=list)


class Verdict(BaseModel):
    claim_index: int
    verdict: Literal["sourced", "inferred", "unverified"]
    evidence_index: int | None = Field(
        default=None, description="Index into the evidence list that directly supports the claim, if any."
    )
    reasoning: str | None = Field(default=None, description="For inferred: the chain from evidence to claim.")


class DemandResult(BaseModel):
    verdicts: list[Verdict] = Field(default_factory=list)


EXTRACT_SYSTEM = """You are the verify step of Afterthought. Split the input into atomic claims.

Rules:
- One claim per checkable statement. Split compound sentences.
- `quote` must be copied verbatim from the input, character for character, so it can be found again. Prefer the shortest span that contains the claim.
- Mark kind as factual when the statement could in principle be true or false about the world. Opinions, instructions and questions are not factual.
- Do not add claims that are not in the input. Do not verify anything; that happens later.
- Use British English. No em dashes."""


DEMAND_SYSTEM = """You are the verify step of Afterthought. For each claim decide whether the supplied evidence supports it.

Rules:
- Return `sourced` only when one evidence item directly states the claim. Give its index.
- Return `inferred` when the claim follows from one or more evidence items by a short chain of reasoning. Write the chain in `reasoning` and cite the indices in it.
- Otherwise return `unverified`. Do not use knowledge from outside the evidence list. Do not invent evidence.
- Every claim index must get exactly one verdict.
- Use British English. No em dashes."""


def extract_request(text: str, slug: str) -> StructuredRequest:
    return StructuredRequest(
        task=EXTRACT_TASK,
        key=f"{slug}-{sha256_hex(text)}",
        system=EXTRACT_SYSTEM,
        user=f"Input:\n\n{text}",
    )


def demand_request(claims: list[str], evidence: list[str], slug: str) -> StructuredRequest:
    claim_lines = "\n".join(f"[{i}] {c}" for i, c in enumerate(claims))
    evidence_lines = "\n".join(f"[{i}] {e}" for i, e in enumerate(evidence)) or "(no evidence available)"
    user = f"Claims:\n{claim_lines}\n\nEvidence:\n{evidence_lines}"
    return StructuredRequest(
        task=DEMAND_TASK,
        key=f"{slug}-{sha256_hex(user)}",
        system=DEMAND_SYSTEM,
        user=user,
    )
