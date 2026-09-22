from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "chatgpt-export"
FIXTURES = Path(__file__).parent / "fixtures"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--live", action="store_true", default=False, help="run tests that call Anthropic")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_live = config.getoption("--live") and os.environ.get("ANTHROPIC_API_KEY")
    if run_live:
        return
    reason = "needs --live and ANTHROPIC_API_KEY"
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def example_export() -> Path:
    return EXAMPLES / "conversations.json"


@pytest.fixture
def example_fixtures() -> Path:
    return EXAMPLES / "fixtures"


@pytest.fixture
def ingest_fixtures() -> Path:
    return FIXTURES / "ingest"


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    return tmp_path / "vault"


@pytest.fixture
def trimmed_export(tmp_path: Path, example_export: Path) -> Path:
    """The demo export with the third conversation removed, for incremental tests."""
    import json

    data = json.loads(example_export.read_text(encoding="utf-8"))
    out = tmp_path / "trimmed" / "conversations.json"
    out.parent.mkdir(parents=True)
    out.write_text(json.dumps(data[:2]), encoding="utf-8")
    return out


def tree_digest(root: Path) -> dict[str, str]:
    """Map of relative path to content, for before/after comparisons."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8")
    return out


def copy_export(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy(src, dst_dir / src.name))
