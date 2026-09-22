"""`afterthought share ...` subcommands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..vault import Vault
from .git import GitError
from .mesh import SharedRepo, select_pages
from .subscribe import pull_subscriptions, subscribe, unsubscribe

share_app = typer.Typer(
    name="share",
    help="Team knowledge mesh: publish pages to a git repo, subscribe to others'.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

VaultOpt = Annotated[Path | None, typer.Option("--vault", "-v", help="Vault folder.", show_default=False)]
RepoOpt = Annotated[
    Path | None,
    typer.Option("--repo", "-r", help="Shared repo folder (default: share.repo in config).", show_default=False),
]


def _vault(vault: Path | None) -> Vault:
    v = Vault.resolve(vault)
    if not v.exists():
        typer.echo(f"No vault at {v.root}. Run `afterthought init`.", err=True)
        raise typer.Exit(code=1)
    return v


def _user(v: Vault, user: str | None) -> str:
    u = user or v.config().get("user")
    if not u:
        typer.echo("Publishing needs a name. Pass --user or set it with `afterthought init --user`.", err=True)
        raise typer.Exit(code=1)
    return u


def _repo(v: Vault, repo: Path | None) -> SharedRepo:
    path = repo or (Path(v.config().get("share", {}).get("repo")) if v.config().get("share", {}).get("repo") else None)
    if path is None:
        typer.echo("No shared repo. Run `afterthought share init <folder>` or pass --repo.", err=True)
        raise typer.Exit(code=1)
    if not path.exists():
        typer.echo(f"Shared repo {path} does not exist. Run `afterthought share init {path}`.", err=True)
        raise typer.Exit(code=1)
    return SharedRepo(path)


@share_app.command()
def init(
    path: Annotated[Path, typer.Argument(help="Folder for the shared repo (created if missing).")],
    vault: VaultOpt = None,
    user: Annotated[str | None, typer.Option("--user")] = None,
) -> None:
    """Create a shared repo (git init, README, manifest) and remember it in the vault config."""
    v = _vault(vault)
    u = _user(v, user)
    try:
        SharedRepo.init(path, u)
    except GitError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    cfg = v.config()
    cfg.setdefault("share", {})["repo"] = str(path.resolve())
    if not cfg.get("user"):
        cfg["user"] = u
    v.save_config(cfg)
    typer.echo(f"Shared repo ready at {path.resolve()}")


@share_app.command()
def publish(
    pages: Annotated[list[str] | None, typer.Argument(help="Vault-relative pages, folders or globs.")] = None,
    vault: VaultOpt = None,
    repo: RepoOpt = None,
    user: Annotated[str | None, typer.Option("--user")] = None,
    all_pages: Annotated[
        bool, typer.Option("--all", help="Everything except staged decisions, claims, runs, coach and shared.")
    ] = False,
    push: Annotated[bool, typer.Option("--push", help="git push after committing, if the repo has a remote.")] = False,
) -> None:
    """Publish pages with provenance. Never overwrites another person's version."""
    v = _vault(vault)
    u = _user(v, user)
    r = _repo(v, repo)
    if not pages and not all_pages:
        typer.echo("Name some pages or pass --all.", err=True)
        raise typer.Exit(code=1)
    rels = select_pages(v, list(pages or []), all_pages)
    if not rels:
        typer.echo("Nothing matched.", err=True)
        raise typer.Exit(code=1)
    try:
        rep = r.publish(v, rels, user=u, push=push)
    except GitError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Repo: {r.path}")
    typer.echo(f"Published {len(rep.published)}, unchanged {len(rep.unchanged)}, skipped {len(rep.skipped)}")
    for rel in rep.published:
        typer.echo(f"  + {rel}")
    for rel in rep.skipped:
        typer.echo(f"  - {rel} (ignored or never published)")
    if rep.conflicts:
        typer.echo("Conflicts (see conflicts/ in the repo):")
        for rel in rep.conflicts:
            typer.echo(f"  ! {rel}")
    for rel in rep.resolved:
        typer.echo(f"  resolved {rel}")
    if rep.commit:
        typer.echo(f"Committed {rep.commit}" + (" and pushed" if rep.pushed else ""))
    else:
        typer.echo("No changes.")


@share_app.command()
def status(vault: VaultOpt = None, repo: RepoOpt = None) -> None:
    """What is in the shared repo, and by whom."""
    v = _vault(vault)
    r = _repo(v, repo)
    s = r.status()
    typer.echo(f"Repo: {s['path']} (HEAD {s['head'] or 'none'})")
    typer.echo(f"Pages: {s['pages']}; conflicts: {len(s['conflicts'])}")
    for pub, n in sorted(s["publishers"].items()):
        typer.echo(f"  {pub}: {n} page(s)")
    for rel in s["conflicts"]:
        typer.echo(f"  ! {rel}")
    subs = v.config().get("share", {}).get("subscriptions", {})
    if subs:
        typer.echo("Subscriptions:")
        for name, url in sorted(subs.items()):
            typer.echo(f"  {name}: {url}")


@share_app.command("subscribe")
def subscribe_cmd(
    url: Annotated[str, typer.Argument(help="Git URL or local path of a shared repo.")],
    vault: VaultOpt = None,
    name: Annotated[str | None, typer.Option("--name", help="Folder name under vault/shared/.")] = None,
) -> None:
    """Pull someone else's published pages into vault/shared/<name>/, read-only."""
    v = _vault(vault)
    try:
        rep = subscribe(v, url, name)
    except GitError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"{rep.action} {rep.name} at {rep.head or 'empty'}: {rep.files} page(s), {len(rep.changed)} updated")


@share_app.command()
def pull(vault: VaultOpt = None, name: Annotated[str | None, typer.Option("--name")] = None) -> None:
    """Refresh every subscription (or one with --name)."""
    v = _vault(vault)
    try:
        reports = pull_subscriptions(v, name)
    except GitError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None
    if not reports:
        typer.echo("No subscriptions. Run `afterthought share subscribe <repo>`.")
        return
    for rep in reports:
        typer.echo(
            f"{rep.name}: {rep.action} at {rep.head or 'empty'}, {rep.files} page(s), {len(rep.changed)} updated, {rep.removed} removed"
        )


@share_app.command("unsubscribe")
def unsubscribe_cmd(name: Annotated[str, typer.Argument()], vault: VaultOpt = None) -> None:
    """Remove a subscription and its mirrored pages."""
    v = _vault(vault)
    if unsubscribe(v, name):
        typer.echo(f"Removed subscription {name}.")
    else:
        typer.echo(f"No subscription named {name}.", err=True)
        raise typer.Exit(code=1)
