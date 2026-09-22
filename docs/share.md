# share

```
afterthought share init <folder> [--user NAME]
afterthought share publish <pages...> | --all [--repo DIR] [--user NAME] [--push]
afterthought share status [--repo DIR]
afterthought share subscribe <git url or path> [--name NAME]
afterthought share pull [--name NAME]
afterthought share unsubscribe <name>
```

A team knowledge mesh with git as the only transport. No server.

## The shared repo

```
team/
  by/<publisher>/<vault path>.md   each person's own version; only they overwrite it
  canonical/<vault path>.md        the earliest publisher's version; never overwritten by someone else
  conflicts/<vault path>.md        a diff page while publishers disagree
  manifest.json                    who published what, when, with which tool, derived from what
```

`share init` creates it (git init, README, manifest) and records the path in the vault config. Put it on any git host you like and add a remote; `publish --push` pushes after committing.

## Publishing

`publish` takes vault-relative paths, folders or globs, or `--all`. Staged decisions, claims, runs, coach, shared and anything matched by `.afterthoughtignore` are never published. Pages are redacted again on the way out.

A published page keeps its frontmatter and gains a `shared` block:

```yaml
shared:
  publisher: Mo
  tool: afterthought 0.1.0
  published: '2026-09-22T21:04:11Z'
  source_hash: 3d1c8f0a9b2e4d6f
  derived_from:
    origin: llm
    tool: afterthought.compile
    model: claude-opus-5
```

Republishing an unchanged page writes nothing and makes no commit. Each publish that changes something is one commit, authored by the publisher.

## Conflicts

When two people publish different versions of the same path:

- both versions live under `by/`, untouched;
- `canonical/` keeps the earliest publisher's version;
- `conflicts/<path>.md` is written with a unified diff of every other version against the canonical one and links to each version.

The conflict page disappears when the versions match again, which happens when one person publishes the other's content, or when both publish a hand-merged page.

## Subscribing

`subscribe` clones the repo into `.afterthought/subscriptions/<name>/` and mirrors `canonical/`, `conflicts/` and `by/` into `vault/shared/<name>/` as read-only files. `pull` refreshes every subscription and removes pages that vanished upstream. Mirrored pages are not compiled and are not used as evidence by `verify`; they are there to read and link to.
