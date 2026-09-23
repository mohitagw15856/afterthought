# Contributing

Thanks for helping. Afterthought is small and opinionated; the notes below keep it that way.

## Setup

```bash
uv sync
uv run pytest
uv run ruff check src tests
```

Python 3.12 is the floor. `uv` is the recommended tool but plain `pip install -e ".[all]"` works.

## Ground rules

- **Plain files only.** Markdown and JSON in the vault. No database, no web framework in v1.
- **No invented facts.** If code would need to guess a citation, source id or date, it must mark the output UNVERIFIED instead. Tests should cover the unverified path.
- **Idempotent.** Every command must produce no changes when run twice. There is a test for this on `compile`; add one for anything new.
- **Tests run without keys.** Model calls go through `afterthought.llm` with fixtures under `tests/fixtures/llm/<task>/<key>.json`. Tests that need a real model are marked `@pytest.mark.live` and only run with `pytest --live` and an `ANTHROPIC_API_KEY`.
- **Obsidian compatible.** Frontmatter, `[[wikilinks]]` and `^block-ids` must render in Obsidian without plugins.
- **British English** in docs and user-facing strings. No em dashes anywhere.

## Commits

Conventional commits, kept small: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`. Commit after every green test run.

## Adding an ingest format

1. Add `src/afterthought/ingest/<name>.py` with a `parse(path) -> Iterator[Message]`.
2. Register it in `ingest/__init__.py` and teach `detect_format` to sniff it.
3. Add a tiny fixture under `tests/fixtures/ingest/` and a test.

## Recording fixtures

```bash
uv run afterthought compile <export> --vault /tmp/v --record --fixtures tests/fixtures/llm
```

Check the recorded JSON for anything private before committing it.

## Releasing

1. Move the `Unreleased` notes in `CHANGELOG.md` under a new version heading with today's date and bump `version` in `pyproject.toml`.
2. Commit, then `git tag vX.Y.Z && git push --tags`.
3. The release workflow builds, runs the tests, publishes `afterthought-cli` to PyPI through trusted publishing and creates the GitHub release with the built files attached.

The PyPI side needs a one-time pending publisher (owner `mohitagw15856`, repository `afterthought`, workflow `release.yml`, environment `pypi`).

## Re-recording the GIFs

`brew install vhs` then `scripts/record_gifs.sh`. The tapes live in `docs/gifs/tapes/`.
