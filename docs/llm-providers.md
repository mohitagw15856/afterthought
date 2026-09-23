# LLM providers

Set in `vault/.afterthought/config.json`:

```json
{
  "llm": {"provider": "anthropic", "model": "claude-opus-5", "fixtures": null}
}
```

| provider | package | auth |
|---|---|---|
| `anthropic` (default) | `anthropic` SDK, structured outputs via `messages.parse` | `ANTHROPIC_API_KEY` or `ant auth login` |
| `openai-compatible` | `httpx` against `/chat/completions` with `response_format: json_schema` | `OPENAI_API_KEY`, `OPENAI_BASE_URL` or `llm.base_url` |

Every response is cached under `.afterthought/cache/llm/<task>/<key>.json`. Delete a file to force a fresh call.

## Other config keys

```json
{
  "user": "Your Name",
  "redact": {"allow_emails": ["you@example.com"]},
  "verify": {"threshold": 0.5, "candidates": 8},
  "share": {"repo": "/path/to/team", "subscriptions": {"team": "git@host:org/team.git"}}
}
```
