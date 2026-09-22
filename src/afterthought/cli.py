"""Afterthought command line."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .vault import Vault

app = typer.Typer(
    name="afterthought",
    help="What happens after the answer: compile, decide, verify, share, replay and coach.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
)

VaultOpt = Annotated[
    Path | None,
    typer.Option(
        "--vault",
        "-v",
        help="Vault folder (default: $AFTERTHOUGHT_VAULT or ./vault).",
        show_default=False,
    ),
]


def _echo_paths(label: str, paths: list[str], limit: int = 40) -> None:
    if not paths:
        return
    typer.echo(f"{label} ({len(paths)}):")
    for p in paths[:limit]:
        typer.echo(f"  {p}")
    if len(paths) > limit:
        typer.echo(f"  ... and {len(paths) - limit} more")


@app.callback()
def _root() -> None:
    pass


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(f"afterthought {__version__}")


@app.command()
def init(
    vault: VaultOpt = None,
    user: Annotated[
        str | None, typer.Option(help="Your name, stamped on pages you publish.")
    ] = None,
) -> None:
    """Create the vault folder layout, config and .afterthoughtignore."""
    v = Vault.resolve(vault)
    created = v.init(user=user)
    if created:
        typer.echo(f"Initialised vault at {v.root}")
        for p in created:
            typer.echo(f"  created {v.rel(p)}")
    else:
        typer.echo(f"Vault at {v.root} already initialised; nothing to do.")


@app.command()
def compile(
    inputs: Annotated[
        list[Path], typer.Argument(help="Export files or folders to ingest.", exists=True)
    ],
    vault: VaultOpt = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Never call a model; replay fixtures only.")
    ] = False,
    record: Annotated[
        bool, typer.Option("--record", help="Save live model responses as fixtures.")
    ] = False,
    fixtures: Annotated[
        list[Path] | None, typer.Option("--fixtures", help="Extra fixture folder(s).")
    ] = None,
    fmt: Annotated[
        str | None,
        typer.Option(
            "--format", help="Force a format: chatgpt, claude, claude_code, slack, markdown."
        ),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", help="List every page written.")] = False,
) -> None:
    """Compile chat exports into wiki pages. Incremental and idempotent."""
    from .compile import compile_inputs
    from .llm import FixtureMissingError, get_provider

    v = Vault.resolve(vault)
    if not v.exists():
        v.init()
    cfg = v.config()
    dirs: list[Path] = list(fixtures or [])
    if cfg.get("llm", {}).get("fixtures"):
        dirs.append(Path(cfg["llm"]["fixtures"]))
    dirs.append(v.cache_dir)
    provider = get_provider(cfg, dry_run=dry_run, fixture_dirs=dirs, record=record)
    try:
        report = compile_inputs(v, inputs, provider=provider, fmt=fmt)
    except FixtureMissingError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from None

    typer.echo(f"Vault: {v.root}")
    typer.echo(f"Inputs: {', '.join(report.files) or 'none'}")
    if report.ignored:
        typer.echo(f"Ignored by .afterthoughtignore: {len(report.ignored)}")
    typer.echo(
        f"Conversations: {report.conversations} "
        f"({report.conversations_with_new} with new material), "
        f"new messages: {report.new_messages}, already processed: {report.skipped_messages}"
    )
    typer.echo(f"Redactions applied: {report.redactions}; model calls: {report.llm_calls}")
    st = report.stats
    typer.echo(
        f"Pages written: {len(st.written)}, unchanged: {len(st.unchanged)}, "
        f"decisions staged: {st.decisions_staged}, questions: {st.questions}, "
        f"unverified facts: {st.unverified_facts}"
    )
    if verbose:
        _echo_paths("Written", st.written)
    if not report.changed:
        typer.echo("No changes.")


@app.command()
def redact(
    path: Annotated[Path, typer.Argument(exists=True, help="File to redact (prints to stdout).")],
) -> None:
    """Show a file with emails, tokens and card numbers redacted."""
    from .redact import redact as _redact

    text, rep = _redact(path.read_text(encoding="utf-8"))
    typer.echo(text, nl=False)
    typer.echo(
        f"\n[redacted {rep.emails} emails, {rep.tokens} tokens, {rep.cards} card numbers]", err=True
    )


@app.command()
def status(vault: VaultOpt = None) -> None:
    """Summarise what is in the vault."""
    v = Vault.resolve(vault)
    if not v.exists():
        typer.echo(f"No vault at {v.root}. Run `afterthought init`.")
        raise typer.Exit(code=1)
    from .compile.state import CompileState

    state = CompileState(v)
    typer.echo(f"Vault: {v.root}")
    typer.echo(
        f"Processed messages: {len(state.processed)}; extraction batches: {len(state.batches)}"
    )
    for sub in ("entities", "decisions", "questions", "timeline", "claims", "runs", "coach"):
        n = len(v.pages(sub))
        if n:
            typer.echo(f"  {sub}: {n} pages")


if __name__ == "__main__":  # pragma: no cover
    app()
