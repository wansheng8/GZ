"""Adblock Rule Collection 单元测试。"""

from __future__ import annotations

from pathlib import Path

from adblock_collection.merge import (
    apply_badfilter,
    dedupe,
    remove_redundant_domains,
    source_stats,
)
from adblock_collection.rules import Rule, parse_line


def _rule(raw: str, **kw) -> Rule:
    base = parse_line(raw)
    assert base is not None
    for k, v in kw.items():
        setattr(base, k, v)
    return base


def test_parse_network_rule():
    r = parse_line("||ads.example.com^")
    assert r is not None
    assert r.kind == "network"
    assert r.domains == ["ads.example.com"]
    assert not r.is_exception


def test_parse_exception_rule():
    r = parse_line("@@||example.com^$document")
    assert r is not None
    assert r.is_exception
    assert r.options.get("document") == ""


def test_parse_css_rule():
    r = parse_line("example.com##.ad-banner")
    assert r is not None
    assert r.kind == "css"
    assert r.domains == ["example.com"]


def test_parse_scriptlet():
    r = parse_line("example.com##+js(set, ad_config, false)")
    assert r is not None
    assert r.kind == "scriptlet"


def test_normalize_option_order():
    a = parse_line("||x.com^$third-party,script")
    b = parse_line("||x.com^$script,third-party")
    assert a is not None and b is not None
    assert a.norm == b.norm


def test_dedupe():
    rules = [
        _rule("||a.com^"),
        _rule("||a.com^"),
        _rule("||b.com^"),
    ]
    assert len(dedupe(rules)) == 2


def test_badfilter_removes_target():
    target = _rule("||tracker.com^$image")
    bad = _rule("||tracker.com^$image,badfilter", is_badfilter=True)
    kept = apply_badfilter([target, bad, _rule("||keep.com^")])
    assert len(kept) == 1
    assert kept[0].raw == "||keep.com^"


def test_redundant_domain_removal():
    rules = [
        _rule("||example.com^", domains=["example.com"]),
        _rule("||sub.example.com^", domains=["sub.example.com"]),
        _rule("||other.com^", domains=["other.com"]),
    ]
    kept = remove_redundant_domains(rules)
    raws = {r.raw for r in kept}
    assert "||sub.example.com^" not in raws
    assert "||example.com^" in raws
    assert "||other.com^" in raws


def test_path_bearing_domain_extraction():
    r = parse_line("||ads.example.com/banner^$script")
    assert r is not None
    assert r.domains == ["ads.example.com"]


def test_exception_classified_as_whitelist():
    r = parse_line("@@||example.com^$document")
    assert r is not None
    assert r.is_exception
    assert r.category == "whitelist"


def test_important_flag():
    r = parse_line("||ads.com^$important")
    assert r is not None
    assert r.is_important


def test_badfilter_target_with_options():
    target = _rule("||tracker.com^$image", is_badfilter=False)
    bad = _rule("||tracker.com^$image,badfilter", is_badfilter=True)
    other = _rule("||keep.com^", is_badfilter=False)
    kept = apply_badfilter([target, bad, other])
    assert len(kept) == 1
    assert kept[0].raw == "||keep.com^"


def test_source_stats_counts():
    rules = [
        _rule("||a.com^", source="X"),
        _rule("||b.com^", source="X"),
        _rule("||c.com^", source="Y"),
    ]
    stats = source_stats(rules)
    assert stats == {"X": 2, "Y": 1}


def test_domain_extraction_rejects_garbage():
    # 选项 token、URL 编码、异常写法不应被当作域名
    assert parse_line("*$image").domains == []
    assert parse_line("||https%3a%2f%2fwww.amazon.co.jp$document").domains == []
    assert parse_line("||jaya9.app/?af=$document").domains == ["jaya9.app"]
    assert parse_line("||ads.example.com^").domains == ["ads.example.com"]


def test_category_split(tmp_path):
    from adblock_collection.cli import _emit_by_category
    rules = [
        parse_line("||ads.example.com^"),
        parse_line("||malware.example.com^"),
        parse_line("##.ad-banner"),
    ]
    _emit_by_category(rules, tmp_path, "test", "T", gen_dns=False, manifest=[])
    assert (tmp_path / "test_other.txt").exists()
    assert (tmp_path / "test_malware.txt").exists()
    assert (tmp_path / "test_css.txt").exists()
