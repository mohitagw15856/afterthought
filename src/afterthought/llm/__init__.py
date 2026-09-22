"""Provider-agnostic LLM access with structured outputs and fixture replay.

Every call carries a `task` (which prompt template) and a caller-chosen
stable `key`. Responses are stored as `<fixtures>/<task>/<key>.json`, so
dry-run mode can replay them without a network and tests run without keys.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import FixtureMissingError, LLMProvider, StructuredRequest
from .fixtures import FixtureStore
from .providers import DryRunProvider, RecordingProvider

__all__ = [
    "DryRunProvider",
    "FixtureMissingError",
    "FixtureStore",
    "LLMProvider",
    "RecordingProvider",
    "StructuredRequest",
    "get_provider",
]


def get_provider(
    config: dict[str, Any],
    *,
    dry_run: bool,
    fixture_dirs: list[Path],
    record: bool = False,
) -> LLMProvider:
    """Build the provider chain from vault config and CLI flags.

    Lookup order for a response: each fixture dir in turn, then (unless dry
    run) the live provider. Live responses are written back to the first
    fixture dir so the next run is a replay.
    """
    store = FixtureStore(fixture_dirs)
    if dry_run:
        return DryRunProvider(store)
    llm_cfg = config.get("llm", {})
    name = llm_cfg.get("provider", "anthropic")
    model = llm_cfg.get("model")
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider

        live: LLMProvider = AnthropicProvider(model=model or "claude-opus-5")
    elif name in {"openai", "openai-compatible"}:
        from .openai_compat import OpenAICompatProvider

        live = OpenAICompatProvider(model=model or "gpt-4o", base_url=llm_cfg.get("base_url"))
    else:
        raise ValueError(f"Unknown llm.provider {name!r}")
    return RecordingProvider(live, store, write=record)
