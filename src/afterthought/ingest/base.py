from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from ..redact import redact
from ..util import sha256_hex

Role = Literal["user", "assistant", "system", "tool"]


class Message(BaseModel):
    source_file: str
    format: str
    conversation_id: str
    conversation_title: str
    message_id: str
    role: Role
    author: str | None = None
    ts: datetime | None = None
    text: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def span(self) -> str:
        """Stable id for this message's content. Changes only if the text changes."""
        return sha256_hex(self.source_file, self.message_id, self.text)

    def redacted(self, allow_emails: tuple[str, ...] = ()) -> Message:
        text, _ = redact(self.text, allow_emails=allow_emails)
        return self.model_copy(update={"text": text})


class Conversation(BaseModel):
    id: str
    title: str
    source_file: str
    format: str
    messages: list[Message] = Field(default_factory=list)

    @property
    def started(self) -> datetime | None:
        stamps = [m.ts for m in self.messages if m.ts]
        return min(stamps) if stamps else None

    @property
    def ended(self) -> datetime | None:
        stamps = [m.ts for m in self.messages if m.ts]
        return max(stamps) if stamps else None


def group_conversations(messages: list[Message]) -> list[Conversation]:
    groups: OrderedDict[str, Conversation] = OrderedDict()
    for m in messages:
        key = f"{m.source_file}::{m.conversation_id}"
        conv = groups.get(key)
        if conv is None:
            conv = Conversation(
                id=m.conversation_id,
                title=m.conversation_title,
                source_file=m.source_file,
                format=m.format,
            )
            groups[key] = conv
        conv.messages.append(m)
    return list(groups.values())


def clean_text(text: str) -> str:
    return text.replace("\r\n", "\n").strip()
