# Architecture

Afterthought is a Python 3.12 package with one CLI (`afterthought`) and six modules that share a vault on disk. This document describes the vault layout, page schemas and the provenance model. It is the contract every module must honour.

## Vault layout

```
vault/
  .afterthoughtignore            gitignore-style patterns; inputs and pages that match are never ingested or published
  .afterthought/
    config.json                  user name, provider, model, redaction allow-list
    state/compile.json           processed message spans and extraction batches
    cache/llm/<task>/<key>.json  every model response, replayable in dry-run mode
  index.md                       generated home page listing every page
  entities/
    projects/<slug>.md           one page per project
    people/<slug>.md             one page per person
    tools/<slug>.md              one page per tool or library
    concepts/<slug>.md           one page per concept
  decisions/
    <D-id>.md                    confirmed decisions
    staged/<D-id>.md             candidate decisions extracted from chats, awaiting confirmation
  questions/<slug>.md            open questions
  timeline/<YYYY-MM-DD>.md       one page per day; `undated.md` for sources without timestamps
  sources/index.json             ingested files: format, local path, message count (local only, never published)
  claims/                        verify outputs (module 3)
  runs/                          replay recordings and viewers (module 5)
  coach/                         curriculum and progress (module 6)
  shared/                        read-only subscriptions (module 4)
```

Everything is markdown or JSON. Git is the sync layer. Inputs are never copied into the vault; provenance points back to the original file by name, and `sources/index.json` records where it was on this machine.

## Page schema

Every markdown page has YAML frontmatter that is a serialised `Page` (see `src/afterthought/schemas.py`):

```yaml
---
id: lantern
title: Lantern
kind: project            # project | person | tool | concept | question | timeline | index | decision
aliases: []
tags: [afterthought, project]
sources:
  - file: conversations.json
    message_id: 3c1a...
    date: 2026-03-04T09:12:00Z
    span: 8f2e1c9a0b7d   # hash of (file, message id, text)
    format: chatgpt
    conversation: conv-1
provenance:
  origin: llm            # human | llm | import | system
  tool: afterthought.compile
  model: claude-opus-5
  created: 2026-03-04T09:12:00Z
  derived_from: [claude-opus-5]
updated: 2026-03-05T17:40:00Z
links: [Priya, Grafana]
---
# Lantern
...
```

Dates are UTC and come from the source material, never from the wall clock, so re-running produces byte-identical pages.

Decision pages use the `Decision` schema in their frontmatter instead of `Page` (plus `title` and `kind: decision`).

### Managed and unmanaged sections

`compile` owns three `## ` sections on entity pages: `Facts`, `Related` and `Sources`. They are rebuilt from data on every run. Any other section a human adds (for example `## Notes`) is preserved verbatim, in its original order, after the managed ones. Timeline pages are fully managed, one `## ` section per conversation.

## Provenance model

The rule is simple: **every line a model wrote ends with a block id that resolves to a source, or is marked UNVERIFIED**.

- Model-derived lines end with `^at-llm-<span>` where `<span>` is the span hash of the source message. The page's `sources` list resolves the span to file, message id and date. Obsidian renders `^id` as a block reference, so any line can be linked to from elsewhere as `[[page#^at-llm-<span>]]`.
- When the model cites a message id that does not exist in the conversation, the line is written as `UNVERIFIED: ...` with `^at-unverified-<hash>` and the page keeps no source for it. Nothing is dropped and nothing is guessed.
- Lines a human writes carry no tag. Lines the system generates (index, banners) are on pages whose `provenance.origin` is `system`.
- A comment banner at the top of each generated page explains the tags to a reader who has never seen Afterthought.

Span hashes are computed from `(file name, message id, message text)`, so an edited export re-processes only the messages whose text changed.

## Idempotency

- `Vault.write_text` compares content before writing and skips unchanged files.
- All lists in frontmatter are sorted; all timestamps come from sources.
- `compile` keeps a ledger of processed spans in `.afterthought/state/compile.json` and only sends new messages to the model. The whole conversation is still sent as context, but only the facts it cites are merged, and merges de-duplicate by normalised text.
- Model responses are cached by `(task, key)` where the key is derived from the conversation id and the hashes of the new messages. The same input never produces a second model call.

## LLM access

`afterthought.llm` exposes one function, `get_provider`, and one method on the result, `complete_structured(request, schema)`. Requests carry a `task` name and a caller-chosen `key`. The provider chain is:

1. Fixture directories (`--fixtures`, `config.llm.fixtures`, then the vault cache): if `<dir>/<task>/<key>.json` exists it is returned.
2. Otherwise, unless `--dry-run`, the live provider (Anthropic via the official SDK with structured outputs; or any OpenAI-compatible endpoint). With `--record` the response is written to the first fixture directory.

In dry-run mode a missing fixture is an error, never a guess. The prompt is written beside the expected fixture path as `<key>.request.json` so a human can author one.

## Privacy

- `.afterthoughtignore` is applied to input paths at ingest and to page paths at publish.
- `afterthought.redact` replaces emails, API tokens (Anthropic, OpenAI, GitHub, Slack, AWS, Google, bearer tokens, private keys, `key=value` secrets) and Luhn-valid card numbers with stable markers before extraction and again on every vault write. Markers are stable, so redaction is idempotent.
- `config.redact.allow_emails` whitelists addresses that should stay (for example your own).

## Module map

| Module | Path | Owns |
|---|---|---|
| core | `vault.py`, `pages.py`, `provenance.py`, `redact.py`, `ignore.py`, `schemas.py` | layout, page IO, tagging, privacy |
| llm | `llm/` | provider protocol, fixtures, dry-run, Anthropic, OpenAI-compatible |
| ingest | `ingest/` | one parser per export format, common `Message` model |
| compile | `compile/` | state ledger, extraction prompt and schema, page merge, pipeline |
| decide | `decide/` | planned |
| verify | `verify/` | planned |
| share | `share/` | planned |
| replay | `replay/` | planned |
| coach | `coach/` | planned |
