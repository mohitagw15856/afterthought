# replay

```
afterthought replay capture <files...> [--format claude_code|jsonl_hook] [--id NAME]
afterthought replay list
afterthought replay show <run> [--step N] [--full]
afterthought replay diff <run-a> <run-b> [--no-write]
```

A flight recorder for agent runs. Capture a run once, step through it whenever you like, and diff two runs to see which tool result or piece of context sent them in different directions.

## Inputs

- **Claude Code transcripts**: `~/.claude/projects/<project>/<session>.jsonl`. Text, `tool_use` and `tool_result` blocks become separate steps; results are paired with their calls by id.
- **Generic hook format**: one JSON object per line with `ts`, `kind` (`user`, `assistant`, `tool_call`, `tool_result`, `system`), optional `name`, `id`/`ref` for pairing, and `content` (string or any JSON). Emit this from any agent loop and Afterthought can replay it. `type`, `tool` and `tool_use_id` are accepted as aliases.

Content is redacted before it is stored, like everything else in the vault.

## What capture writes

```
runs/<id>/
  run.json       the Run record (steps with kind, tool, timestamps, input and output hashes)
  steps.jsonl    one step per line
  run.md         an Obsidian page: outcome, tools used, a step table
  viewer.html    a single-file viewer: step list, prev/next, keyboard (arrows or j/k), filter by kind
```

The run id is the file name plus a hash of the content, so capturing the same file twice changes nothing. The viewer has no external resources; open it from disk.

## Diffing

`diff` aligns the two runs on `(kind, tool name, input hash)` with a sequence matcher, then compares outputs on aligned steps. It reports:

- **changed tool result**: same call, different output. The most common cause of a different outcome.
- **changed context**: a user or system step that differs.
- **changed assistant**: the model said something different after identical inputs.
- **added / removed** steps.

The earliest tool-result or context change is named as the likely cause when outcomes differ. The diff folder gets `diff.md`, `diff.json` and `diff.html`, a side-by-side viewer with a "next difference" button.
