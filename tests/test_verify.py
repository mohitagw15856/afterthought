import json
from pathlib import Path

from conftest import ROOT, tree_digest
from typer.testing import CliRunner

from afterthought.cli import app
from afterthought.compile import compile_inputs
from afterthought.llm import DryRunProvider, FixtureStore, StructuredRequest
from afterthought.pages import block_ids, read_page, split_frontmatter
from afterthought.vault import Vault
from afterthought.verify import verify_text
from afterthought.verify.evidence import build_index, plain_text, score
from afterthought.verify.extract import ClaimExtraction, DemandResult
from afterthought.verify.pipeline import locate, read_input

runner = CliRunner()
ANSWER = ROOT / "examples" / "verify" / "lantern-answer.md"


def _vault(vault_dir: Path, example_export: Path, example_fixtures: Path) -> Vault:
    v = Vault(vault_dir)
    compile_inputs(v, [example_export], provider=DryRunProvider(FixtureStore([example_fixtures])))
    return v


def test_evidence_index_resolves_to_page_blocks(vault_dir, example_export, example_fixtures) -> None:
    v = _vault(vault_dir, example_export, example_fixtures)
    index = build_index(v)
    assert len(index) > 40
    for e in index:
        fm, body = split_frontmatter((v.root / f"{e.page}.md").read_text())
        assert e.block in block_ids(body), e.link
        spans = {s["span"] for s in fm.get("sources", [])} | ({fm["source"]["span"]} if fm.get("source") else set())
        assert e.source is not None and e.source.span in spans
        assert "^at-" not in e.text and "[[" not in e.text
    assert not any(e.text.startswith("UNVERIFIED") for e in index)


def test_matching_is_conservative() -> None:
    assert (
        score("Raw readings are compressed after seven days.", "Raw readings will be compressed after seven days.")
        >= 0.5
    )
    assert score("Siyu is a lawyer from Beijing.", "A friend of the user from Beijing, China.") < 0.5
    assert score("The VPS costs 4 pounds a month.", "Assumed to cost under 5 pounds a month.") < 0.5
    assert plain_text("- [x] Uses [[grafana|Grafana]] annotations ^at-llm-abc-2") == "Uses Grafana annotations"


def test_locate_variants() -> None:
    text = "Alpha beta.  Gamma\ndelta epsilon."
    assert locate(text, "Alpha beta.") == (0, 11)
    assert locate(text, "gamma delta") == (13, 24)
    assert locate(text, "not there") == (0, 0)


def test_match_mode(vault_dir, example_export, example_fixtures) -> None:
    v = _vault(vault_dir, example_export, example_fixtures)
    text, slug, name = read_input(ANSWER, None)
    report = verify_text(
        v, text, slug=slug, source_name=name, provider=DryRunProvider(FixtureStore([example_fixtures]))
    )
    assert report.llm_calls == 1 and len(report.claims) == 7  # the opinion is dropped
    assert report.counts() == {"SOURCED": 3, "INFERRED": 0, "UNVERIFIED": 4}
    sourced = [c for c in report.claims if c.tag == "SOURCED"]
    for c in sourced:
        assert c.evidence and c.evidence.startswith("[[entities/") and "#^at-llm-" in c.evidence
        assert c.citation is not None and c.citation.message_id
    page = v.root / "claims" / "lantern-answer.claims.md"
    assert page.exists() and read_page(page).kind == "claims"
    annotated = (v.root / "claims" / "lantern-answer.annotated.md").read_text()
    assert annotated.count("[UNVERIFIED]") == 4 and "[SOURCED: [[" in annotated
    assert "sensible architecture for a hobby project." in annotated and "hobby project. [" not in annotated
    data = json.loads((v.root / "claims" / "lantern-answer.claims.json").read_text())
    assert all(d["tag"] in {"SOURCED", "INFERRED", "UNVERIFIED"} for d in data)
    before = tree_digest(vault_dir)
    again = verify_text(v, text, slug=slug, source_name=name, provider=DryRunProvider(FixtureStore([example_fixtures])))
    assert not again.written and tree_digest(vault_dir) == before


def test_demand_mode(vault_dir, example_export, example_fixtures) -> None:
    v = _vault(vault_dir, example_export, example_fixtures)
    text, slug, name = read_input(ANSWER, None)
    report = verify_text(
        v, text, slug=slug, source_name=name, provider=DryRunProvider(FixtureStore([example_fixtures])), demand=True
    )
    assert report.llm_calls == 2
    assert report.counts() == {"SOURCED": 3, "INFERRED": 2, "UNVERIFIED": 2}
    inferred = [c for c in report.claims if c.tag == "INFERRED"]
    assert all(c.reasoning and c.demanded for c in inferred)
    assert [c.text for c in report.claims if c.tag == "UNVERIFIED"] == [
        "The VPS costs 4 pounds a month.",
        "InfluxDB was rejected because it cannot store more than a year of data.",
    ]


class Liar:
    """A provider that cites evidence that does not exist and infers without reasoning."""

    name = "liar"
    model = "liar-1"

    def complete_structured(self, req: StructuredRequest, schema):
        if schema is ClaimExtraction:
            return ClaimExtraction.model_validate(
                {
                    "claims": [
                        {
                            "text": "The moon is made of cheese.",
                            "quote": "The moon is made of cheese.",
                            "kind": "factual",
                        },
                        {
                            "text": "Lantern runs on a Raspberry Pi 4.",
                            "quote": "Lantern runs on a Raspberry Pi 4.",
                            "kind": "factual",
                        },
                    ]
                }
            )
        return DemandResult.model_validate(
            {
                "verdicts": [
                    {"claim_index": 0, "verdict": "sourced", "evidence_index": 999},
                    {"claim_index": 1, "verdict": "inferred", "reasoning": ""},
                ]
            }
        )


def test_invented_citations_never_count(vault_dir, example_export, example_fixtures) -> None:
    v = _vault(vault_dir, example_export, example_fixtures)
    text = "The moon is made of cheese. Lantern runs on a Raspberry Pi 4."
    report = verify_text(v, text, slug="liar", source_name="liar", provider=Liar(), demand=True, write=False)
    assert report.claims[0].tag == "UNVERIFIED" and report.claims[0].evidence is None
    assert (
        report.claims[1].tag == "SOURCED"
    )  # matched deterministically before the demand; the empty reasoning is ignored


def test_empty_vault_defaults_to_unverified(tmp_path, example_fixtures) -> None:
    v = Vault(tmp_path / "empty")
    v.init()
    text, slug, name = read_input(ANSWER, None)
    report = verify_text(
        v, text, slug=slug, source_name=name, provider=DryRunProvider(FixtureStore([example_fixtures]))
    )
    assert report.evidence_items == 0 and report.counts()["UNVERIFIED"] == 7


def test_cli_file_stdin_and_vault_page(vault_dir, example_export, example_fixtures) -> None:
    _vault(vault_dir, example_export, example_fixtures)
    common = ["--vault", str(vault_dir), "--dry-run", "--fixtures", str(example_fixtures)]
    r = runner.invoke(app, ["verify", str(ANSWER), *common])
    assert r.exit_code == 0, r.output
    assert "SOURCED 3  INFERRED 0  UNVERIFIED 4" in r.output and "Written:" in r.output
    r = runner.invoke(app, ["verify", str(ANSWER), *common, "--json", "--no-write"])
    assert r.exit_code == 0 and len(json.loads(r.output)) == 7
    r = runner.invoke(app, ["verify", str(ANSWER), *common])
    assert "No changes." in r.output
    r = runner.invoke(app, ["verify", str(ANSWER), *common, "--demand", "--show"])
    assert r.exit_code == 0 and "[INFERRED]" in r.output and "Written:" in r.output
    r = runner.invoke(app, ["verify", "-", *common], input="Nothing in the vault says this.\n")
    assert r.exit_code == 2 and "No fixture" in r.output  # dry-run never guesses
    r = runner.invoke(app, ["verify", "does-not-exist.md", *common])
    assert r.exit_code == 1


def test_threshold_is_configurable(vault_dir, example_export, example_fixtures) -> None:
    v = _vault(vault_dir, example_export, example_fixtures)
    text, slug, name = read_input(ANSWER, None)
    strict = verify_text(
        v,
        text,
        slug=slug,
        source_name=name,
        provider=DryRunProvider(FixtureStore([example_fixtures])),
        write=False,
        threshold=0.95,
    )
    assert strict.counts()["SOURCED"] < 3  # only word-for-word matches survive
    cfg = v.config()
    cfg["verify"]["threshold"] = 0.2
    v.save_config(cfg)
    loose = verify_text(
        v, text, slug=slug, source_name=name, provider=DryRunProvider(FixtureStore([example_fixtures])), write=False
    )
    assert loose.counts()["SOURCED"] >= 3
    common = ["--vault", str(vault_dir), "--dry-run", "--fixtures", str(example_fixtures), "--no-write"]
    r = runner.invoke(app, ["verify", str(ANSWER), *common, "--threshold", "0.95"])
    assert r.exit_code == 0 and "SOURCED 3" not in r.output
