from pathlib import Path

from afterthought.ignore import IgnoreRules


def test_patterns(tmp_path: Path) -> None:
    (tmp_path / ".afterthoughtignore").write_text(
        "# comment\n*.env\nprivate/\n**/secrets/**\n!private/keep.md\nnotes.md\n"
    )
    r = IgnoreRules.load(tmp_path)
    assert r.is_ignored("prod.env")
    assert r.is_ignored("private/anything.md")
    assert r.is_ignored("a/b/secrets/c.json")
    assert not r.is_ignored("private/keep.md")
    assert r.is_ignored("deep/notes.md")
    assert not r.is_ignored("public/readme.md")


def test_missing_file(tmp_path: Path) -> None:
    assert not IgnoreRules.load(tmp_path).is_ignored("anything")
