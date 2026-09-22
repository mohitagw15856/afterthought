from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import StructuredRequest


class FixtureStore:
    """Read from several directories, write to the first one."""

    def __init__(self, dirs: list[Path]) -> None:
        self.dirs = [Path(d) for d in dirs if d is not None]

    def path_for(self, task: str, key: str, root: Path | None = None) -> Path:
        base = root or (self.dirs[0] if self.dirs else Path("fixtures"))
        return base / task / f"{key}.json"

    def load(self, task: str, key: str) -> dict[str, Any] | None:
        for d in self.dirs:
            p = self.path_for(task, key, d)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if "response" in data:
                    return data
                return {"response": data, "model": None}
        return None

    def save(self, req: StructuredRequest, response: dict[str, Any], model: str | None) -> Path:
        p = self.path_for(req.task, req.key)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"task": req.task, "key": req.key, "model": model, "response": response}
        p.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return p

    def save_request(self, req: StructuredRequest) -> Path:
        """Write the prompt beside where the fixture should go, to help a human author it."""
        p = self.path_for(req.task, req.key).with_suffix(".request.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(
                {"task": req.task, "key": req.key, "system": req.system, "user": req.user},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return p
