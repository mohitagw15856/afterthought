from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class StructuredRequest:
    task: str
    key: str
    system: str
    user: str


class FixtureMissingError(RuntimeError):
    def __init__(self, task: str, key: str, hint_path: str) -> None:
        super().__init__(
            f"No fixture for task {task!r} key {key!r}. Dry-run mode never calls a model. "
            f"Run again without --dry-run (with --record) or author {hint_path}"
        )
        self.task = task
        self.key = key
        self.hint_path = hint_path


class LLMProvider(Protocol):
    name: str
    model: str | None

    def complete_structured(self, req: StructuredRequest, schema: type[T]) -> T: ...
