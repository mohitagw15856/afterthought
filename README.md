# Afterthought

**What happens after the answer.**

Most AI tooling competes on the first half of the journey: prompting, context, retrieval. Almost nothing good exists for the second half: storing, trusting, deciding on, sharing and learning from the work an AI did with you. Conversations are write-only today. You get an answer, close the tab, and a week later you cannot find it, cannot tell how much of it was true, and cannot remember what you decided because of it.

Afterthought makes every AI conversation, agent run and decision compound into a maintained, trustworthy knowledge base that you, and later your team, can query. Everything is plain markdown and JSON in a single `vault/` folder. Obsidian reads it natively. Git is the sync layer. There is no server and no database.

## Six capabilities

| Command | What it does | Status |
|---|---|---|
| `compile` | Turns ChatGPT, Claude, Claude Code, Slack and markdown exports into a wiki: one page per project, person, tool and concept, plus decisions, questions and a timeline. Incremental. Every model-written line carries its source. | v0.1 |
| `decide` | A decision ledger: question, options, chosen option, reasoning, assumptions with confidence and check-by dates. Candidate decisions are auto-staged from chats. `review` asks whether due assumptions held. | planned |
| `verify` | Extracts atomic claims from any model output and tags each SOURCED, INFERRED or UNVERIFIED. Never invents a citation. `--demand` asks the model for evidence per claim. | planned |
| `share` | Publish selected pages to a shared git repo with provenance. Conflicts become diff pages, never silent overwrites. `subscribe` pulls others' pages read-only. | planned |
| `replay` | Agent flight recorder. Replay a Claude Code session step by step, diff two runs, see which tool results changed the outcome. Static HTML, no server. | planned |
| `coach` | Interviews a new user, builds a 30-day curriculum of concrete tasks to try with AI, tracks progress in the wiki. | planned |

## Principles

- **Nothing is presented as fact without a source.** Every model-derived line in the wiki ends with an origin tag that resolves to a file, message id and date in the page frontmatter. If a source cannot be resolved the line is marked UNVERIFIED.
- **Idempotent.** Running any command twice produces no changes.
- **Private by default.** A `.afterthoughtignore` file excludes inputs and pages. Emails, tokens and card numbers are redacted before anything is written or published, and before any model sees them.
- **Tests run without keys.** All model calls go through one provider-agnostic module with a dry-run mode that replays fixtures.

## 60-second quickstart

```bash
git clone https://github.com/mohitagw15856/afterthought && cd afterthought
uv sync                                  # or: pip install -e ".[anthropic]"

# Compile the bundled demo export without touching a model (fixtures are replayed)
uv run afterthought compile examples/chatgpt-export/conversations.json \
    --vault demo-vault --dry-run --fixtures examples/chatgpt-export/fixtures

# Look around
uv run afterthought status --vault demo-vault
cat demo-vault/entities/projects/lantern.md

# Run it again: nothing changes
uv run afterthought compile examples/chatgpt-export/conversations.json \
    --vault demo-vault --dry-run --fixtures examples/chatgpt-export/fixtures
```

Open `demo-vault/` in Obsidian to browse it with backlinks and the graph view.

To compile your own export with a live model:

```bash
export ANTHROPIC_API_KEY=...
uv run afterthought init --vault ~/vault --user "Your Name"
uv run afterthought compile ~/Downloads/chatgpt-export/conversations.json --vault ~/vault
```

Responses are cached in `vault/.afterthought/cache/llm/`, so re-running never repeats a model call.

## Supported inputs (compile)

- ChatGPT data export (`conversations.json`)
- Claude.ai data export (`conversations.json`)
- Claude Code session transcripts (`.jsonl`)
- Slack workspace export (folder with `channels.json`, `users.json`)
- Plain markdown transcripts (`**User:**` / `**Assistant:**` turns, or a whole file as one note)

Format is sniffed automatically; pass `--format` to force one.

## Vault layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full layout, page schemas and the provenance model.

## GIFs to record

Placeholders for the README; none exist yet.

1. `docs/gifs/compile.gif`: running compile on the demo export and opening the result in Obsidian.
2. `docs/gifs/provenance.gif`: hovering a `^at-llm-` block id and jumping to the source in frontmatter.
3. `docs/gifs/idempotent.gif`: running compile twice, second run prints "No changes."
4. `docs/gifs/decide-review.gif`: reviewing due assumptions (module 2).
5. `docs/gifs/verify.gif`: claims table for a model answer (module 3).
6. `docs/gifs/replay.gif`: stepping through an agent run in the HTML viewer (module 5).

## Development

```bash
uv sync
uv run pytest                 # fixtures only, no network
uv run pytest --live          # also runs tests that hit Anthropic (needs ANTHROPIC_API_KEY)
uv run ruff check src tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT. See [LICENSE](LICENSE).
