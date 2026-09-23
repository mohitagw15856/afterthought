import json
from pathlib import Path

from conftest import ROOT, tree_digest
from typer.testing import CliRunner

from afterthought.cli import app
from afterthought.coach import Progress
from afterthought.compile import compile_inputs
from afterthought.llm import DryRunProvider, FixtureStore
from afterthought.pages import read_page
from afterthought.vault import Vault

runner = CliRunner()
ANSWERS = ROOT / "examples" / "coach" / "answers.json"


def _setup(vault_dir: Path, fixtures: Path, user: str = "Siyu") -> Vault:
    v = Vault(vault_dir)
    v.init(user=user)
    r = runner.invoke(app, ["coach", "interview", "--answers", str(ANSWERS), "--vault", str(vault_dir)])
    assert r.exit_code == 0, r.output
    r = runner.invoke(
        app,
        ["coach", "plan", "--vault", str(vault_dir), "--dry-run", "--fixtures", str(fixtures), "--start", "2026-09-01"],
    )
    assert r.exit_code == 0, r.output
    return v


def test_interview_from_file_and_interactive(vault_dir, example_fixtures) -> None:
    _setup(vault_dir, example_fixtures)
    profile = json.loads((vault_dir / "coach" / "profile.json").read_text())
    assert profile["name"] == "Siyu" and profile["answers"]["minutes"] == "25 minutes a day"
    page = read_page(vault_dir / "coach" / "profile.md")
    assert page.kind == "coach" and page.provenance.origin == "human" and "^at-" not in page.body
    before = tree_digest(vault_dir / "coach")
    r = runner.invoke(app, ["coach", "interview", "--answers", str(ANSWERS), "--vault", str(vault_dir)])
    assert "No changes." in r.output and tree_digest(vault_dir / "coach") == before

    other = Vault(vault_dir.parent / "other")
    other.init()
    r = runner.invoke(
        app, ["coach", "interview", "--vault", str(other.root)], input="Teacher\n\n\nMarking\n\n\n15\nMark faster\n"
    )
    assert r.exit_code == 0 and "4 of 8 answers" in r.output
    r = runner.invoke(app, ["coach", "plan", "--vault", str(other.root), "--dry-run"])
    assert r.exit_code == 2 and "No fixture" in r.output  # no invented curriculum
    empty = Vault(vault_dir.parent / "empty")
    empty.init()
    assert runner.invoke(app, ["coach", "plan", "--vault", str(empty.root), "--dry-run"]).exit_code == 1


def test_plan_writes_tagged_curriculum(vault_dir, example_fixtures) -> None:
    _setup(vault_dir, example_fixtures)
    data = json.loads((vault_dir / "coach" / "curriculum.json").read_text())
    assert len(data["items"]) == 30 and [i["day"] for i in data["items"]] == list(range(1, 31))
    assert data["started"] == "2026-09-01" and data["model"] == "hand-authored fixture"
    page = read_page(vault_dir / "coach" / "curriculum.md")
    assert page.kind == "coach" and page.provenance.origin == "llm"
    assert page.sources[0].file == "coach/profile.json" and page.sources[0].span == data["profile_hash"]
    tagged = [ln for ln in page.body.splitlines() if ln.startswith("- [ ] Day ")]
    assert len(tagged) == 30 and all(f"^at-llm-{data['profile_hash']}-" in ln for ln in tagged)
    assert "## Week 5" in page.body and "[redact before sharing]" in page.body
    before = tree_digest(vault_dir)
    r = runner.invoke(
        app,
        [
            "coach",
            "plan",
            "--vault",
            str(vault_dir),
            "--dry-run",
            "--fixtures",
            str(example_fixtures),
            "--start",
            "2026-09-01",
        ],
    )
    assert "No changes." in r.output and tree_digest(vault_dir) == before


def test_today_done_skip_status(vault_dir, example_fixtures) -> None:
    v = _setup(vault_dir, example_fixtures)
    common = ["--vault", str(vault_dir)]
    r = runner.invoke(app, ["coach", "today", *common, "--as-of", "2026-09-03"])
    assert r.exit_code == 0 and r.output.count("Day ") == 3
    r = runner.invoke(
        app, ["coach", "done", "1", *common, "--as-of", "2026-09-01", "--note", "Used the 2019 supply template"]
    )
    assert r.exit_code == 0 and "L-01-" in r.output and "done:" in r.output
    r = runner.invoke(
        app, ["coach", "done", "1", *common, "--as-of", "2026-09-01", "--note", "Used the 2019 supply template"]
    )
    assert "(unchanged)" in r.output
    r = runner.invoke(app, ["coach", "skip", "2", *common, "--as-of", "2026-09-02"])
    assert r.exit_code == 0
    r = runner.invoke(app, ["coach", "done", "3", *common, "--as-of", "2026-09-03", "--evidence", "notes/day3.md"])
    assert r.exit_code == 0
    r = runner.invoke(app, ["coach", "today", *common, "--as-of", "2026-09-03"])
    assert "Nothing due" in r.output
    r = runner.invoke(app, ["coach", "status", *common])
    assert "2 done, 1 skipped, 27 to go of 30 days; started 2026-09-01" in r.output
    assert "redact before sharing: 1" in r.output and "verify a claim against the source: 1" in r.output
    body = (vault_dir / "coach" / "curriculum.md").read_text()
    assert (
        "- [x] Day 1:" in body
        and "(done 2026-09-01) Note: Used the 2019 supply template" in body
        and "- [-] Day 2:" in body
    )
    items = json.loads(runner.invoke(app, ["coach", "status", "--json", *common]).output)
    assert items[2]["evidence"]["file"] == "notes/day3.md" and items[2]["completed_on"] == "2026-09-03"
    assert runner.invoke(app, ["coach", "done", "99", *common]).exit_code == 1
    p = Progress(v)
    assert p.find(p.load()[1], "L-03").day == 3


def test_progress_feeds_the_wiki(vault_dir, example_export, example_fixtures) -> None:
    v = _setup(vault_dir, example_fixtures)
    compile_inputs(v, [example_export], provider=DryRunProvider(FixtureStore([example_fixtures])))
    siyu = vault_dir / "entities" / "people" / "siyu.md"
    assert "## Learned" not in siyu.read_text()
    r = runner.invoke(app, ["coach", "done", "3", "--vault", str(vault_dir), "--as-of", "2026-09-03"])
    assert r.exit_code == 0
    skills = read_page(vault_dir / "coach" / "skills.md")
    assert skills.provenance.origin == "system"
    assert (
        "- Can verify a claim against the source (first done 2026-09-03, 1 task, see [[coach/curriculum]]) "
        "^at-system-l-03-" in skills.body
    )
    text = siyu.read_text()
    assert "## Learned" in text and "Can verify a claim against the source" in text
    assert text.index("## Sources") < text.index("## Learned")
    page = read_page(siyu)
    assert "coach/curriculum" in page.links and "^at-llm-" in page.body  # compiled facts intact
    # compile again: Learned section survives and nothing changes
    before = tree_digest(vault_dir)
    rep = compile_inputs(v, [example_export], provider=DryRunProvider(FixtureStore([example_fixtures])))
    assert not rep.changed and tree_digest(vault_dir) == before
    # a fresh compile after the state file is removed still keeps the Learned section
    (v.state_dir / "compile.json").unlink()
    compile_inputs(v, [example_export], provider=DryRunProvider(FixtureStore([example_fixtures])))
    assert siyu.read_text().count("## Learned") == 1


def test_learned_page_created_when_person_page_missing(vault_dir, example_fixtures) -> None:
    v = _setup(vault_dir, example_fixtures, user="Nobody Yet")
    r = runner.invoke(app, ["coach", "done", "5", "--vault", str(vault_dir), "--as-of", "2026-09-05"])
    assert r.exit_code == 0
    page = read_page(vault_dir / "entities" / "people" / "nobody-yet.md")
    assert page.kind == "person" and page.provenance.origin == "system"
    assert "Can write a reusable prompt" in page.body
    assert v.config()["user"] == "Nobody Yet"
