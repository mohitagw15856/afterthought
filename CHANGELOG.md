# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

### Added

- `verify`: claim verifier. Extracts atomic claims from any model output and tags each SOURCED (with a citation into the vault), INFERRED (reasoning shown) or UNVERIFIED. `--demand` asks the model for evidence per claim; citations are validated against the supplied evidence so none can be invented. Writes a claims page, an annotated copy and JSON.
- `decide`: decision ledger. `new`, `list`, `show`, `confirm`, `reject`, `review` and `check`. Staged decisions from `compile` are confirmed with check-by dates; `review` walks through due assumptions and records whether they held.
- `compile`: chat-to-wiki compiler for ChatGPT, Claude.ai, Claude Code, Slack and markdown exports. Entity, decision, question and timeline pages with source-tagged lines. Incremental and idempotent.
- Provider-agnostic LLM module with structured outputs, fixture replay and dry-run mode.
- Redaction pass for emails, tokens and card numbers; `.afterthoughtignore` support.
- Vault layout, `init`, `status` and `redact` commands.
- Demo ChatGPT export and replayable fixtures under `examples/`.
