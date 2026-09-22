# compile

```
afterthought compile <inputs...> [--vault DIR] [--dry-run] [--record] [--fixtures DIR] [--format NAME] [--verbose]
```

Ingests exported chat histories and upserts wiki pages.

## What it produces

- `entities/<kind>/<slug>.md` with a `## Facts` list where every bullet ends in `^at-llm-<span>`.
- `decisions/staged/D-<id>.md` for every choice the model found; confirm them with `afterthought decide review` (module 2).
- `questions/<slug>.md` for open questions.
- `timeline/<date>.md` with one section per conversation.
- `index.md` linking everything.

## Incremental runs

The ledger in `.afterthought/state/compile.json` records every processed message span. A second run over the same export prints `No changes.` A new export that adds messages to a conversation sends the whole conversation for context but only merges facts that cite messages, and de-duplicates facts by text.

## Dry run and fixtures

`--dry-run` never calls a model. It replays `<task>/<key>.json` from `--fixtures` directories, the `llm.fixtures` path in config, and the vault cache. A missing fixture is an error and the prompt is written beside the expected path as `<key>.request.json`.

`--record` writes live responses to the first `--fixtures` directory.
