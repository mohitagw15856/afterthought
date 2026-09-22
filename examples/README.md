# Examples

## chatgpt-export

`conversations.json` is a small, entirely fictional ChatGPT data export: three conversations about a made-up home energy dashboard called Lantern. It deliberately contains a fake email address and a fake API key so you can see the redaction pass work.

`fixtures/` holds the recorded model responses for these conversations, so the demo runs without a key:

```bash
uv run afterthought compile examples/chatgpt-export/conversations.json \
    --vault demo-vault --dry-run --fixtures examples/chatgpt-export/fixtures
```

Nothing in this folder refers to a real person, product decision or account.
