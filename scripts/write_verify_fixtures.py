"""Hand-authored fixtures for `afterthought verify` on examples/verify/lantern-answer.md.

Keys depend on the input text and on the evidence the demo vault supplies, so
this script compiles the demo vault into a temporary folder and computes them.
The verdicts below were written by a person reading the demo; sourced verdicts
name a substring of the evidence text and the script resolves the index.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from afterthought.compile import compile_inputs
from afterthought.llm import DryRunProvider, FixtureStore
from afterthought.redact import redact
from afterthought.vault import Vault
from afterthought.verify.evidence import build_index, candidates
from afterthought.verify.extract import demand_request, extract_request
from afterthought.verify.pipeline import read_input

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "examples" / "verify" / "lantern-answer.md"
DEMO = ROOT / "examples" / "chatgpt-export"
OUT = DEMO / "fixtures"
MODEL = "hand-authored fixture"

CLAIMS = [
    {
        "text": "Lantern reads an Octopus Home Mini smart meter every 30 seconds.",
        "quote": "Lantern reads an Octopus Home Mini smart meter every 30 seconds.",
        "kind": "factual",
    },
    {
        "text": "Lantern's storage is PostgreSQL with the TimescaleDB extension.",
        "quote": "Storage is PostgreSQL with the TimescaleDB extension",
        "kind": "factual",
    },
    {
        "text": "Raw readings are compressed after seven days.",
        "quote": "raw readings are compressed after seven days",
        "kind": "factual",
    },
    {"text": "Siyu is a lawyer from Beijing.", "quote": "Siyu is a lawyer from Beijing.", "kind": "factual"},
    {
        "text": "Grafana was chosen for the dashboard because Siyu recommended it.",
        "quote": "Grafana was chosen for the dashboard because Siyu recommended it.",
        "kind": "factual",
    },
    {"text": "The VPS costs 4 pounds a month.", "quote": "The VPS costs 4 pounds a month.", "kind": "factual"},
    {
        "text": "InfluxDB was rejected because it cannot store more than a year of data.",
        "quote": "InfluxDB was rejected because it cannot store more than a year of data.",
        "kind": "factual",
    },
    {
        "text": "This is a sensible architecture for a hobby project.",
        "quote": "this is a sensible architecture for a hobby project",
        "kind": "opinion",
    },
]

# verdict per factual claim index; "sourced" carries a substring of the evidence text
VERDICTS = [
    ("sourced", "every 30 seconds", None),
    ("sourced", "Storage will be PostgreSQL", None),
    ("sourced", "compressed after seven days", None),
    (
        "inferred",
        None,
        "Evidence says Siyu is a friend from Beijing, China and separately that she is a lawyer, so together they give the claim.",
    ),
    (
        "inferred",
        None,
        "Evidence says Siyu suggested Grafana and that the dashboard will use Grafana rather than a custom UI, which supports the causal claim.",
    ),
    ("unverified", None, None),
    ("unverified", None, None),
]


def main() -> None:
    text, slug, _ = read_input(INPUT, None)
    text, _ = redact(text)
    ext = extract_request(text, slug)
    p = OUT / ext.task / f"{ext.key}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {"task": ext.task, "key": ext.key, "model": MODEL, "response": {"claims": CLAIMS}},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print("wrote", p.relative_to(ROOT))

    with tempfile.TemporaryDirectory() as tmp:
        vault = Vault(Path(tmp) / "vault")
        compile_inputs(vault, [DEMO / "conversations.json"], provider=DryRunProvider(FixtureStore([OUT])))
        index = build_index(vault)
        factual = [c["text"] for c in CLAIMS if c["kind"] == "factual"]
        flat, seen = [], set()
        for c in factual:
            for e in candidates(c, index):
                if e.link not in seen:
                    seen.add(e.link)
                    flat.append(e)
        verdicts = []
        for i, (verdict, needle, reasoning) in enumerate(VERDICTS):
            ev_index = None
            if needle:
                ev_index = next(j for j, e in enumerate(flat) if needle in e.text)
            verdicts.append({"claim_index": i, "verdict": verdict, "evidence_index": ev_index, "reasoning": reasoning})
        req = demand_request(factual, [f"{e.text} ({e.link})" for e in flat], slug)
        p = OUT / req.task / f"{req.key}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(
                {"task": req.task, "key": req.key, "model": MODEL, "response": {"verdicts": verdicts}},
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
        print("wrote", p.relative_to(ROOT), f"({len(flat)} evidence items)")


if __name__ == "__main__":
    main()
