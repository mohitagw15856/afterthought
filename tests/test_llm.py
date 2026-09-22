from pathlib import Path

import pytest
from pydantic import BaseModel

from afterthought.llm import (
    DryRunProvider,
    FixtureMissingError,
    FixtureStore,
    RecordingProvider,
    StructuredRequest,
    get_provider,
)


class Out(BaseModel):
    answer: str


REQ = StructuredRequest(task="t", key="k", system="s", user="u")


def test_dry_run_missing_writes_request(tmp_path: Path) -> None:
    p = DryRunProvider(FixtureStore([tmp_path]))
    with pytest.raises(FixtureMissingError):
        p.complete_structured(REQ, Out)
    assert (tmp_path / "t" / "k.request.json").exists()


def test_dry_run_replays(tmp_path: Path) -> None:
    store = FixtureStore([tmp_path])
    store.save(REQ, {"answer": "42"}, model="m")
    p = DryRunProvider(store)
    assert p.complete_structured(REQ, Out).answer == "42"
    assert p.model == "m"


class Fake:
    name = "fake"
    model = "fake-1"
    calls = 0

    def complete_structured(self, req: StructuredRequest, schema: type[Out]) -> Out:
        self.calls += 1
        return schema(answer="live")


def test_recording_caches(tmp_path: Path) -> None:
    fake = Fake()
    p = RecordingProvider(fake, FixtureStore([tmp_path]), write=True)
    assert p.complete_structured(REQ, Out).answer == "live"
    assert p.complete_structured(REQ, Out).answer == "live"
    assert fake.calls == 1
    assert (tmp_path / "t" / "k.json").exists()


def test_get_provider_dry_run(tmp_path: Path) -> None:
    p = get_provider({}, dry_run=True, fixture_dirs=[tmp_path])
    assert isinstance(p, DryRunProvider)


@pytest.mark.live
def test_live_anthropic_extraction(tmp_path: Path, example_export: Path) -> None:
    from afterthought.compile.extract import Extraction, build_request
    from afterthought.ingest import group_conversations, load

    conv = group_conversations(list(load(example_export)))[1]
    req = build_request(conv, [m.span for m in conv.messages])
    p = get_provider(
        {"llm": {"provider": "anthropic", "model": "claude-opus-5"}},
        dry_run=False,
        fixture_dirs=[tmp_path],
    )
    out = p.complete_structured(req, Extraction)
    assert out.entities
    ids = {m.message_id for m in conv.messages}
    assert any(f.message_id in ids for e in out.entities for f in e.facts)
