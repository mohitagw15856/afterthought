<p align="center">
  <img src="docs/logo-placeholder.svg" alt="Afterthought" width="96" height="96">
</p>

<h1 align="center">Afterthought</h1>

<p align="center"><strong>What happens after the answer.</strong></p>

<p align="center">
  <a href="https://github.com/mohitagw15856/afterthought/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/mohitagw15856/afterthought/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-blue">
  <img alt="Licence MIT" src="https://img.shields.io/badge/licence-MIT-green">
  <img alt="Obsidian ready" src="https://img.shields.io/badge/obsidian-ready-7c3aed">
  <img alt="No server" src="https://img.shields.io/badge/server-none-lightgrey">
</p>

---

You ask an AI something clever. It answers. You nod, close the tab, and three weeks later you are asking the same question again because the answer, the reasoning and the decision you made because of it have all evaporated.

Every tool out there is racing to make the *first half* of that journey better: prompts, context, retrieval, agents. Almost nothing cares about the *second half*: keeping what you learned, knowing how much of it to trust, remembering what you decided, sharing it with the people you work with, and getting better at the whole thing.

**Afterthought is the second half.** It turns your chats and agent runs into a wiki you can actually rely on. Plain markdown. One folder. Opens in Obsidian. No server, no database, no account.

## Try it in 60 seconds

```bash
git clone https://github.com/mohitagw15856/afterthought && cd afterthought
uv sync

# Compile the bundled demo. No API key needed: recorded model responses are replayed.
uv run afterthought compile examples/chatgpt-export/conversations.json \
    --vault demo-vault --dry-run --fixtures examples/chatgpt-export/fixtures

# Have a look around
uv run afterthought status --vault demo-vault
uv run afterthought decide list --vault demo-vault
cat demo-vault/entities/people/siyu.md
```

Then open `demo-vault/` in Obsidian and click around the graph. Run the compile again and it prints `No changes.` because it already knows every message it has seen.

With a real export and a key:

```bash
export ANTHROPIC_API_KEY=...
uv run afterthought init --vault ~/vault --user "Your Name"
uv run afterthought compile ~/Downloads/chatgpt-export/conversations.json --vault ~/vault
uv run afterthought decide review --vault ~/vault
```

## What it does

| Command | In one sentence | Status |
|---|---|---|
| **compile** | Turns ChatGPT, Claude, Claude Code, Slack and markdown exports into a wiki: a page per project, person, tool and concept, plus decisions, open questions and a timeline. Only new messages are processed. | shipped |
| **decide** | A decision ledger. Choices found in your chats are staged for you to confirm; each assumption gets a confidence and a check-by date, and `review` asks you later whether it held. | shipped |
| **verify** | Splits any model output into atomic claims and tags each SOURCED, INFERRED or UNVERIFIED. It never invents a citation. | next |
| **share** | Publish chosen pages to a shared git repo with full provenance. Two people's pages on the same thing become a diff page, never a silent overwrite. | planned |
| **replay** | A flight recorder for agent runs. Step through a Claude Code session, diff two runs, see which tool result changed the outcome. Static HTML. | planned |
| **coach** | Interviews you about your real work and builds a 30-day curriculum of things to try with AI, tracked in the wiki. | planned |

## See it work

Here is a person page the demo produces. Siyu is fictional. So is everything else in the demo, including the leaked API key that gets redacted before any model sees it.

```markdown
---
id: siyu
title: Siyu
kind: person
sources:
  - file: conversations.json
    message_id: conv-lantern-01-m03
    date: '2026-03-04T09:20:00Z'
    span: 398c94ce04f9
provenance:
  origin: llm
  tool: afterthought.compile
---
# Siyu

## Facts
- A friend of the user from Beijing, China. ^at-llm-398c94ce04f9
- A lawyer who tinkers with home automation at weekends. ^at-llm-398c94ce04f9-2
- Suggested [[grafana|Grafana]] for the [[lantern|Lantern]] dashboard. ^at-llm-398c94ce04f9-3
- Her law firm's IT team uses [[grafana|Grafana]] annotations to mark deploys. ^at-llm-f8e9aa5dd34d
```

Every line the model wrote ends in a block id. The block id resolves, through the frontmatter, to the exact file, message and timestamp it came from. If the model cites a message that does not exist, the line is written as `UNVERIFIED: ...` and kept out of the sources. Nothing is dropped, nothing is guessed.

And a decision, after you have confirmed it and checked an assumption:

```markdown
# Where should Lantern's database and dashboard run: the home Raspberry Pi or a VPS?

Status: confirmed
Decided on: 2026-03-15
Decider: Mo

## Chosen
- Postgres and Grafana on a VPS, collector stays on the Pi with a local retry buffer

## Assumptions
- [x] A small VPS costs under 5 pounds a month (confidence 0.90, check by 2026-06-13, checked 2026-06-14) Note: invoice was 4.20
- [ ] The Pi collector can buffer a day of readings on its SD card (confidence 0.50, check by 2026-06-13)
```

## How trust works

Afterthought has one rule, and everything else falls out of it:

> A line is either traceable to a source, or it says UNVERIFIED.

- Model-written lines carry `^at-llm-<span>` block ids. Obsidian renders them as block references, so you can link to a single fact from anywhere with `[[page#^at-llm-...]]`.
- Human-written lines carry nothing. The system knows the difference.
- Dates come from your sources, never from the clock, so re-running produces byte-identical pages.
- Every model response is cached by input. The same conversation never costs you twice, and the whole test suite runs on recorded fixtures with no key.
- Emails, API tokens and card numbers are redacted before extraction and again before every write. There is a `.afterthoughtignore` for everything else.

The full contract is in [ARCHITECTURE.md](ARCHITECTURE.md).

## Supported inputs

| Source | How to get it |
|---|---|
| ChatGPT | Settings, Data controls, Export. Point at `conversations.json`. |
| Claude.ai | Settings, Privacy, Export data. Point at `conversations.json`. |
| Claude Code | `~/.claude/projects/<project>/<session>.jsonl` |
| Slack | Workspace export folder (needs `channels.json` and `users.json`). |
| Markdown | Any `.md` with `**User:**` / `**Assistant:**` turns, or a whole file as one note. |

Format is sniffed automatically. Use `--format` to insist.

## About

**Why this exists.** I kept noticing that my most useful thinking was happening in chat windows and then disappearing. Note-taking apps wanted me to write things down twice. RAG tools wanted to re-read my chats every time. What I actually wanted was a wiki that wrote itself from the conversations I was already having, told me honestly which bits were made up, and reminded me when a decision I had made was due for a second look. So I built the second half.

**What it is not.** It is not a chat client, a prompt library or a vector database. It does not talk to a model unless you ask it to compile something, and when it does, everything it learned is written to plain files you own.

**The name.** An afterthought is the thing you think of after the conversation is over. Usually that is the important bit.

**Design principles.**

1. Plain files. Markdown and JSON in one folder. Git is the sync layer.
2. Provenance or nothing. No line pretends to be a fact without a source.
3. Idempotent. Run anything twice and nothing changes.
4. Private by default. Redaction runs before the model sees your data.
5. Obsidian first. If it does not render there without plugins, it is a bug.
6. Tests without keys. Fixtures are recorded once and replayed forever.

**Who.** Built by [Mohit](https://github.com/mohitagw15856), with Claude as a pair. Released under the MIT licence; contributions welcome.

## Roadmap

- [x] compile: chat-to-wiki compiler with incremental state and provenance
- [x] decide: decision ledger, staged confirmations, assumption review
- [ ] verify: claim extraction and SOURCED / INFERRED / UNVERIFIED tagging, with `--demand`
- [ ] share: git-based team mesh with diff pages and `subscribe`
- [ ] replay: agent flight recorder with a static HTML viewer
- [ ] coach: onboarding interview and 30-day curriculum

## GIFs to record

Not recorded yet; placeholders so nobody forgets.

1. `docs/gifs/compile.gif`: compiling the demo and opening the vault in Obsidian.
2. `docs/gifs/provenance.gif`: clicking a `^at-llm-` block id through to its source.
3. `docs/gifs/idempotent.gif`: second run prints `No changes.`
4. `docs/gifs/decide-review.gif`: `decide review` walking through due assumptions.
5. `docs/gifs/verify.gif`: the claims table for a model answer.
6. `docs/gifs/replay.gif`: stepping through an agent run in the viewer.

## Development

```bash
uv sync
uv run pytest                 # fixtures only, no network
uv run pytest --live          # also hits Anthropic (needs ANTHROPIC_API_KEY)
uv run ruff check src tests
```

Commands, vault layout and schemas: [ARCHITECTURE.md](ARCHITECTURE.md). Per-module docs: [docs/](docs/). How to help: [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT. See [LICENSE](LICENSE).
