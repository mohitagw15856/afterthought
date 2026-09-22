"""Anthropic provider using the official SDK with structured outputs."""

from __future__ import annotations

from .base import StructuredRequest, T


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str = "claude-opus-5", max_tokens: int = 16000) -> None:
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "Install the anthropic extra: pip install 'afterthought[anthropic]'"
            ) from e
        self._client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def complete_structured(self, req: StructuredRequest, schema: type[T]) -> T:
        response = self._client.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            system=req.system,
            messages=[{"role": "user", "content": req.user}],
            output_format=schema,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Model declined request {req.task}/{req.key}")
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError(f"No structured output returned for {req.task}/{req.key}")
        return parsed
