"""`afterthought decide ...` subcommands."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from ..vault import Vault
from .store import DecisionStore, parse_assumption, to_json

decide_app = typer.Typer(
    name="decide",
    help="Decision ledger: record, confirm, review and check assumptions.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

VaultOpt = Annotated[
    Path | None,
    typer.Option("--vault", "-v", help="Vault folder (default: $AFTERTHOUGHT_VAULT or ./vault).", show_default=False),
]


def _store(vault: Path | None) -> DecisionStore:
    v = Vault.resolve(vault)
    if not v.exists():
        typer.echo(f"No vault at {v.root}. Run `afterthought init`.", err=True)
        raise typer.Exit(code=1)
    return DecisionStore(v)


def _reindex(store: DecisionStore) -> None:
    from ..compile.merge import MergeStats, rebuild_index

    rebuild_index(store.vault, MergeStats())


def _print_decision(d, path: Path | None = None) -> None:
    flag = {"staged": "?", "confirmed": "*", "superseded": "-"}[d.status]
    when = d.decided_on.isoformat() if d.decided_on else "undated"
    open_n = sum(1 for a in d.assumptions if a.status == "open")
    typer.echo(f"{flag} {d.id}  {when}  {d.question}")
    typer.echo(f"      chosen: {d.chosen}")
    if d.assumptions:
        typer.echo(f"      assumptions: {len(d.assumptions)} ({open_n} open)")


@decide_app.command("list")
def list_cmd(
    vault: VaultOpt = None,
    status: Annotated[str, typer.Option(help="all, staged or confirmed")] = "all",
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """List decisions. `?` staged, `*` confirmed."""
    store = _store(vault)
    decisions = store.list(status)
    if as_json:
        typer.echo(to_json(decisions))
        return
    if not decisions:
        typer.echo("No decisions yet. Compile some chats or run `afterthought decide new`.")
        return
    for d in decisions:
        _print_decision(d)


@decide_app.command()
def show(
    decision_id: Annotated[str, typer.Argument(help="Decision id, e.g. D-913ef655")], vault: VaultOpt = None
) -> None:
    """Print a decision page."""
    store = _store(vault)
    try:
        _, _, path = store.get(decision_id)
    except KeyError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    typer.echo(path.read_text(encoding="utf-8"), nl=False)


@decide_app.command()
def new(
    vault: VaultOpt = None,
    question: Annotated[str | None, typer.Option("--question", "-q")] = None,
    chosen: Annotated[str | None, typer.Option("--chosen", "-c")] = None,
    option: Annotated[
        list[str] | None, typer.Option("--option", "-o", help="Repeat for each option considered.")
    ] = None,
    reasoning: Annotated[str | None, typer.Option("--reasoning", "-r")] = None,
    assumption: Annotated[
        list[str] | None,
        typer.Option("--assumption", "-a", help="'text | confidence | YYYY-MM-DD'. Repeat as needed."),
    ] = None,
    decider: Annotated[str | None, typer.Option("--decider")] = None,
    decided_on: Annotated[str | None, typer.Option("--on", help="Date decided, YYYY-MM-DD. Defaults to today.")] = None,
    check_in: Annotated[
        int, typer.Option("--check-in", help="Days until assumptions without a date are checked.")
    ] = 30,
) -> None:
    """Record a decision by hand. Prompts for anything not passed as a flag."""
    store = _store(vault)
    question = question or typer.prompt("Question")
    options = list(option or [])
    if not options:
        typer.echo("Options considered (empty line to finish):")
        while True:
            o = typer.prompt("  option", default="", show_default=False)
            if not o:
                break
            options.append(o)
    chosen = chosen or typer.prompt("Chosen option")
    if chosen not in options:
        options.append(chosen)
    reasoning = reasoning if reasoning is not None else typer.prompt("Reasoning", default="", show_default=False)
    specs = list(assumption or [])
    if assumption is None:
        typer.echo("Assumptions as 'text | confidence | YYYY-MM-DD' (empty line to finish):")
        while True:
            a = typer.prompt("  assumption", default="", show_default=False)
            if not a:
                break
            specs.append(a)
    when = date.fromisoformat(decided_on) if decided_on else date.today()
    from datetime import timedelta

    assumptions = []
    for spec in specs:
        a = parse_assumption(spec)
        if a.check_by is None:
            a = a.model_copy(update={"check_by": when + timedelta(days=check_in)})
        assumptions.append(a)
    cfg_user = store.vault.config().get("user")
    decision, created = store.create(
        question=question,
        chosen=chosen,
        options=options,
        reasoning=reasoning or "",
        assumptions=assumptions,
        decider=decider or cfg_user,
        decided_on=when,
    )
    _reindex(store)
    typer.echo(("Recorded " if created else "Already recorded ") + f"{decision.id}: {decision.question}")


@decide_app.command()
def confirm(
    decision_id: Annotated[str, typer.Argument()],
    vault: VaultOpt = None,
    decider: Annotated[str | None, typer.Option("--decider")] = None,
    check_in: Annotated[
        int | None, typer.Option("--check-in", help="Days from the decision date to check assumptions.")
    ] = None,
    check_by: Annotated[str | None, typer.Option("--check-by", help="Fixed check date, YYYY-MM-DD.")] = None,
    confidence: Annotated[
        list[str] | None,
        typer.Option("--confidence", help="index=value, e.g. 0=0.8. Repeat as needed."),
    ] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", hidden=True)] = None,
) -> None:
    """Accept a staged decision. Assumptions get a check-by date (default 30 days)."""
    store = _store(vault)
    confidences = {}
    for spec in confidence or []:
        i, _, val = spec.partition("=")
        confidences[int(i)] = float(val)
    try:
        decision, changed = store.confirm(
            decision_id,
            decider=decider or store.vault.config().get("user"),
            check_in_days=check_in if (check_in or check_by) else 30,
            check_by=date.fromisoformat(check_by) if check_by else None,
            confidences=confidences,
            today=date.fromisoformat(as_of) if as_of else None,
        )
    except (KeyError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    _reindex(store)
    if changed:
        typer.echo(f"Confirmed {decision.id}: {decision.question}")
        for a in decision.assumptions:
            typer.echo(f"  check by {a.check_by}: {a.text}")
    else:
        typer.echo(f"{decision.id} is already confirmed; nothing to do.")


@decide_app.command()
def reject(
    decision_id: Annotated[str, typer.Argument()],
    vault: VaultOpt = None,
    reason: Annotated[str | None, typer.Option("--reason")] = None,
) -> None:
    """Drop a staged decision. compile will not stage it again."""
    store = _store(vault)
    try:
        store.reject(decision_id, reason)
    except (KeyError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    _reindex(store)
    typer.echo(f"Rejected {decision_id}.")


@decide_app.command()
def check(
    decision_id: Annotated[str, typer.Argument()],
    index: Annotated[int, typer.Argument(help="Assumption number, starting at 0.")],
    vault: VaultOpt = None,
    held: Annotated[bool, typer.Option("--held", help="The assumption turned out true.")] = False,
    failed: Annotated[bool, typer.Option("--failed", help="The assumption turned out false.")] = False,
    unknown: Annotated[bool, typer.Option("--unknown", help="Could not tell.")] = False,
    note: Annotated[str | None, typer.Option("--note")] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", hidden=True)] = None,
) -> None:
    """Record whether one assumption held."""
    outcomes = [o for o, flag in (("held", held), ("failed", failed), ("unknown", unknown)) if flag]
    if len(outcomes) != 1:
        typer.echo("Pass exactly one of --held, --failed, --unknown.", err=True)
        raise typer.Exit(code=1)
    store = _store(vault)
    try:
        decision, changed = store.check(
            decision_id, index, outcomes[0], note=note, today=date.fromisoformat(as_of) if as_of else None
        )
    except (KeyError, IndexError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    a = decision.assumptions[index]
    typer.echo(f"{decision.id} assumption {index} {a.status}: {a.text}" + ("" if changed else " (unchanged)"))


@decide_app.command()
def review(
    vault: VaultOpt = None,
    as_of: Annotated[str | None, typer.Option("--as-of", help="Pretend today is this date, YYYY-MM-DD.")] = None,
    all_open: Annotated[bool, typer.Option("--all", help="Include assumptions not yet due.")] = False,
    list_only: Annotated[bool, typer.Option("--list", help="Do not prompt; just list what is due.")] = False,
) -> None:
    """Walk through assumptions whose check-by date has passed and ask whether they held."""
    store = _store(vault)
    today = date.fromisoformat(as_of) if as_of else date.today()
    due = store.due(today, include_all=all_open)
    if not due:
        typer.echo("Nothing due. Every open assumption has a check-by date in the future.")
        return
    typer.echo(f"{len(due)} assumption(s) due as of {today.isoformat()}:")
    for item in due:
        a = item.assumption
        late = (today - a.check_by).days if a.check_by else None
        when = f"due {a.check_by} ({late} days ago)" if late is not None and late > 0 else f"due {a.check_by}"
        typer.echo(f"\n{item.decision.id}  {item.decision.question}")
        typer.echo(f"  [{item.index}] {a.text}  (confidence {a.confidence:.2f}, {when})")
        if list_only:
            continue
        answer = typer.prompt("  Did it hold? [y]es / [n]o / [u]nknown / [s]kip", default="s", show_default=False)
        outcome = {"y": "held", "n": "failed", "u": "unknown"}.get(answer.strip().lower()[:1])
        if outcome is None:
            continue
        note = typer.prompt("  Note", default="", show_default=False) or None
        store.check(item.decision.id, item.index, outcome, note=note, today=today)
        typer.echo(f"  recorded: {outcome}")
    if not list_only:
        _reindex(store)
