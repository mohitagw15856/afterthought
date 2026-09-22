import json
from pathlib import Path

from conftest import tree_digest
from typer.testing import CliRunner

from afterthought.cli import app
from afterthought.compile import compile_inputs
from afterthought.decide import DecisionStore
from afterthought.llm import DryRunProvider, FixtureStore
from afterthought.vault import Vault

runner = CliRunner()
HOSTING = "D-913ef655"  # Pi versus VPS, two assumptions


def _compiled(vault_dir: Path, export: Path, fixtures: Path) -> Vault:
    v = Vault(vault_dir)
    compile_inputs(v, [export], provider=DryRunProvider(FixtureStore([fixtures])))
    return v


def _cli(*args: str, vault: Path):
    return runner.invoke(app, ["decide", *args, "--vault", str(vault)])


def test_list_and_show(vault_dir, example_export, example_fixtures) -> None:
    _compiled(vault_dir, example_export, example_fixtures)
    r = _cli("list", vault=vault_dir)
    assert r.exit_code == 0 and r.output.count("? D-") == 4
    r = _cli("list", "--json", vault=vault_dir)
    assert len(json.loads(r.output)) == 4
    r = _cli("show", HOSTING, vault=vault_dir)
    assert r.exit_code == 0 and "status: staged" in r.output
    assert _cli("show", "D-nope", vault=vault_dir).exit_code == 1


def test_confirm_moves_page_and_dates_assumptions(vault_dir, example_export, example_fixtures) -> None:
    _compiled(vault_dir, example_export, example_fixtures)
    r = _cli("confirm", HOSTING, "--check-in", "90", "--decider", "Mo", "--confidence", "0=0.9", vault=vault_dir)
    assert r.exit_code == 0, r.output
    assert "check by 2026-06-13" in r.output  # decided 2026-03-15 + 90 days
    assert not (vault_dir / "decisions/staged" / f"{HOSTING}.md").exists()
    page = vault_dir / "decisions" / f"{HOSTING}.md"
    text = page.read_text()
    assert "status: confirmed" in text and "decider: Mo" in text
    assert "confidence: 0.9" in text
    assert "^at-llm-40f56318d8d2" in text  # provenance survives the move
    assert "[[decisions/D-913ef655|" in (vault_dir / "index.md").read_text()
    before = tree_digest(vault_dir)
    r = _cli("confirm", HOSTING, vault=vault_dir)
    assert "already confirmed" in r.output and tree_digest(vault_dir) == before


def test_confirm_with_fixed_date(vault_dir, example_export, example_fixtures) -> None:
    _compiled(vault_dir, example_export, example_fixtures)
    r = _cli("confirm", HOSTING, "--check-by", "2026-07-01", vault=vault_dir)
    assert r.exit_code == 0 and r.output.count("check by 2026-07-01") == 2


def test_reject_is_remembered_by_compile(vault_dir, example_export, example_fixtures) -> None:
    v = _compiled(vault_dir, example_export, example_fixtures)
    r = _cli("reject", HOSTING, "--reason", "not a real decision", vault=vault_dir)
    assert r.exit_code == 0
    assert not (vault_dir / "decisions/staged" / f"{HOSTING}.md").exists()
    (v.state_dir / "compile.json").unlink()  # force full re-extraction
    compile_inputs(v, [example_export], provider=DryRunProvider(FixtureStore([example_fixtures])))
    assert not (vault_dir / "decisions/staged" / f"{HOSTING}.md").exists()
    assert len(list((vault_dir / "decisions/staged").glob("D-*.md"))) == 3
    assert _cli("reject", HOSTING, vault=vault_dir).exit_code == 1


def test_review_and_check(vault_dir, example_export, example_fixtures) -> None:
    _compiled(vault_dir, example_export, example_fixtures)
    _cli("confirm", HOSTING, "--check-in", "30", vault=vault_dir)
    r = _cli("review", "--list", "--as-of", "2026-04-01", vault=vault_dir)
    assert "Nothing due" in r.output
    r = _cli("review", "--list", "--as-of", "2026-05-01", vault=vault_dir)
    assert "2 assumption(s) due" in r.output and "17 days ago" in r.output
    # interactive walk: first held with a note, second skipped
    r = runner.invoke(
        app,
        ["decide", "review", "--as-of", "2026-05-01", "--vault", str(vault_dir)],
        input="y\nInvoice was 4.20 a month\ns\n",
    )
    assert r.exit_code == 0 and "recorded: held" in r.output
    store = DecisionStore(Vault(vault_dir))
    d, _, _ = store.get(HOSTING)
    assert d.assumptions[0].status == "held" and d.assumptions[0].checked_on.isoformat() == "2026-05-01"
    assert d.assumptions[0].note == "Invoice was 4.20 a month"
    assert d.assumptions[1].status == "open"
    page = (vault_dir / "decisions" / f"{HOSTING}.md").read_text()
    assert "- [x] A small VPS costs under 5 pounds a month" in page
    r = _cli("check", HOSTING, "1", "--failed", "--note", "card wore out", "--as-of", "2026-05-02", vault=vault_dir)
    assert r.exit_code == 0 and "failed" in r.output
    r = _cli("review", "--list", "--as-of", "2026-06-01", vault=vault_dir)
    assert "Nothing due" in r.output
    assert _cli("check", HOSTING, "1", "--held", "--failed", vault=vault_dir).exit_code == 1
    assert _cli("check", HOSTING, "9", "--held", vault=vault_dir).exit_code == 1


def test_new_by_flags_is_idempotent(vault_dir) -> None:
    runner.invoke(app, ["init", "--vault", str(vault_dir), "--user", "Mo"])
    args = [
        "new", "-q", "Which licence for Afterthought?", "-c", "MIT", "-o", "MIT", "-o", "Apache 2.0",
        "-r", "Simplest for contributors.", "-a", "Nobody needs a patent grant | 0.7 | 2026-12-01",
        "-a", "Contributors accept MIT", "--on", "2026-09-22", "--check-in", "10",
    ]
    r = _cli(*args, vault=vault_dir)
    assert r.exit_code == 0 and r.output.startswith("Recorded D-")
    did = r.output.split()[1].rstrip(":")
    text = (vault_dir / "decisions" / f"{did}.md").read_text()
    assert "origin: human" in text and "decider: Mo" in text and "^at-" not in text
    assert "check_by: '2026-12-01'" in text and "check_by: '2026-10-02'" in text
    before = tree_digest(vault_dir)
    r = _cli(*args, vault=vault_dir)
    assert "Already recorded" in r.output and tree_digest(vault_dir) == before


def test_new_interactive(vault_dir) -> None:
    runner.invoke(app, ["init", "--vault", str(vault_dir)])
    r = runner.invoke(
        app,
        ["decide", "new", "--vault", str(vault_dir)],
        input="Tabs or spaces?\ntabs\nspaces\n\nspaces\nEditor default.\nEveryone uses black | 0.9\n\n",
    )
    assert r.exit_code == 0, r.output
    assert "Recorded D-" in r.output
    pages = list((vault_dir / "decisions").glob("D-*.md"))
    assert len(pages) == 1 and "Everyone uses black" in pages[0].read_text()
