import json
import os
import subprocess
from pathlib import Path

from conftest import tree_digest
from typer.testing import CliRunner

from afterthought.cli import app
from afterthought.compile import compile_inputs
from afterthought.llm import DryRunProvider, FixtureStore
from afterthought.pages import split_frontmatter
from afterthought.share import SharedRepo
from afterthought.vault import Vault

runner = CliRunner()
LANTERN = "entities/projects/lantern.md"
SIYU = "entities/people/siyu.md"


def _vault(path: Path, user: str, example_export: Path, example_fixtures: Path) -> Vault:
    v = Vault(path)
    v.init(user=user)
    compile_inputs(v, [example_export], provider=DryRunProvider(FixtureStore([example_fixtures])))
    return v


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def test_init_and_publish_with_provenance(tmp_path, example_export, example_fixtures) -> None:
    v = _vault(tmp_path / "mo", "Mo", example_export, example_fixtures)
    repo = tmp_path / "team"
    r = runner.invoke(app, ["share", "init", str(repo), "--vault", str(v.root)])
    assert r.exit_code == 0, r.output
    assert (repo / ".git").exists() and (repo / "manifest.json").exists() and (repo / "README.md").exists()
    assert v.config()["share"]["repo"] == str(repo.resolve())

    r = runner.invoke(app, ["share", "publish", "entities/projects", SIYU, "--vault", str(v.root)])
    assert r.exit_code == 0, r.output
    assert "Published 2" in r.output and "Committed" in r.output
    mine = repo / "by" / "mo" / LANTERN
    canon = repo / "canonical" / LANTERN
    assert mine.exists() and canon.exists()
    fm, body = split_frontmatter(mine.read_text())
    assert fm["shared"]["publisher"] == "Mo" and fm["shared"]["tool"].startswith("afterthought ")
    assert fm["shared"]["published"].endswith("Z") and fm["shared"]["derived_from"]["origin"] == "llm"
    assert fm["shared"]["source_hash"] and fm["provenance"]["origin"] == "llm"
    assert "^at-llm-" in body  # page content untouched
    manifest = json.loads((repo / "manifest.json").read_text())
    assert manifest["pages"][LANTERN]["canonical"] == "mo"
    assert "Mo" == manifest["pages"][LANTERN]["versions"]["mo"]["publisher"]
    assert _git(repo, "log", "--oneline").count("\n") == 2
    assert "Mo <mo@afterthought.invalid>" in _git(repo, "log", "-1", "--format=%an <%ae>")

    # republish: nothing changes, no new commit
    before = tree_digest(repo / "by")
    r = runner.invoke(app, ["share", "publish", "entities/projects", SIYU, "--vault", str(v.root)])
    assert "No changes." in r.output and tree_digest(repo / "by") == before
    assert _git(repo, "log", "--oneline").count("\n") == 2


def test_never_publish_and_ignore(tmp_path, example_export, example_fixtures) -> None:
    v = _vault(tmp_path / "mo", "Mo", example_export, example_fixtures)
    repo = SharedRepo.init(tmp_path / "team", "Mo")
    (v.root / ".afterthoughtignore").write_text("entities/people/**\n")
    r = runner.invoke(app, ["share", "publish", "--all", "--vault", str(v.root), "--repo", str(repo.path)])
    assert r.exit_code == 0, r.output
    published = sorted(
        p.relative_to(repo.path / "by" / "mo").as_posix() for p in (repo.path / "by" / "mo").rglob("*.md")
    )
    assert LANTERN in published and "index.md" in published
    assert not any(p.startswith(("decisions/staged", "claims/", "entities/people")) for p in published)
    r = runner.invoke(app, ["share", "publish", "decisions/staged", "--vault", str(v.root), "--repo", str(repo.path)])
    assert "skipped" in r.output and "No changes." in r.output


def test_conflict_page_and_resolution(tmp_path, example_export, example_fixtures) -> None:
    mo = _vault(tmp_path / "mo", "Mo", example_export, example_fixtures)
    siyu = _vault(tmp_path / "siyu", "Siyu", example_export, example_fixtures)
    repo = SharedRepo.init(tmp_path / "team", "Mo")
    repo.publish(mo, [LANTERN], user="Mo")
    page = siyu.root / LANTERN
    page.write_text(page.read_text() + "\n## Notes\nSiyu says the Pi is too slow.\n")
    rep = repo.publish(siyu, [LANTERN], user="Siyu")
    assert rep.conflicts == [LANTERN] and rep.commit
    conflict = repo.conflict_path(LANTERN)
    assert conflict.exists()
    fm, body = split_frontmatter(conflict.read_text())
    assert fm["kind"] == "conflict" and fm["canonical"] == "mo" and len(fm["versions"]) == 2
    assert (
        "```diff" in body
        and "+Siyu says the Pi is too slow." in body
        and "[[by/siyu/entities/projects/lantern|siyu]]" in body
    )
    assert "Siyu says" not in repo.canonical_path(LANTERN).read_text()  # canonical not overwritten
    assert "Siyu says" in repo.by_path("Siyu", LANTERN).read_text()
    assert json.loads(repo.manifest_path.read_text())["pages"][LANTERN]["conflict"] is True

    # Mo republishes unchanged: conflict persists, nothing written
    rep = repo.publish(mo, [LANTERN], user="Mo")
    assert rep.unchanged == [LANTERN] and rep.commit is None and conflict.exists()

    # Siyu publishes Mo's version: conflict resolved
    page.write_text((mo.root / LANTERN).read_text())
    rep = repo.publish(siyu, [LANTERN], user="Siyu")
    assert rep.resolved == [LANTERN] and not conflict.exists()
    assert "conflict" not in json.loads(repo.manifest_path.read_text())["pages"][LANTERN]


def test_subscribe_pull_and_readonly(tmp_path, example_export, example_fixtures) -> None:
    mo = _vault(tmp_path / "mo", "Mo", example_export, example_fixtures)
    repo = SharedRepo.init(tmp_path / "team", "Mo")
    repo.publish(mo, [LANTERN], user="Mo")

    reader = Vault(tmp_path / "reader")
    reader.init(user="Reader")
    r = runner.invoke(app, ["share", "subscribe", str(repo.path), "--vault", str(reader.root)])
    assert r.exit_code == 0, r.output
    assert "cloned team" in r.output
    mirrored = reader.root / "shared" / "team" / "canonical" / LANTERN
    assert mirrored.exists() and (reader.root / "shared" / "team" / "by" / "mo" / LANTERN).exists()
    assert not os.access(mirrored, os.W_OK)
    assert reader.config()["share"]["subscriptions"]["team"] == str(repo.path)

    repo.publish(mo, [SIYU], user="Mo")
    r = runner.invoke(app, ["share", "pull", "--vault", str(reader.root)])
    assert r.exit_code == 0 and "pulled" in r.output and "1 updated" in r.output.replace("2 updated", "1 updated")
    assert (reader.root / "shared" / "team" / "canonical" / SIYU).exists()
    r = runner.invoke(app, ["share", "pull", "--vault", str(reader.root)])
    assert "0 updated" in r.output

    # mirrored pages are not evidence and not compiled
    from afterthought.verify.evidence import build_index

    assert not any(e.page.startswith("shared/") for e in build_index(reader))

    r = runner.invoke(app, ["share", "unsubscribe", "team", "--vault", str(reader.root)])
    assert r.exit_code == 0 and not (reader.root / "shared" / "team").exists()
    assert "team" not in reader.config()["share"]["subscriptions"]


def test_push_to_remote(tmp_path, example_export, example_fixtures) -> None:
    mo = _vault(tmp_path / "mo", "Mo", example_export, example_fixtures)
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    repo = SharedRepo.init(tmp_path / "team", "Mo")
    _git(repo.path, "remote", "add", "origin", str(bare))
    rep = repo.publish(mo, [LANTERN], user="Mo", push=True)
    assert rep.pushed
    assert _git(bare, "log", "--oneline", "main").count("\n") == 2


def test_status_and_errors(tmp_path, example_export, example_fixtures) -> None:
    v = _vault(tmp_path / "anon", None, example_export, example_fixtures)
    r = runner.invoke(app, ["share", "publish", "--all", "--vault", str(v.root), "--repo", str(tmp_path / "nope")])
    assert r.exit_code == 1 and "needs a name" in r.output
    r = runner.invoke(app, ["share", "publish", "--all", "--vault", str(v.root), "--user", "Mo"])
    assert r.exit_code == 1 and "No shared repo" in r.output
    repo = SharedRepo.init(tmp_path / "team", "Mo")
    repo.publish(v, [LANTERN, SIYU], user="Mo")
    r = runner.invoke(app, ["share", "status", "--vault", str(v.root), "--repo", str(repo.path)])
    assert r.exit_code == 0 and "Pages: 2" in r.output and "mo: 2 page(s)" in r.output
