"""`afterthought verify` command."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from ..vault import Vault


def verify(
    source: Annotated[str, typer.Argument(help="File to verify, a vault page, or '-' for stdin.")],
    vault: Annotated[Path | None, typer.Option("--vault", "-v", help="Vault folder.", show_default=False)] = None,
    demand: Annotated[bool, typer.Option("--demand", help="Ask the model for evidence per claim and re-tag.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Never call a model; replay fixtures only.")] = False,
    record: Annotated[bool, typer.Option("--record", help="Save live model responses as fixtures.")] = False,
    fixtures: Annotated[list[Path] | None, typer.Option("--fixtures", help="Extra fixture folder(s).")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the claims as JSON instead of a summary.")] = False,
    no_write: Annotated[bool, typer.Option("--no-write", help="Do not write anything into the vault.")] = False,
    show: Annotated[bool, typer.Option("--show", help="Print the annotated text.")] = False,
    threshold: Annotated[
        float | None,
        typer.Option(
            "--threshold", min=0.0, max=1.0, help="Match strictness, 0 to 1 (config verify.threshold, default 0.5)."
        ),
    ] = None,
) -> None:
    """Extract claims from a model output and tag each SOURCED, INFERRED or UNVERIFIED."""
    from ..llm import FixtureMissingError, get_provider
    from .pipeline import claims_json, read_input, verify_text

    v = Vault.resolve(vault)
    if not v.exists():
        v.init()
    cfg = v.config()
    dirs: list[Path] = list(fixtures or [])
    if cfg.get("llm", {}).get("fixtures"):
        dirs.append(Path(cfg["llm"]["fixtures"]))
    dirs.append(v.cache_dir)
    provider = get_provider(cfg, dry_run=dry_run, fixture_dirs=dirs, record=record)

    if source == "-":
        text, slug, name = read_input(None, sys.stdin.read())
    else:
        p = Path(source)
        if not p.exists() and (v.root / source).exists():
            p = v.root / source
        if not p.exists():
            typer.echo(f"error: {source} not found", err=True)
            raise typer.Exit(code=1)
        text, slug, name = read_input(p, None)
    if not text.strip():
        typer.echo("error: nothing to verify", err=True)
        raise typer.Exit(code=1)

    try:
        report = verify_text(
            v,
            text,
            slug=slug,
            source_name=name,
            provider=provider,
            demand=demand,
            write=not no_write,
            threshold=threshold,
        )
    except FixtureMissingError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from None

    if as_json:
        typer.echo(claims_json(report.claims))
        return
    c = report.counts()
    typer.echo(f"Input: {name}; evidence items in vault: {report.evidence_items}; model calls: {report.llm_calls}")
    typer.echo(
        f"Claims: {len(report.claims)}  SOURCED {c['SOURCED']}  INFERRED {c['INFERRED']}  UNVERIFIED {c['UNVERIFIED']}"
    )
    for i, cl in enumerate(report.claims):
        extra = f" -> {cl.evidence}" if cl.tag == "SOURCED" else (f" -> {cl.reasoning}" if cl.tag == "INFERRED" else "")
        typer.echo(f"  [{i}] {cl.tag:<10} {cl.text}{extra}")
    if report.unlocated:
        typer.echo(f"  ({len(report.unlocated)} claim(s) could not be located in the text)")
    if report.written:
        typer.echo("Written: " + ", ".join(report.written))
    elif not no_write:
        typer.echo("No changes.")
    if show:
        typer.echo("")
        typer.echo(report.annotated, nl=False)
