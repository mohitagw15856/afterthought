"""`afterthought coach ...` subcommands."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from ..vault import Vault
from .interview import QUESTIONS, Profile, answers_from_file, load_profile, save_profile
from .plan import make_plan
from .progress import Progress, to_json

coach_app = typer.Typer(
    name="coach",
    help="Onboarding coach: interview, 30-day curriculum, progress that feeds the wiki.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
VaultOpt = Annotated[Path | None, typer.Option("--vault", "-v", help="Vault folder.", show_default=False)]
AsOf = Annotated[str | None, typer.Option("--as-of", help="Pretend today is this date, YYYY-MM-DD.")]


def _vault(vault: Path | None) -> Vault:
    v = Vault.resolve(vault)
    if not v.exists():
        v.init()
    return v


def _progress(vault: Path | None) -> Progress:
    return Progress(_vault(vault))


def _date(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


@coach_app.command()
def interview(
    vault: VaultOpt = None,
    answers: Annotated[
        Path | None, typer.Option("--answers", help="JSON file of answers keyed by question id, instead of prompting.")
    ] = None,
    name: Annotated[str | None, typer.Option("--name")] = None,
) -> None:
    """Answer eight questions about your real work. Writes coach/profile.md."""
    v = _vault(vault)
    if answers:
        try:
            got = answers_from_file(answers)
        except (ValueError, OSError) as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=1) from None
    else:
        typer.echo("Eight questions. Short, honest answers work best. Press Enter to skip one.\n")
        got = {}
        for key, question in QUESTIONS:
            a = typer.prompt(question, default="", show_default=False).strip()
            if a:
                got[key] = a
    if not got:
        typer.echo("No answers given; nothing written.", err=True)
        raise typer.Exit(code=1)
    cfg = v.config()
    if name and not cfg.get("user"):
        cfg["user"] = name
        v.save_config(cfg)
    profile = Profile(name=name or cfg.get("user"), answers=got)
    written = save_profile(v, profile)
    typer.echo(f"Profile saved with {len(got)} of {len(QUESTIONS)} answers." + (" No changes." if not written else ""))
    typer.echo("Next: `afterthought coach plan`.")


@coach_app.command()
def plan(
    vault: VaultOpt = None,
    days: Annotated[int, typer.Option("--days", min=7, max=90)] = 30,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    record: Annotated[bool, typer.Option("--record")] = False,
    fixtures: Annotated[list[Path] | None, typer.Option("--fixtures")] = None,
    start: Annotated[
        str | None, typer.Option("--start", help="Start date, YYYY-MM-DD. Defaults to the day you first mark an item.")
    ] = None,
) -> None:
    """Generate the curriculum from the profile. Writes coach/curriculum.md."""
    from ..llm import FixtureMissingError, get_provider

    v = _vault(vault)
    profile = load_profile(v)
    if profile is None:
        typer.echo("No profile. Run `afterthought coach interview` first.", err=True)
        raise typer.Exit(code=1)
    cfg = v.config()
    dirs: list[Path] = list(fixtures or [])
    if cfg.get("llm", {}).get("fixtures"):
        dirs.append(Path(cfg["llm"]["fixtures"]))
    dirs.append(v.cache_dir)
    provider = get_provider(cfg, dry_run=dry_run, fixture_dirs=dirs, record=record)
    try:
        items, written = make_plan(v, profile, provider, days=days, started=_date(start))
    except FixtureMissingError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(f"{len(items)} tasks over {days} days." + (" No changes." if not written else ""))
    for it in items[:5]:
        typer.echo(f"  Day {it.day}: {it.task} [{it.skill}]")
    if len(items) > 5:
        typer.echo("  ... see coach/curriculum.md for the rest")


@coach_app.command()
def today(vault: VaultOpt = None, as_of: AsOf = None) -> None:
    """Show the tasks due so far that are not done."""
    p = _progress(vault)
    try:
        due = p.due(_date(as_of))
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    if not due:
        typer.echo("Nothing due. You are up to date.")
        return
    for it in due:
        typer.echo(f"{it.id}  Day {it.day}: {it.task}")
        typer.echo(f"      skill: {it.skill}" + (f"; why: {it.why}" if it.why else ""))


def _mark(vault: Path | None, ref: str, status: str, note: str | None, evidence: str | None, as_of: str | None) -> None:
    p = _progress(vault)
    try:
        it, written = p.mark(ref, status, note=note, evidence=evidence, today=_date(as_of))
    except (FileNotFoundError, KeyError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"{it.id} {it.status}: {it.task}" + ("" if written else " (unchanged)"))


@coach_app.command()
def done(
    ref: Annotated[str, typer.Argument(help="Item id, prefix, or day number.")],
    vault: VaultOpt = None,
    note: Annotated[str | None, typer.Option("--note")] = None,
    evidence: Annotated[str | None, typer.Option("--evidence", help="File or page that shows the work.")] = None,
    as_of: AsOf = None,
) -> None:
    """Mark a task done. Updates the curriculum, coach/skills.md and your person page."""
    _mark(vault, ref, "done", note, evidence, as_of)


@coach_app.command()
def skip(
    ref: Annotated[str, typer.Argument()],
    vault: VaultOpt = None,
    note: Annotated[str | None, typer.Option("--note")] = None,
    as_of: AsOf = None,
) -> None:
    """Skip a task."""
    _mark(vault, ref, "skipped", note, None, as_of)


@coach_app.command()
def status(vault: VaultOpt = None, as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Progress so far and the skills you have shown."""
    p = _progress(vault)
    try:
        s = p.summary()
        _, items = p.load()
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    if as_json:
        typer.echo(to_json(items))
        return
    typer.echo(
        f"{s['done']} done, {s['skipped']} skipped, {s['todo']} to go of {s['days']} days"
        + (f"; started {s['started']}" if s["started"] else "; not started")
    )
    if s["skills"]:
        typer.echo("Skills shown:")
        for skill, n in s["skills"].items():
            typer.echo(f"  {skill}: {n}")
    if s["last_done"]:
        typer.echo(f"Last done: {s['last_done']}")
