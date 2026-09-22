import json
from pathlib import Path

from conftest import copy_export, tree_digest

from afterthought.compile import compile_inputs
from afterthought.llm import DryRunProvider, FixtureStore
from afterthought.pages import block_ids, read_page
from afterthought.vault import Vault


def _run(vault_dir: Path, export: Path, fixtures: Path):
    v = Vault(vault_dir)
    provider = DryRunProvider(FixtureStore([fixtures]))
    return v, compile_inputs(v, [export], provider=provider)


def test_end_to_end(vault_dir: Path, example_export: Path, example_fixtures: Path) -> None:
    v, report = _run(vault_dir, example_export, example_fixtures)
    assert report.llm_calls == 3 and report.conversations == 3
    assert report.stats.decisions_staged == 4 and report.stats.questions == 1
    assert report.stats.unverified_facts == 1
    assert report.redactions == 2

    lantern = read_page(vault_dir / "entities/projects/lantern.md")
    assert lantern.kind == "project" and lantern.updated is not None
    spans = {s.span for s in lantern.sources}
    for bid in block_ids(lantern.body):
        if bid.startswith("at-llm-"):
            assert bid.split("-")[2] in spans, bid
    assert "[[grafana|Grafana]]" in lantern.body
    assert "^at-llm-" in lantern.body
    assert lantern.provenance.origin == "llm"

    octopus = (vault_dir / "entities/tools/octopus-home-mini.md").read_text()
    assert "UNVERIFIED: The Home Mini provides 30-second data at no charge. ^at-unverified-" in octopus

    for p in vault_dir.rglob("*.md"):
        text = p.read_text()
        assert "mo.example@example.com" not in text and "9f8e7d6c5b4a" not in text, p
        ids = [ln.rsplit("^", 1)[1] for ln in text.splitlines() if " ^at-" in ln]
        assert len(ids) == len(set(ids)), f"duplicate block id in {p}"

    idx = (vault_dir / "index.md").read_text()
    assert "[[entities/projects/lantern|Lantern]]" in idx
    assert (vault_dir / "decisions/staged").is_dir() and len(list((vault_dir / "decisions/staged").glob("D-*.md"))) == 4
    assert (vault_dir / "timeline/2026-03-04.md").exists()
    state = json.loads((v.state_dir / "compile.json").read_text())
    assert len(state["processed"]) == 13


def test_idempotent(vault_dir: Path, example_export: Path, example_fixtures: Path) -> None:
    _run(vault_dir, example_export, example_fixtures)
    before = tree_digest(vault_dir)
    v, report = _run(vault_dir, example_export, example_fixtures)
    assert tree_digest(vault_dir) == before
    assert not report.changed and report.llm_calls == 0 and report.new_messages == 0


def test_incremental(
    vault_dir: Path,
    tmp_path: Path,
    trimmed_export: Path,
    example_export: Path,
    example_fixtures: Path,
) -> None:
    _, first = _run(vault_dir, trimmed_export, example_fixtures)
    assert first.llm_calls == 2
    assert not (vault_dir / "entities/tools/vps.md").exists()
    full = copy_export(example_export, tmp_path / "full")
    _, second = _run(vault_dir, full, example_fixtures)
    assert second.llm_calls == 1 and second.conversations_with_new == 1 and second.skipped_messages == 9
    assert (vault_dir / "entities/tools/vps.md").exists()
    lantern = (vault_dir / "entities/projects/lantern.md").read_text()
    assert lantern.count("- Lantern is a side project") == 1
    assert "collector stays on the Raspberry Pi" in lantern


def test_human_sections_survive(vault_dir: Path, example_export: Path, example_fixtures: Path) -> None:
    _run(vault_dir, example_export, example_fixtures)
    page = vault_dir / "entities/tools/grafana.md"
    page.write_text(page.read_text() + "\n## Notes\nI prefer the dark theme.\n")
    (vault_dir / ".afterthought/state/compile.json").unlink()  # force a full re-merge
    _run(vault_dir, example_export, example_fixtures)
    text = page.read_text()
    assert text.count("## Notes") == 1 and "I prefer the dark theme." in text
    assert text.index("## Sources") < text.index("## Notes")


def test_ignore_rules(vault_dir: Path, example_export: Path, example_fixtures: Path) -> None:
    v = Vault(vault_dir)
    v.init()
    (vault_dir / ".afterthoughtignore").write_text("conversations.json\n")
    report = compile_inputs(v, [example_export], provider=DryRunProvider(FixtureStore([example_fixtures])))
    assert report.ignored and report.conversations == 0
