"""Thin wrapper over the git command line. No server, no library."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..util import slugify


class GitError(RuntimeError):
    pass


def run(args: list[str], cwd: Path, *, user: str | None = None, check: bool = True) -> str:
    cmd = ["git"]
    if user:
        cmd += ["-c", f"user.name={user}", "-c", f"user.email={slugify(user)}@afterthought.invalid"]
    cmd += args
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def is_repo(path: Path) -> bool:
    return (path / ".git").exists()


def init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if not is_repo(path):
        run(["init", "-q", "-b", "main"], path)


def dirty(path: Path) -> bool:
    return bool(run(["status", "--porcelain"], path).strip())


def commit_all(path: Path, message: str, user: str) -> str | None:
    if not dirty(path):
        return None
    run(["add", "-A"], path)
    run(["commit", "-q", "-m", message], path, user=user)
    return run(["rev-parse", "--short", "HEAD"], path).strip()


def has_remote(path: Path) -> bool:
    return bool(run(["remote"], path).strip())


def push(path: Path) -> None:
    run(["push", "-q", "-u", "origin", "HEAD"], path)


def clone_or_pull(url: str, dest: Path) -> str:
    if is_repo(dest):
        run(["pull", "-q", "--ff-only"], dest)
        return "pulled"
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "-q", url, str(dest)], dest.parent)
    return "cloned"


def head(path: Path) -> str | None:
    try:
        return run(["rev-parse", "--short", "HEAD"], path).strip()
    except GitError:
        return None
