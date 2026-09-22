from pathlib import Path

from afterthought.ingest import detect_format, group_conversations, load


def test_chatgpt(example_export: Path) -> None:
    assert detect_format(example_export) == "chatgpt"
    msgs = list(load(example_export))
    convs = group_conversations(msgs)
    assert [len(c.messages) for c in convs] == [5, 4, 4]
    assert convs[0].messages[0].role == "user"
    assert convs[0].started is not None and convs[0].started.isoformat().startswith("2026-03-04")
    assert len({m.span for m in msgs}) == len(msgs)


def test_claude_export(ingest_fixtures: Path) -> None:
    p = ingest_fixtures / "claude-conversations.json"
    assert detect_format(p) == "claude"
    msgs = list(load(p))
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].text.startswith("Call it vault")
    assert msgs[0].conversation_title == "Vault naming"


def test_claude_code(ingest_fixtures: Path) -> None:
    p = ingest_fixtures / "claude-code-session.jsonl"
    assert detect_format(p) == "claude_code"
    msgs = list(load(p))
    assert len(msgs) == 4
    assert msgs[0].conversation_title.startswith("Add a --verbose flag")
    assert "[tool_use Read]" in msgs[1].text
    assert "[tool_result]" in msgs[2].text
    assert msgs[0].conversation_id == "sess-abc"


def test_slack(ingest_fixtures: Path) -> None:
    p = ingest_fixtures / "slack-export"
    assert detect_format(p) == "slack"
    msgs = list(load(p))
    assert len(msgs) == 2  # channel_join dropped
    assert msgs[0].author == "Siyu" and msgs[0].conversation_title == "#general"
    assert msgs[0].ts is not None


def test_markdown(ingest_fixtures: Path) -> None:
    p = ingest_fixtures / "transcript.md"
    assert detect_format(p) == "markdown"
    msgs = list(load(p))
    assert [m.role for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0].author == "Mo" and msgs[1].author is None
    assert msgs[2].text == "Done."
    assert msgs[0].conversation_title == "Naming the CLI"
    plain = list(load(ingest_fixtures / "note.md"))
    assert len(plain) == 1 and plain[0].role == "user"


def test_unknown(tmp_path: Path) -> None:
    f = tmp_path / "x.json"
    f.write_text("{}")
    assert detect_format(f) is None
