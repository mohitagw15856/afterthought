# verify

```
afterthought verify <file | vault page | -> [--vault DIR] [--demand] [--dry-run] [--record] [--fixtures DIR] [--json] [--no-write] [--show]
```

Takes any model output and answers one question per sentence: can this be backed up?

## What it does

1. Redacts the text, then asks the model to split it into atomic claims. Each claim carries a verbatim quote so it can be located in the text. Opinions, instructions and questions are dropped.
2. Builds an evidence index from the vault: every model-written line that resolves to a source through its block id, plus lines on pages a person recorded by hand.
3. **Match mode (default).** A claim is `SOURCED` when it closely matches an evidence line: Jaccard overlap of content words at or above `verify.threshold` in the vault config (default 0.5) with at least three shared words. `--threshold` overrides it per run. Everything else is `UNVERIFIED`. No model call is involved in tagging.
4. **Demand mode (`--demand`).** The claims and the top candidate evidence (`verify.candidates` per claim, default 8) go back to the model, which must return one of: `sourced` with the index of the evidence that states the claim, `inferred` with the reasoning chain, or `unverified`. An index that does not exist in the list is ignored and the claim stays `UNVERIFIED`. `inferred` without reasoning is ignored too. The model cannot invent a citation because it never writes one; it can only point at evidence Afterthought supplied.

## Outputs

Written to `claims/<slug>.*` in the vault:

- `<slug>.claims.md`: a page with a table of claims, tags and evidence. `SOURCED` rows link to the block on the vault page and name the file, message id and date behind it.
- `<slug>.annotated.md`: the original text with `[SOURCED: [[page#^block]]]`, `[INFERRED]` or `[UNVERIFIED]` after each located claim.
- `<slug>.claims.json`: the `Claim` records for other tools.

`--json` prints the records instead; `--no-write` leaves the vault alone; `--show` prints the annotated text.

## Tags

| Tag | Meaning |
|---|---|
| `SOURCED` | Matches a fact in this vault that resolves to a file, message and date. Citation given. |
| `INFERRED` | Follows from vault evidence by the reasoning shown. Only produced by `--demand`. |
| `UNVERIFIED` | No evidence found. This is the default and needs no justification. |

Verify only ever cites your own vault. It does not search the web and it does not trust the input's own references.
