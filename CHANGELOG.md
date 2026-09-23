# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

### Added

- `coach`: onboarding coach. Eight-question interview, a model-generated N-day curriculum of concrete tasks tagged to the profile, `today`/`done`/`skip`/`status`, and a sync that writes learned skills to `coach/skills.md` and a managed `Learned` section on the person's page, run after every progress change and every compile.
- `replay`: agent flight recorder. Captures Claude Code transcripts and a generic JSONL hook format into `runs/`, with a single-file HTML viewer per run, terminal replay, and `diff` that aligns two runs and names the tool result or context change most likely to have changed the outcome.
- `share`: git-based team mesh. `init`, `publish` (per-publisher namespace, canonical copy, provenance stamp, one commit per change, optional push), conflict diff pages instead of overwrites, `subscribe`/`pull`/`unsubscribe` for read-only mirrors of others' pages, `status`.
- `verify`: claim verifier. Extracts atomic claims from any model output and tags each SOURCED (with a citation into the vault), INFERRED (reasoning shown) or UNVERIFIED. `--demand` asks the model for evidence per claim; citations are validated against the supplied evidence so none can be invented. Writes a claims page, an annotated copy and JSON.
- `decide`: decision ledger. `new`, `list`, `show`, `confirm`, `reject`, `review` and `check`. Staged decisions from `compile` are confirmed with check-by dates; `review` walks through due assumptions and records whether they held.
- `compile`: chat-to-wiki compiler for ChatGPT, Claude.ai, Claude Code, Slack and markdown exports. Entity, decision, question and timeline pages with source-tagged lines. Incremental and idempotent.
- Provider-agnostic LLM module with structured outputs, fixture replay and dry-run mode.
- Redaction pass for emails, tokens and card numbers; `.afterthoughtignore` support.
- Vault layout, `init`, `status` and `redact` commands.
- Demo ChatGPT export and replayable fixtures under `examples/`.
