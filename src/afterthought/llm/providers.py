from __future__ import annotations

from .base import FixtureMissingError, LLMProvider, StructuredRequest, T
from .fixtures import FixtureStore


class DryRunProvider:
    """Replays fixtures. Never calls a model, never invents a response."""

    name = "dry-run"

    def __init__(self, store: FixtureStore) -> None:
        self.store = store
        self.model = None

    def complete_structured(self, req: StructuredRequest, schema: type[T]) -> T:
        payload = self.store.load(req.task, req.key)
        if payload is None:
            hint = self.store.save_request(req)
            raise FixtureMissingError(req.task, req.key, str(hint.with_suffix("").with_suffix(".json")))
        self.model = payload.get("model") or "fixture"
        return schema.model_validate(payload["response"])


class RecordingProvider:
    """Fixture first, then the live provider. Optionally records live responses."""

    name = "recording"

    def __init__(self, inner: LLMProvider, store: FixtureStore, *, write: bool = True) -> None:
        self.inner = inner
        self.store = store
        self.write = write
        self.model = inner.model

    def complete_structured(self, req: StructuredRequest, schema: type[T]) -> T:
        cached = self.store.load(req.task, req.key)
        if cached is not None:
            self.model = cached.get("model") or self.inner.model
            return schema.model_validate(cached["response"])
        self.model = self.inner.model
        result = self.inner.complete_structured(req, schema)
        if self.write:
            self.store.save(req, result.model_dump(mode="json"), self.inner.model)
        return result
