"""OpenAI-compatible chat completions provider (OpenAI, Ollama, vLLM, etc)."""

from __future__ import annotations

import json
import os

from .base import StructuredRequest, T


class OpenAICompatProvider:
    name = "openai-compatible"

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None) -> None:
        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("Install the openai extra: pip install 'afterthought[openai]'") from e
        self._httpx = httpx
        self.model = model
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def complete_structured(self, req: StructuredRequest, schema: type[T]) -> T:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": req.system},
                {"role": "user", "content": req.user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            },
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        r = self._httpx.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=120)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return schema.model_validate(json.loads(content))
