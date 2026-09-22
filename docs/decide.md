# decide

A decision ledger. Each decision is one markdown page in `decisions/` whose frontmatter is the `Decision` schema: question, options considered, chosen option, reasoning, assumptions (each with a confidence and a check-by date), decider, source conversation and provenance.

```
afterthought decide list [--status staged|confirmed|all] [--json]
afterthought decide show <id>
afterthought decide new [-q ...] [-c ...] [-o ... -o ...] [-r ...] [-a "text | confidence | date" ...] [--on DATE] [--check-in DAYS]
afterthought decide confirm <id> [--check-in DAYS | --check-by DATE] [--decider NAME] [--confidence i=v ...]
afterthought decide reject <id> [--reason ...]
afterthought decide review [--as-of DATE] [--all] [--list]
afterthought decide check <id> <n> --held|--failed|--unknown [--note ...]
```

## Where decisions come from

- `compile` stages every choice it finds in a chat under `decisions/staged/`, with block ids pointing at the message where the choice was made.
- `decide new` records one by hand. It prompts for anything you do not pass as a flag. Pages recorded by hand have `origin: human` and no block ids.

## Confirming

`confirm` moves a staged page to `decisions/` and gives every assumption a check-by date: `--check-by` for a fixed date, or `--check-in` days after the decision date (default 30). The provenance tags survive the move. Confirming twice is a no-op.

`reject` deletes the staged page and records the id in `.afterthought/state/rejected.json`, so a later compile will not stage it again.

## Reviewing

`review` lists open assumptions whose check-by date has passed and asks, one by one, whether they held. Answers are written back to the page: the checkbox becomes `[x]` held, `[!]` failed or `[?]` unknown, with the date and your note. `--list` only prints what is due; `--all` includes assumptions not yet due. `check` records a single answer without the walk-through.

Nothing here reads the wall clock except the default for "today", and every command accepts `--as-of` to pin that.
