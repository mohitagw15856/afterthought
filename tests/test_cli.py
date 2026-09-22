from pathlib import Path

from typer.testing import CliRunner

from afterthought.cli import app

runner = CliRunner()


def test_init_and_status(vault_dir: Path) -> None:
    r = runner.invoke(app, ["init", "--vault", str(vault_dir), "--user", "Mo"])
    assert r.exit_code == 0 and "Initialised" in r.output
    assert (vault_dir / ".afterthoughtignore").exists()
    r = runner.invoke(app, ["init", "--vault", str(vault_dir)])
    assert "nothing to do" in r.output
    r = runner.invoke(app, ["status", "--vault", str(vault_dir)])
    assert r.exit_code == 0 and "Processed messages: 0" in r.output


def test_compile_dry_run(vault_dir: Path, example_export: Path, example_fixtures: Path) -> None:
    args = [
        "compile",
        str(example_export),
        "--vault",
        str(vault_dir),
        "--dry-run",
        "--fixtures",
        str(example_fixtures),
    ]
    r = runner.invoke(app, args)
    assert r.exit_code == 0, r.output
    assert "decisions staged: 4" in r.output
    r = runner.invoke(app, args)
    assert r.exit_code == 0 and "No changes." in r.output
    r = runner.invoke(app, ["status", "--vault", str(vault_dir)])
    assert "entities: 10 pages" in r.output


def test_compile_missing_fixture_fails_cleanly(vault_dir: Path, example_export: Path) -> None:
    r = runner.invoke(app, ["compile", str(example_export), "--vault", str(vault_dir), "--dry-run"])
    assert r.exit_code == 2
    assert "No fixture" in r.output


def test_redact_command(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hi a@b.com\n")
    r = runner.invoke(app, ["redact", str(f)])
    assert r.exit_code == 0 and "[REDACTED:email]" in r.output
