"""Adblock Rule Collection 单元测试。"""

from __future__ import annotations

from pathlib import Path

from adblock_collection.dns_policy import (
    DNS_LEVELS,
    DNS_REJECT,
    DNS_SAFE,
    classify_dns,
    is_dns_eligible,
    load_dns_policy,
    resolve_policy,
)
from adblock_collection.merge import (
    apply_badfilter,
    dedupe,
    remove_redundant_css,
    remove_redundant_domains,
    source_stats,
    validate_local_rules,
)
from adblock_collection.quality_gate import (
    collect_metrics,
    evaluate,
    load_thresholds,
    save_previous,
)
from adblock_collection.pipeline import (
    PARSER_VERSION,
    parse_source_cached,
)
from adblock_collection.provenance import (
    build_provenance,
    cross_source_duplicate_count,
    detect_exception_conflicts,
    load_security_policy,
    source_group,
)
from adblock_collection.regression import check_allow, check_block, load_false_positives
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


def test_parse_adguard_extended_syntax():
    r = parse_line("example.com#$#body{display:none}")
    assert r is not None
    assert r.kind == "css" and r.is_css and r.domains == ["example.com"]
    assert not r.is_exception

    r = parse_line("example.com#@$#.ad{display:none}")
    assert r is not None
    assert r.kind == "css" and r.is_exception

    r = parse_line("example.com#%#var a = 1")
    assert r is not None
    assert r.kind == "js" and r.domains == ["example.com"]

    r = parse_line("example.com#@%#var a = 1")
    assert r is not None
    assert r.kind == "js" and r.is_exception


def test_parse_adguard_scriptlet():
    r = parse_line("example.com#%#//scriptlet(abort-on-property-read, ads)")
    assert r is not None
    assert r.kind == "scriptlet" and r.is_scriptlet


def test_parse_html_filter_kind():
    r = parse_line("example.com##^script:has-text(adsbygoogle)")
    assert r is not None
    assert r.kind == "html" and r.domains == ["example.com"]


def test_parse_adguard_dollar_html_filter():
    r = parse_line('m.sm.cn$$div[ad_dot_url="adclick"]')
    assert r is not None
    assert r.kind == "html" and r.domains == ["m.sm.cn"]
    assert not r.is_exception


def test_parse_exception_html_filter():
    r = parse_line("example.com#@#^script:has-text(NREUM)")
    assert r is not None
    assert r.kind == "html" and r.is_exception


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


def test_redundant_css_dedupes_extended_syntax():
    rules = [
        _rule("example.com#$#.ad-banner"),
        _rule("example.com#$#.ad-banner"),
        _rule("example.com#$#.ad-top{display:none}"),
        _rule("example.com#$#.ad-top{visibility:hidden}"),
    ]
    kept = remove_redundant_css(rules)
    raws = {r.raw for r in kept}
    assert len(raws) == 3  # 纯类名合 1，两个不同声明各保留
    assert "example.com#$#.ad-top{display:none}" in raws
    assert "example.com#$#.ad-top{visibility:hidden}" in raws


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
    _emit_by_category(rules, tmp_path, "test", "T", gen_dns=False, manifest=[], policy=None)
    assert (tmp_path / "test_other.txt").exists()
    assert (tmp_path / "test_malware.txt").exists()
    assert (tmp_path / "test_css.txt").exists()


def test_path_bearing_rule_excluded_from_dns():
    from adblock_collection import writer
    r = parse_line("||example.com/ads^")
    assert writer._to_hosts_line(r) is None
    assert writer._to_domain(r) is None


def test_exception_cancels_blocked_domain_in_dns():
    from adblock_collection import writer
    rules = [
        parse_line("||block.com^"),
        parse_line("@@||block.com^"),
        parse_line("||keep.com^"),
    ]
    assert sorted(writer._blocked_domains(rules)) == ["keep.com"]


def test_pure_domain_rule_included_in_dns():
    from adblock_collection import writer
    r = parse_line("||example.com^")
    assert writer._to_hosts_line(r) == "0.0.0.0 example.com"
    assert writer._to_domain(r) == "example.com"


# ---------------- DNS 安全分级 ----------------

def test_classify_pure_domain_is_safe():
    v = classify_dns(parse_line("||ads.example.com^"))
    assert v.eligibility == DNS_SAFE
    assert v.confidence == 1.0


def test_classify_path_rule_is_reject():
    v = classify_dns(parse_line("||example.com/ads^$script"))
    assert v.eligibility == DNS_REJECT
    assert v.reason == "path_rule"


def test_classify_css_is_reject():
    v = classify_dns(parse_line("example.com##.ad-banner"))
    assert v.eligibility == DNS_REJECT


def test_classify_modifier_rule_is_conditional():
    v = classify_dns(parse_line("||example.com^$third-party"))
    assert v.eligibility == "CONDITIONAL"
    assert v.reason == "domain_modifier"


def test_policy_all_rejects_modifier():
    r = parse_line("||example.com^$third-party")
    assert is_dns_eligible(r, {"level": "all"}) is False
    assert is_dns_eligible(r, {"level": "safe"}) is True


def test_policy_strict_safe_rejects_modifier():
    r = parse_line("||example.com^$third-party")
    assert is_dns_eligible(r, {"level": "strict-safe"}) is False


def test_load_dns_policy_default_all(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("name: x\nsources:\n  - name: a\n    url: https://a\n", encoding="utf-8")
    policy = load_dns_policy(cfg)
    assert policy["level"] == "all"
    assert policy["allow_modifier"] is False


def test_load_dns_policy_from_config(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\ndns_policy:\n  level: safe\nsources:\n  - name: a\n    url: https://a\n",
        encoding="utf-8",
    )
    policy = load_dns_policy(cfg)
    assert policy["level"] == "safe"
    assert policy["allow_modifier"] is True


def test_resolve_policy_unknown_level_falls_back():
    p = resolve_policy({"level": "nonexistent"})
    assert p["level"] in DNS_LEVELS
    assert p["level"] != "nonexistent"


def test_exception_rule_not_in_dns():
    from adblock_collection import writer
    r = parse_line("@@||example.com^")
    assert writer._to_hosts_line(r) is None
    assert writer._to_domain(r) is None


# ---------------- 误杀回归 ----------------

def test_check_allow_flags_exact_block():
    # 精确匹配：allow 清单中的域名本身被整域阻断才算误杀
    rules = [parse_line("||example.com^")]
    v = check_allow(rules, ["example.com"])
    assert len(v) == 1
    assert v[0]["blocked_by"] == "example.com"


def test_check_allow_ignores_subdomain_block():
    # 子域被封不算误杀（仅祖先命中不报），避免大站子域追踪也被一起放行
    rules = [parse_line("||sub.example.com^")]
    assert check_allow(rules, ["example.com"]) == []
    # 反之 allow 子域、父域被封也不算（放行只作用于精确域名）
    rules2 = [parse_line("||example.com^")]
    assert check_allow(rules2, ["sub.example.com"]) == []


def test_check_allow_passes_when_not_blocked():
    rules = [parse_line("||ads.example.com^")]
    assert check_allow(rules, ["google.com"]) == []


def test_check_allow_ignores_exception():
    rules = [parse_line("||example.com^"), parse_line("@@||example.com^")]
    assert check_allow(rules, ["example.com"]) == []


def test_check_block_detects_missing():
    rules = [parse_line("||ads.example.com^")]
    m = check_block(rules, ["doubleclick.net"])
    assert len(m) == 1


def test_check_block_passes_when_present():
    rules = [parse_line("||doubleclick.net^")]
    assert check_block(rules, ["doubleclick.net"]) == []


def test_load_false_positives_default(tmp_path):
    cfg = tmp_path / "false_positives.yaml"
    cfg.write_text("allow:\n  - google.com\nblock:\n  - doubleclick.net\n", encoding="utf-8")
    fps = load_false_positives(cfg)
    assert fps["allow"] == ["google.com"]
    assert fps["block"] == ["doubleclick.net"]


def test_regression_end_to_end_via_cli(tmp_path):
    from adblock_collection.cli import regression_cmd

    cfg = tmp_path / "sources.yaml"
    cfg.write_text("name: x\ndns_policy:\n  level: all\nsources:\n  - name: a\n    url: https://a\n", encoding="utf-8")
    fp = tmp_path / "false_positives.yaml"
    fp.write_text("allow:\n  - google.com\nblock:\n  - doubleclick.net\n", encoding="utf-8")
    out = tmp_path / "dist"
    out.mkdir()
    # 误杀：整域封禁了 google.com 自身
    (out / "adblock_collection_full.txt").write_text(
        "! Title\n||google.com^\n||doubleclick.net^\n", encoding="utf-8"
    )
    args = type("A", (), {"config": str(cfg), "out": str(out)})()
    # ||google.com^ 命中 allow 清单，应失败返回 1
    assert regression_cmd(args) == 1
    report = (out / "regression_report.json").read_text(encoding="utf-8")
    assert "google.com" in report


# ---------------- 质量门禁 ----------------

def test_collect_metrics_counts_root_blocks():
    rules = [
        parse_line("||example.com^"),
        parse_line("||a.example.com^"),
        parse_line("||com^"),  # 非合法域，domains 为空，不计
    ]
    m = collect_metrics(rules, dns_domains=1, source_counts={"A": 2}, category_counts={"network": 2})
    assert m.total_rules == 3
    assert m.dns_domains == 1
    assert m.root_domain_blocks == 1  # 仅 example.com（单点分隔）
    assert m.source_counts == {"A": 2}


def test_evaluate_passes_without_previous():
    from adblock_collection.quality_gate import Metrics

    m = Metrics(total_rules=100, dns_domains=10, source_counts={"A": 5}, category_counts={})
    gate = evaluate(m, None, _default_thresholds())
    assert gate.passed


def _default_thresholds():
    return {
        "total_rule_growth_percent": 20.0,
        "dns_growth_percent": 15.0,
        "source_drop_percent": 50.0,
        "category_growth_percent": 30.0,
        "max_root_domain_blocks": 0,
    }


def test_evaluate_flags_rule_surge():
    from adblock_collection.quality_gate import Metrics

    prev = Metrics(total_rules=1000, dns_domains=100, source_counts={"A": 500}, category_counts={})
    cur = Metrics(total_rules=1500, dns_domains=100, source_counts={"A": 500}, category_counts={})
    gate = evaluate(cur, prev, _default_thresholds())
    assert not gate.passed
    assert any("总规则数增长" in f for f in gate.failures)


def test_evaluate_flags_source_drop():
    from adblock_collection.quality_gate import Metrics

    prev = Metrics(total_rules=1000, dns_domains=100, source_counts={"A": 500, "B": 500}, category_counts={})
    cur = Metrics(total_rules=1000, dns_domains=100, source_counts={"A": 100, "B": 500}, category_counts={})
    gate = evaluate(cur, prev, _default_thresholds())
    assert not gate.passed
    assert any("骤降" in f for f in gate.failures)


def test_evaluate_flags_dns_surge():
    from adblock_collection.quality_gate import Metrics

    prev = Metrics(total_rules=1000, dns_domains=100, source_counts={"A": 500}, category_counts={})
    cur = Metrics(total_rules=1000, dns_domains=200, source_counts={"A": 500}, category_counts={})
    gate = evaluate(cur, prev, _default_thresholds())
    assert not gate.passed
    assert any("DNS" in f for f in gate.failures)


def test_load_thresholds_from_config(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nquality_gate:\n  total_rule_growth_percent: 5\nsources:\n  - name: a\n    url: https://a\n",
        encoding="utf-8",
    )
    t = load_thresholds(cfg)
    assert t["total_rule_growth_percent"] == 5.0


def test_save_and_load_previous(tmp_path):
    from adblock_collection.quality_gate import Metrics

    m = Metrics(total_rules=10, dns_domains=2, source_counts={"A": 1}, category_counts={})
    save_previous(m, tmp_path)
    loaded = save_previous.__module__ and __import__(
        "adblock_collection.quality_gate", fromlist=["load_previous"]
    ).load_previous(tmp_path)
    assert loaded is not None
    assert loaded.total_rules == 10


def test_quality_gate_via_cli_build(tmp_path):
    from adblock_collection.cli import build

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nquality_gate:\n  total_rule_growth_percent: 10\nsources:\n  - name: a\n    url: https://a\n",
        encoding="utf-8",
    )
    out = tmp_path / "dist"
    out.mkdir()
    # 第一轮构建，无 previous，应通过
    rules_txt = "! t\n" + "\n".join(f"||a{i}.example.com^" for i in range(100)) + "\n"
    (tmp_path / "sample.txt").write_text(rules_txt, encoding="utf-8")
    args1 = type("A", (), {
        "config": str(cfg), "out": str(out), "no_cache": True, "offline": False,
        "no_dns": False, "redundant": False, "split_by_category": False, "dns_policy": None,
    })()
    # 直接调用 _run_quality_gate 逻辑：用 build 内部不便，单独构造
    from adblock_collection.quality_gate import (
        collect_metrics, evaluate, load_previous, load_thresholds, save_previous, write_build_report,
    )
    from adblock_collection.merge import source_stats
    from adblock_collection.rules import parse_line

    rules = [parse_line(x) for x in rules_txt.splitlines() if x and not x.startswith("!")]
    sc = source_stats(rules)
    m1 = collect_metrics(rules, dns_domains=100, source_counts=sc, category_counts={})
    prev = load_previous(out)
    gate1 = evaluate(m1, prev, load_thresholds(cfg))
    write_build_report(out, m1, prev, gate1)
    save_previous(m1, out)
    assert gate1.passed

    # 第二轮：规则数暴增 200%，应失败
    rules_txt2 = "! t\n" + "\n".join(f"||b{i}.example.com^" for i in range(300)) + "\n"
    rules2 = [parse_line(x) for x in rules_txt2.splitlines() if x and not x.startswith("!")]
    sc2 = source_stats(rules2)
    m2 = collect_metrics(rules2, dns_domains=300, source_counts=sc2, category_counts={})
    prev2 = load_previous(out)
    gate2 = evaluate(m2, prev2, load_thresholds(cfg))
    assert not gate2.passed


# ---------------- 阶段缓存 / 算法版本 ----------------

def test_parser_version_constant():
    assert PARSER_VERSION


def test_stage_cache_hit_and_miss(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    url = "https://example.invalid/x.txt"
    lines = ["! c", "||ads.example.com^", "@@||example.com^"]
    r1 = parse_source_cached(lines, "network", "src", url=url, use_stage_cache=True)
    assert len(r1) == 2
    r2 = parse_source_cached(lines, "network", "src", url=url, use_stage_cache=True)
    assert len(r2) == 2
    assert r2[0].raw == "||ads.example.com^"
    r3 = parse_source_cached(lines, "network", "src", url=url, use_stage_cache=False)
    assert len(r3) == 2


def test_stage_cache_invalidated_on_content_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    url = "https://example.invalid/y.txt"
    lines_a = ["||a.example.com^"]
    parse_source_cached(lines_a, "network", "s", url=url, use_stage_cache=True)
    lines_b = ["||b.example.com^", "||c.example.com^"]
    r = parse_source_cached(lines_b, "network", "s", url=url, use_stage_cache=True)
    assert {x.raw for x in r} == {"||b.example.com^", "||c.example.com^"}


def test_collect_uses_stage_cache(tmp_path, monkeypatch):
    from adblock_collection.merge import collect
    from adblock_collection.pipeline import STAGE_DIR

    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n    category: network\n",
        encoding="utf-8",
    )
    import hashlib
    raw = "! c\n||ads.example.com^\n"
    cs = tmp_path / ".cache" / "sources"
    cs.mkdir(parents=True, exist_ok=True)
    cp = cs / hashlib.sha256(b"https://a").hexdigest()[:16]
    cp.write_text(raw, encoding="utf-8")

    res = collect(cfg, use_cache=True, offline=True, use_stage_cache=True)
    assert len(res["all"]) == 1
    assert len(res["all"][0][1]) == 1
    assert STAGE_DIR.exists()


# ---------------- 来源血缘 / 语义去重 ----------------

def test_source_group_classifies():
    assert source_group("AdGuard Base") == "adguard"
    assert source_group("EasyList") == "easylist"
    assert source_group("uBlock Origin") == "ubo"
    assert source_group("URLHaus Filter") == "security"
    assert source_group("Some Random List") == "Some Random List"


def test_build_provenance_aggregates_sources():
    rules = [
        parse_line("||ads.example.com^", source="EasyList"),
        parse_line("||ads.example.com^", source="AdGuard Base"),
        parse_line("||tracker.example.com^", source="EasyList"),
    ]
    prov = build_provenance(rules)
    p = prov[parse_line("||ads.example.com^").norm]
    assert p.source_count == 2
    assert set(p.groups) == {"easylist", "adguard"}
    assert p.independent_group_count == 2
    assert p.confidence > 0.5


def test_cross_source_duplicate_count():
    rules = [
        parse_line("||a.com^", source="EasyList"),
        parse_line("||a.com^", source="AdGuard Base"),
        parse_line("||b.com^", source="EasyList"),
    ]
    prov = build_provenance(rules)
    assert cross_source_duplicate_count(prov) == 1


def test_exception_conflict_detection():
    rules = [
        parse_line("||example.com^"),
        parse_line("@@||example.com^$document"),
    ]
    conflicts = detect_exception_conflicts(rules)
    assert "example.com" in conflicts
    assert len(conflicts["example.com"]) == 2


def test_load_security_policy_default(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsecurity_policy:\n  categories: [malware, phishing]\n  source_drop_percent: 80\n"
        "sources:\n  - name: a\n    url: https://a\n",
        encoding="utf-8",
    )
    sp = load_security_policy(cfg)
    assert sp["categories"] == ["malware", "phishing"]
    assert sp["source_drop_percent"] == 80.0


# ---------------- 安全类独立发行 ----------------

def test_security_independent_release(tmp_path, monkeypatch):
    from adblock_collection.cli import _emit_security, write_manifest

    monkeypatch.chdir(tmp_path)
    rules = [
        parse_line("||malware.example.com^"),
        parse_line("||phishing.example.com^"),
        parse_line("||ads.example.com^"),
    ]
    sp = {"categories": ["malware", "phishing"], "source_drop_percent": 80.0}
    manifest = []
    _emit_security(rules, tmp_path, sp, manifest, gen_dns=True, dns_policy={"level": "all"})

    sec_dir = tmp_path / "security"
    assert (sec_dir / "adblock_collection_security.txt").exists()
    assert (sec_dir / "adblock_collection_security_dns.txt").exists()
    # 普通广告规则不应出现在安全发行中
    content = (sec_dir / "adblock_collection_security.txt").read_text(encoding="utf-8")
    assert "ads.example.com" not in content
    assert "malware.example.com" in content


# ---------------- 本地增强规则校验 ----------------

def test_validate_local_rules_passes_normal(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("sources: []\n", encoding="utf-8")
    lr = tmp_path / "local_rules.txt"
    lr.write_text(
        "# 注释\n"
        "! 标题\n"
        "example.com##.ad-banner\n"
        "live.bilibili.com##[class*=\"recommend\"]\n"
        "||ad.douyin.com^\n",
        encoding="utf-8",
    )
    assert validate_local_rules(cfg) == []


def test_validate_local_rules_blocks_wildcard(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("sources: []\n", encoding="utf-8")
    lr = tmp_path / "local_rules.txt"
    lr.write_text(
        "example.com##*\n"
        "example.com##body\n"
        "##[class*=\"ad\"]\n"
        "*##.banner\n",
        encoding="utf-8",
    )
    v = validate_local_rules(cfg)
    assert len(v) >= 3  # ##* / body / 域通配 应被拦


def test_validate_local_rules_extended_syntax(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("sources: []\n", encoding="utf-8")
    lr = tmp_path / "local_rules.txt"
    lr.write_text(
        "example.com#$#*\n"
        "*.example.com#$#.ad\n"
        "example.com#$#body{display:none}\n"
        "example.com#$#.ad-banner\n"
        "example.com#$#.ad{display:none}\n"
        "example.com#%#var x = 1\n",
        encoding="utf-8",
    )
    v = validate_local_rules(cfg)
    assert len(v) == 3  # #$#* / 域通配 / body 应被拦
    # 合法 #$# 纯类名、带声明、JS 注入应放行（不在违规列表中）
    assert all("ad-banner" not in x and "var x" not in x for x in v)


def test_validate_local_rules_missing_file_ok(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("sources: []\n", encoding="utf-8")
    assert validate_local_rules(cfg) == []
