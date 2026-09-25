"""需求 8.1：相邻两次构建的逐条规则差异。"""

from __future__ import annotations

from adblock_collection.build_diff import (
    diff_fingerprint,
    fingerprint,
    load_previous_fingerprint,
    registrable_domain,
    review_new_domains,
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


def test_registrable_domain():
    assert registrable_domain("example.com") == "example.com"
    assert registrable_domain("sub.example.com") == "example.com"
    assert registrable_domain("a.b.co.uk") == "b.co.uk"
    assert registrable_domain("a.b.example.co.uk") == "example.co.uk"
    assert registrable_domain("localhost") == "localhost"


def test_review_new_domains_risk_and_allow(tmp_path):
    import json

    added = [
        parse_line("||example.com^").norm,  # high：可注册域本体
        parse_line("||sub.example.org^").norm,  # low：子域
        parse_line("||safe.example^").norm,  # critical：命中 allow
        parse_line("||track.example^$third-party").norm,  # 非整域阻断，忽略
        parse_line("||notify.example^$important").norm,  # 整域阻断（含 $important）
    ]
    summary = review_new_domains(tmp_path, added, allow_domains=["safe.example"])

    assert summary["total_new_domains"] == 4  # track.example 被排除
    assert summary["by_risk"] == {"critical": 1, "high": 2, "low": 1}
    assert summary["critical"] == ["safe.example"]
    risks = {e["domain"]: e["risk"] for e in summary["entries"]}
    assert risks == {
        "safe.example": "critical",
        "example.com": "high",
        "notify.example": "high",
        "sub.example.org": "low",
    }
    # 落盘 JSON 与返回一致
    saved = json.loads((tmp_path / "new_domain_review.json").read_text(encoding="utf-8"))
    assert saved["total_new_domains"] == 4
    # entries 按风险降序、同风险按域名升序
    order = [e["domain"] for e in summary["entries"]]
    assert order == ["safe.example", "example.com", "notify.example", "sub.example.org"]


def test_review_new_domains_truncates(tmp_path, monkeypatch):
    import adblock_collection.build_diff as bd

    monkeypatch.setattr(bd, "MAX_REVIEW_ENTRIES", 2)
    added = [parse_line(f"||d{i}.example^").norm for i in range(5)]
    summary = review_new_domains(tmp_path, added)
    assert summary["total_new_domains"] == 5
    assert summary["truncated"] is True
    assert len(summary["entries"]) == 2
