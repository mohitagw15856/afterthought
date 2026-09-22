"""`afterthought replay ...` subcommands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..vault import Vault
from .store import RunStore

replay_app = typer.Typer(
    name="replay",
    help="Agent flight recorder: capture runs, step through them, diff two runs.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
VaultOpt = Annotated[Path | None, typer.Option("--vault", "-v", help="Vault folder.", show_default=False)]


def _store(vault: Path | None) -> RunStore:
    v = Vault.resolve(vault)
    if not v.exists():
        v.init()
    return RunStore(v)


@replay_app.command()
def capture(
    files: Annotated[list[Path], typer.Argument(exists=True, help="Claude Code .jsonl transcripts or hook logs.")],
    vault: VaultOpt = None,
    fmt: Annotated[str | None, typer.Option("--format", help="claude_code or jsonl_hook (sniffed by default).")] = None,
    run_id: Annotated[str | None, typer.Option("--id", help="Run id (single file only).")] = None,
) -> None:
    """Record one or more runs into the vault, with a static HTML viewer each."""
    store = _store(vault)
    if run_id and len(files) > 1:
        typer.echo("--id works with a single file.", err=True)
        raise typer.Exit(code=1)
    for f in files:
        try:
            rep = store.capture(f, fmt, run_id)
        except ValueError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=1) from None
        r = rep.run
        state = "captured" if rep.changed else "unchanged"
        typer.echo(f"{state} {r.id}: {len(r.steps)} steps from {f.name} ({r.source})")
        typer.echo(f"  viewer: {store.dir(r.id) / 'viewer.html'}")


@replay_app.command("list")
def list_cmd(vault: VaultOpt = None) -> None:
    """List captured runs."""
    store = _store(vault)
    runs = store.list()
    if not runs:
        typer.echo("No runs yet. Try `afterthought replay capture <session.jsonl>`.")
        return
    for r in runs:
        when = r.started.strftime("%Y-%m-%d %H:%M") if r.started else "undated"
        typer.echo(f"{r.id}  {when}  {len(r.steps):>3} steps  {r.title or ''}")


@replay_app.command()
def show(
    run_id: Annotated[str, typer.Argument(help="Run id or unique prefix.")],
    vault: VaultOpt = None,
    step: Annotated[int | None, typer.Option("--step", help="Print one step in full.")] = None,
    full: Annotated[bool, typer.Option("--full", help="Print every step in full.")] = False,
) -> None:
    """Replay a run in the terminal."""
    store = _store(vault)
    try:
        run = store.get(run_id)
    except KeyError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    if step is not None:
        if not 0 <= step < len(run.steps):
            typer.echo(f"Run has {len(run.steps)} steps.", err=True)
            raise typer.Exit(code=1)
        s = run.steps[step]
        typer.echo(f"[{s.index}] {s.kind}{' ' + s.name if s.name else ''} {s.ts.isoformat() if s.ts else ''}")
        typer.echo(s.content)
        return
    typer.echo(f"{run.id}: {run.title or ''}")
    typer.echo(f"{run.source_file} ({run.source}), {len(run.steps)} steps")
    for s in run.steps:
        preview = s.content if full else s.content.replace("\n", " ")[:100]
        typer.echo(f"[{s.index:>3}] {s.kind:<11} {(s.name or ''):<14} {preview}")
    if run.outcome:
        typer.echo(f"outcome: {run.outcome.replace(chr(10), ' ')[:200]}")


@replay_app.command()
def diff(
    a: Annotated[str, typer.Argument()],
    b: Annotated[str, typer.Argument()],
    vault: VaultOpt = None,
    no_write: Annotated[bool, typer.Option("--no-write", help="Do not write the diff folder.")] = False,
) -> None:
    """Align two runs and say where they diverged and which tool result or context changed."""
    store = _store(vault)
    try:
        d, written = store.diff(a, b, write=not no_write)
    except KeyError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    typer.echo(d.summary())
    for c in d.changes:
        typer.echo(f"  {c.describe()}")
    if d.likely_cause and not d.same_outcome:
        typer.echo(f"Likely cause of the different outcome: {d.likely_cause.describe()}")
    if written:
        typer.echo("Written: " + ", ".join(written))
    elif not no_write:
        typer.echo("No changes.")
