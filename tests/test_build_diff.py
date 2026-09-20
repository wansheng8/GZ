"""需求 8.1：相邻两次构建的逐条规则差异。"""

from __future__ import annotations

from adblock_collection.build_diff import (
    diff_fingerprint,
    fingerprint,
    load_previous_fingerprint,
    save_fingerprint,
    write_build_diff,
)
from adblock_collection.rules import parse_line


def _rules(*raws):
    return [parse_line(raw) for raw in raws]


def test_fingerprint_dedupes_and_sorts():
    rules = _rules("||b.com^", "||a.com^", "||a.com^$third-party")
    fps = fingerprint(rules)
    assert fps == sorted(set(fps))
    assert len(fps) == len(rules)


def test_diff_fingerprint_reports_added_and_removed():
    previous = set(fingerprint(_rules("||a.com^", "||b.com^")))
    added, removed = diff_fingerprint(previous, _rules("||b.com^", "||c.com^"))
    assert added == [parse_line("||c.com^").norm]
    assert removed == [parse_line("||a.com^").norm]


def test_save_and_load_previous_fingerprint(tmp_path):
    path = tmp_path / "previous_rules.txt"
    assert load_previous_fingerprint(path) is None
    save_fingerprint(_rules("||a.com^", "||b.com^"), path)
    loaded = load_previous_fingerprint(path)
    assert loaded == set(fingerprint(_rules("||a.com^", "||b.com^")))


def test_write_build_diff_lists_both_sides(tmp_path):
    added = [parse_line("||new.com^").norm]
    removed = [parse_line("||old.com^").norm]
    summary = write_build_diff(tmp_path, added, removed)
    assert summary == {"added": 1, "removed": 1}
    text = (tmp_path / "build_diff.txt").read_text(encoding="utf-8")
    assert f"+ {added[0]}" in text
    assert f"- {removed[0]}" in text
