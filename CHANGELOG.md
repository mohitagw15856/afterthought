# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

### Added

- `decide`: decision ledger. `new`, `list`, `show`, `confirm`, `reject`, `review` and `check`. Staged decisions from `compile` are confirmed with check-by dates; `review` walks through due assumptions and records whether they held.
- `compile`: chat-to-wiki compiler for ChatGPT, Claude.ai, Claude Code, Slack and markdown exports. Entity, decision, question and timeline pages with source-tagged lines. Incremental and idempotent.
- Provider-agnostic LLM module with structured outputs, fixture replay and dry-run mode.
- Redaction pass for emails, tokens and card numbers; `.afterthoughtignore` support.
- Vault layout, `init`, `status` and `redact` commands.
- Demo ChatGPT export and replayable fixtures under `examples/`.
