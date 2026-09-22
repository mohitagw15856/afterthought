"""Ledger of processed message spans so re-runs only touch new material."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..vault import Vault

STATE_FILE = "compile.json"


class CompileState:
    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self.path: Path = vault.state_dir / STATE_FILE
        data = vault.read_json(self.path, default={}) or {}
        self.processed: dict[str, dict[str, Any]] = data.get("processed", {})
        self.batches: dict[str, dict[str, Any]] = data.get("batches", {})

    def is_processed(self, span: str) -> bool:
        return span in self.processed

    def mark(self, span: str, *, file: str, message_id: str, conversation: str) -> None:
        self.processed[span] = {
            "file": file,
            "message_id": message_id,
            "conversation": conversation,
        }

    def record_batch(self, key: str, *, conversation: str, spans: list[str], model: str | None) -> None:
        self.batches[key] = {"conversation": conversation, "spans": sorted(spans), "model": model}

    def save(self) -> bool:
        data = {"version": 1, "processed": self.processed, "batches": self.batches}
        return self.vault.write_json(self.path, data).changed
