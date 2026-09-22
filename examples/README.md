# Examples

## chatgpt-export

`conversations.json` is a small, entirely fictional ChatGPT data export: three conversations about a made-up home energy dashboard called Lantern. It deliberately contains a fake email address and a fake API key so you can see the redaction pass work.

`fixtures/` holds the recorded model responses for these conversations, so the demo runs without a key:

```bash
uv run afterthought compile examples/chatgpt-export/conversations.json \
    --vault demo-vault --dry-run --fixtures examples/chatgpt-export/fixtures
```

Nothing in this folder refers to a real person, product decision or account.

## verify

`lantern-answer.md` is a short "model answer" about Lantern with a mix of true, inferable and invented claims. Its fixtures live under `chatgpt-export/fixtures/verify.*` and are written by `scripts/write_verify_fixtures.py`:

```bash
uv run afterthought verify examples/verify/lantern-answer.md --vault demo-vault \
    --dry-run --fixtures examples/chatgpt-export/fixtures --demand --show
```

## replay

Two hook-format recordings of an agent fixing the same failing test. Run A succeeds; in run B the first test command fails with a missing module and the run ends without a fix.

```bash
uv run afterthought replay capture examples/replay/*.jsonl --vault demo-vault
uv run afterthought replay diff fix-test-run-a fix-test-run-b --vault demo-vault
```
