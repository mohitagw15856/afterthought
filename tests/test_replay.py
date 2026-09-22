import json
from pathlib import Path

from conftest import ROOT, tree_digest
from typer.testing import CliRunner

from afterthought.cli import app
from afterthought.replay import RunStore, diff_runs, parse_run
from afterthought.replay.parse import detect_run_format
from afterthought.vault import Vault

runner = CliRunner()
RUN_A = ROOT / "examples" / "replay" / "fix-test-run-a.jsonl"
RUN_B = ROOT / "examples" / "replay" / "fix-test-run-b.jsonl"


def test_parse_claude_code(ingest_fixtures: Path) -> None:
    p = ingest_fixtures / "claude-code-session.jsonl"
    assert detect_run_format(p) == "claude_code"
    run = parse_run(p)
    assert run.source == "claude_code"
    assert [s.kind for s in run.steps] == ["user", "assistant", "tool_call", "tool_result", "assistant"]
    assert run.steps[2].name == "Read" and run.steps[3].name == "Read" and run.steps[3].ref == "t1"
    assert run.title.startswith("Add a --verbose flag") and run.outcome == "Added the flag and a test."
    assert run.started.isoformat().startswith("2026-05-01T10:00:00")
    assert run.id.startswith("claude-code-session-")


def test_parse_hook_and_redaction(tmp_path: Path) -> None:
    assert detect_run_format(RUN_A) == "jsonl_hook"
    run = parse_run(RUN_A)
    assert len(run.steps) == 12 and run.steps[2].kind == "tool_call" and run.steps[2].ref == "t1"
    assert run.steps[3].ref == "t1" and run.steps[3].output_hash and not run.steps[3].input_hash
    assert '"cmd": "pytest' in run.steps[2].content
    f = tmp_path / "leak.jsonl"
    f.write_text(
        json.dumps(
            {
                "kind": "tool_result",
                "name": "bash",
                "content": "token is sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789",
            }
        )
        + "\n"
    )
    leaky = parse_run(f)
    assert "sk-ant" not in leaky.steps[0].content and "[REDACTED:token]" in leaky.steps[0].content


def test_capture_is_idempotent_and_static(vault_dir: Path) -> None:
    store = RunStore(Vault(vault_dir))
    rep = store.capture(RUN_A)
    assert rep.changed and len(rep.written) == 4
    d = store.dir(rep.run.id)
    for name in ("run.json", "steps.jsonl", "run.md", "viewer.html"):
        assert (d / name).exists()
    html = (d / "viewer.html").read_text()
    assert "http://" not in html and "https://" not in html and 'type="application/json"' in html
    assert "Fix the failing" not in html and "test_downsample_keeps_peaks" in html
    assert "kind: run" in (d / "run.md").read_text() and "| 3 | tool_result | bash |" in (d / "run.md").read_text()
    before = tree_digest(vault_dir)
    rep2 = store.capture(RUN_A)
    assert not rep2.changed and tree_digest(vault_dir) == before
    assert [r.id for r in store.list()] == [rep.run.id]
    assert store.get(rep.run.id[:8]).id == rep.run.id


def test_diff_finds_changed_tool_result() -> None:
    a, b = parse_run(RUN_A), parse_run(RUN_B)
    d = diff_runs(a, b)
    assert not d.same_outcome and d.changes
    cause = d.likely_cause
    assert cause.kind == "changed_result" and cause.a.name == "bash" and cause.a.index == 3 and cause.b.index == 3
    assert d.first_divergence == (3, 3)
    assert "tool result of bash differs (step 3 vs 3)" in d.summary()
    same = diff_runs(a, parse_run(RUN_A))
    assert same.same_outcome and not same.changes and "identical" in same.summary()


def test_cli_capture_show_diff(vault_dir: Path) -> None:
    common = ["--vault", str(vault_dir)]
    r = runner.invoke(app, ["replay", "capture", str(RUN_A), str(RUN_B), *common])
    assert r.exit_code == 0, r.output
    assert r.output.count("captured ") == 2
    r = runner.invoke(app, ["replay", "list", *common])
    assert r.exit_code == 0 and "fix-test-run-a" in r.output and "12 steps" in r.output
    ids = [line.split()[0] for line in r.output.splitlines()]
    r = runner.invoke(app, ["replay", "show", ids[0], *common])
    assert r.exit_code == 0 and "[  3] tool_result bash" in r.output and "outcome:" in r.output
    r = runner.invoke(app, ["replay", "show", ids[0], "--step", "3", *common])
    assert "expected 4.8" in r.output
    r = runner.invoke(app, ["replay", "diff", ids[0], ids[1], *common])
    assert r.exit_code == 0, r.output
    assert "outcome differs" in r.output and "Likely cause" in r.output and "Written:" in r.output
    folder = next(vault_dir.glob("runs/*__vs__*"))
    assert (folder / "diff.html").exists() and (folder / "diff.md").exists()
    assert "next difference" in (folder / "diff.html").read_text()
    r = runner.invoke(app, ["replay", "diff", ids[0], ids[1], *common])
    assert "No changes." in r.output
    r = runner.invoke(app, ["replay", "show", "nope", *common])
    assert r.exit_code == 1
    r = runner.invoke(app, ["replay", "capture", str(RUN_A), *common, "--format", "bogus"])
    assert r.exit_code == 1
