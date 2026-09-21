"""Adblock Rule Collection 单元测试。"""

from __future__ import annotations

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
from adblock_collection.quality_gate import (
    collect_metrics,
    evaluate,
    load_thresholds,
    save_previous,
)
from adblock_collection.regression import check_allow, check_block, load_false_positives
from adblock_collection.rules import Rule, parse_line, parse_lines, parse_options


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


def test_parse_adguard_scriptlet_exception():
    r = parse_line("example.com#@%#//scriptlet(abort-on-property-read, ads)")
    assert r is not None
    assert r.kind == "scriptlet" and r.is_scriptlet and r.is_exception


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


def test_parse_options_keeps_comma_in_regex_value():
    opts = parse_options("frame,3p,removeparam=/^__mk_[a-z]{1,3}_[a-z]{1,3}=/,script")
    assert set(opts) == {"frame", "3p", "removeparam", "script"}
    assert opts["removeparam"] == "/^__mk_[a-z]{1,3}_[a-z]{1,3}=/"


def test_parse_options_keeps_comma_in_quoted_value():
    opts = parse_options("frame,replace='/a,b/c/'")
    assert set(opts) == {"frame", "replace"}
    assert opts["replace"] == "'/a,b/c/'"


def test_parse_options_honours_escaped_comma():
    opts = parse_options(r"header=vary:/^referer\,accept-encoding/i")
    assert opts["header"] == r"vary:/^referer\,accept-encoding/i"


def test_parse_options_keeps_comma_in_named_header_regex():
    opts = parse_options(r"script,3p,header=via:/, 1\.1 google$/,domain=x")
    assert set(opts) == {"script", "3p", "header", "domain"}
    assert opts["header"] == r"via:/, 1\.1 google$/"


def test_parse_options_csp_url_not_treated_as_regex():
    opts = parse_options("csp=default-src 'self' https://cdn.example.com,domain=x")
    assert set(opts) == {"csp", "domain"}
    assert opts["csp"] == "default-src 'self' https://cdn.example.com"


def test_options_locates_dollar_inside_value():
    r = parse_line("$uritransform=/#E=[\\d]{10}$//,to=a.com|b.com")
    assert r is not None
    assert set(r.options) == {"uritransform", "to"}
    assert r.options["uritransform"] == "/#E=[\\d]{10}$//"


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


def test_redundant_domain_prefers_full_block_over_narrow():
    rules = [_rule("||a.com^$image"), _rule("||a.com^")]
    kept = remove_redundant_domains(rules)
    assert [r.raw for r in kept] == ["||a.com^"]


def test_redundant_domain_prefers_important():
    rules = [_rule("||a.com^"), _rule("||a.com^$important")]
    kept = remove_redundant_domains(rules)
    assert [r.raw for r in kept] == ["||a.com^$important"]


def test_redundant_domain_narrow_parent_does_not_cover_child():
    rules = [_rule("||a.com^$third-party"), _rule("||sub.a.com^")]
    kept = remove_redundant_domains(rules)
    assert {r.raw for r in kept} == {"||a.com^$third-party", "||sub.a.com^"}


def test_path_rule_does_not_override_pure_domain_block():
    rules = [_rule("||doubleclick.net/tag/js/gpt.js"), _rule("||doubleclick.net^")]
    kept = remove_redundant_domains(rules)
    assert {r.raw for r in kept} == {"||doubleclick.net^"}


def test_path_rule_does_not_cover_subdomain():
    rules = [_rule("||a.com/path^"), _rule("||sub.a.com^")]
    kept = remove_redundant_domains(rules)
    assert {r.raw for r in kept} == {"||a.com/path^", "||sub.a.com^"}


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


def test_badfilter_pure_token_cancels_target():
    # 只有 badfilter 一个选项时，去掉后需连同 $ 一同丢弃才能匹配无选项规则
    target = _rule("||ads.com^", is_badfilter=False)
    bad = _rule("||ads.com^$badfilter", is_badfilter=True)
    kept = apply_badfilter([target, bad, _rule("||keep.com^")])
    assert [r.raw for r in kept] == ["||keep.com^"]


def test_badfilter_ignores_comma_inside_value():
    target = _rule("||ads.com^$removeparam=/x{1,3}/", is_badfilter=False)
    bad = _rule("||ads.com^$removeparam=/x{1,3}/,badfilter", is_badfilter=True)
    assert apply_badfilter([target, bad]) == []


def test_legacy_badfilter_cancels_target():
    # 遗留写法 `||domain^,badfilter` 应与 `$badfilter` 同义
    bad = _rule("||ads.com^,badfilter")
    assert bad.is_badfilter
    kept = apply_badfilter([_rule("||ads.com^"), bad, _rule("||keep.com^")])
    assert [r.raw for r in kept] == ["||keep.com^"]


def test_legacy_badfilter_without_target_is_dropped():
    # 悬空的 badfilter 自身绝不应作为普通阻断规则保留
    assert apply_badfilter([_rule("||lone.com^,badfilter")]) == []


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
    _emit_by_category(
        rules, tmp_path, "test", "T", gen_dns=False, manifest=[], policy=None
    )
    assert (tmp_path / "test_other.txt").exists()
    assert (tmp_path / "test_malware.txt").exists()
    assert (tmp_path / "test_css.txt").exists()


def test_path_bearing_rule_excluded_from_dns():
    from adblock_collection import writer

    assert writer._blocked_domains([parse_line("||example.com/ads^")]) == set()


def test_upstream_exception_does_not_cancel_dns_block():
    from adblock_collection import writer

    rules = [
        parse_line("||block.com^"),
        parse_line("@@||block.com^"),
        parse_line("||keep.com^"),
    ]
    # 上游例外不参与 DNS 剔除（P3）：两个整域阻断都保留
    assert sorted(writer._blocked_domains(rules)) == ["block.com", "keep.com"]


def test_custom_allowlist_exception_cancels_dns_block():
    from adblock_collection import writer

    rules = [
        parse_line("||block.com^"),
        parse_line("@@||block.com^", source="LocalAllowlist"),
        parse_line("||keep.com^"),
    ]
    assert sorted(writer._blocked_domains(rules)) == ["keep.com"]


def test_custom_blocklist_enters_dns_block():
    from adblock_collection import writer

    rules = [parse_line("||local.example^", source="LocalBlocklist")]
    assert writer._blocked_domains(rules) == {"local.example"}


def test_custom_allowlist_overrides_custom_blocklist_in_dns():
    from adblock_collection import writer

    rules = [
        parse_line("||a.com^", source="LocalBlocklist"),
        parse_line("@@||a.com^", source="LocalAllowlist"),
    ]
    assert writer._blocked_domains(rules) == set()


def test_pure_domain_rule_included_in_dns():
    from adblock_collection import writer

    assert writer._blocked_domains([parse_line("||example.com^")]) == {"example.com"}


def test_reserved_hostname_excluded_from_dns():
    from adblock_collection import writer

    rules = [parse_line("||localhost.localdomain^"), parse_line("||example.com^")]
    assert writer._blocked_domains(rules) == {"example.com"}


def test_ubo_enhanced_rule_selection():
    from adblock_collection.rules import is_ubo_enhanced

    assert is_ubo_enhanced(parse_line("||a.com^$removeparam=utm_source"))
    assert is_ubo_enhanced(parse_line("||a.com^$csp=script-src 'self'"))
    assert is_ubo_enhanced(parse_line("||a.com^$redirect=noopjs"))
    assert not is_ubo_enhanced(parse_line("||a.com^$third-party"))
    assert not is_ubo_enhanced(parse_line("||a.com^"))


def test_ubo_enhanced_includes_ubo_only_cosmetic():
    from adblock_collection.rules import is_ubo_enhanced

    # uBO/AdGuard 专有元素/脚本语法归入增强清单
    assert is_ubo_enhanced(parse_line("example.com##+js(noop)"))
    assert is_ubo_enhanced(parse_line("example.com#?#.promo:has-text(Ad)"))
    assert is_ubo_enhanced(parse_line("example.com##.ad:remove()"))
    assert is_ubo_enhanced(parse_line("example.com##.ad:remove-attr(hidden)"))
    assert is_ubo_enhanced(parse_line("example.com##^script:has-text(ad)"))
    assert is_ubo_enhanced(parse_line("example.com#$#.ad{display:none}"))
    assert is_ubo_enhanced(parse_line("example.com#%#window.x=1"))
    # ABP/uBO/AdGuard 通用语法留在基础清单
    assert not is_ubo_enhanced(parse_line("example.com##.ad-banner"))
    assert not is_ubo_enhanced(parse_line("example.com###ad"))
    assert not is_ubo_enhanced(parse_line("example.com#@#.ad-banner"))


def test_write_dns_allow_lists_custom_allowlist_exceptions(tmp_path):
    from adblock_collection import writer

    rules = [
        parse_line("@@||allowed.example^", source="LocalAllowlist"),
        parse_line("@@||upstream.example^"),
        parse_line("@@||scoped.example^$domain=x.com", source="LocalAllowlist"),
        parse_line("@@||typed.example^$script", source="LocalAllowlist"),
        parse_line("@@||party.example^$third-party", source="LocalAllowlist"),
        parse_line("||blocked.example^"),
    ]
    path = tmp_path / "dns_allow.txt"
    count = writer.write_dns_allow(rules, path, "T")
    text = path.read_text(encoding="utf-8")
    assert count == 1
    assert "allowed.example" in text
    # 上游例外不再派生 DNS 白名单
    assert "upstream.example" not in text
    assert "scoped.example" not in text
    # 资源类型/第三方限定的例外是局部放行，不得升级为整域 DNS 白名单
    assert "typed.example" not in text
    assert "party.example" not in text


def test_adblock_split_builds_include_master(tmp_path):
    from adblock_collection import writer

    rules = [parse_line(f"||h{i}.example.com^") for i in range(50)]
    result = writer.write_adblock_split(rules, tmp_path, "big", "T", "D", max_bytes=400)
    assert result is not None
    master, parts, total = result
    assert master == "big_jsdelivr.txt"
    assert total == len(rules)
    assert len(parts) > 1
    merged = []
    for name in parts:
        part = tmp_path / name
        assert part.stat().st_size <= 400
        for line in part.read_text(encoding="utf-8").splitlines():
            if not line.startswith("!"):
                merged.append(line)
    assert merged == [r.raw for r in rules]
    content = (tmp_path / master).read_text(encoding="utf-8")
    for name in parts:
        assert f"!#include {name}" in content


def test_emit_generates_jsdelivr_split_when_oversized(tmp_path, monkeypatch):
    from adblock_collection import cli

    monkeypatch.setattr(cli, "JSDELIVR_MAX_BYTES", 200)
    rules = [parse_line(f"||h{i}.example.com^") for i in range(30)]
    manifest = []
    cli._emit(
        rules,
        tmp_path,
        "adblock_collection_full",
        "T",
        "D",
        gen_dns=False,
        source_counts=None,
        manifest=manifest,
        policy=None,
    )
    files = {m["file"] for m in manifest}
    assert "adblock_collection_full.txt" in files
    assert "adblock_collection_full_jsdelivr.txt" in files
    assert (tmp_path / "adblock_collection_full_jsdelivr.txt").exists()


def test_dns_outputs_contain_only_pure_blocked_domains(tmp_path):
    from adblock_collection import writer

    rules = [
        parse_line("||ads.example.com^"),
        parse_line("@@||allow.example.com^"),
        parse_line("@@||ads.taboola.com^"),
        parse_line("@@||doubleclick.net^$xhr,domain=yyets.click"),
        parse_line("||ads.example.com/track^"),
        parse_line("example.com##.ad"),
    ]
    path = tmp_path / "x_dns.txt"
    writer.write_hosts(rules, path, "T", {"level": "all"})
    content = path.read_text(encoding="utf-8")
    domains = {
        line.split(" ", 1)[1]
        for line in content.splitlines()
        if line.startswith("0.0.0.0 ")
    }
    assert "ads.example.com" in domains
    # 例外与路径规则绝不能以任何形式进入 DNS 输出，否则会被 DNS 端当作放行
    assert "@@" not in content
    assert "/" not in content


# ---------------- 三层产物（网络 / 元素隐藏 / DNS 等价） ----------------


def test_emit_layers_splits_rules_by_kind(tmp_path):
    from adblock_collection import cli

    rules = [
        parse_line("||ads.example.com^"),
        parse_line("||track.example.com^$third-party"),
        parse_line("example.com##.ad-banner"),
        parse_line("example.com##+js(set-constant, adblockDetected, false)"),
        parse_line("example.com#?#div:has(.advert)"),
    ]
    manifest: list = []
    cli._emit_layers(
        rules,
        tmp_path,
        "adblock_collection_full",
        manifest,
        gen_dns=True,
        policy={"level": "all"},
    )
    files = {m["file"] for m in manifest}
    assert {
        "adblock_collection_full_browser_network.txt",
        "adblock_collection_full_cosmetic.txt",
        "adblock_collection_full_dns_abp.txt",
    } <= files

    network = (tmp_path / "adblock_collection_full_browser_network.txt").read_text(
        encoding="utf-8"
    )
    assert "||ads.example.com^" in network
    assert "||track.example.com^$third-party" in network
    assert "##" not in network

    cosmetic = (tmp_path / "adblock_collection_full_cosmetic.txt").read_text(
        encoding="utf-8"
    )
    assert "example.com##.ad-banner" in cosmetic
    assert "##+js(" in cosmetic
    assert "#?#div:has(.advert)" in cosmetic
    assert "||ads.example.com^" not in cosmetic


def test_dns_abp_contains_only_pure_domain_rules(tmp_path):
    from adblock_collection import cli

    rules = [
        parse_line("||ads.example.com^"),
        parse_line("||track.example.com^$third-party"),
        parse_line("@@||allow.example.com^"),
        parse_line("@@||doubleclick.net^$xhr,domain=yyets.click"),
        parse_line("||ads.example.com/track^"),
        parse_line("example.com##.ad"),
    ]
    manifest: list = []
    cli._emit_layers(
        rules,
        tmp_path,
        "adblock_collection_full",
        manifest,
        gen_dns=True,
        policy={"level": "all"},
    )
    content = (tmp_path / "adblock_collection_full_dns_abp.txt").read_text(
        encoding="utf-8"
    )
    body = [
        line
        for line in content.splitlines()
        if line and not line.startswith("!") and not line.startswith("[")
    ]
    assert body
    for line in body:
        assert line.startswith("||") and line.endswith("^")
        assert "$" not in line
        assert "##" not in line
        assert "@@" not in line
    assert "||ads.example.com^" in body
    # 路径规则不得被扩成整域，例外不得出现在 DNS 等价清单里
    assert "||allow.example.com^" not in body


def test_emit_layers_skips_dns_abp_without_dns(tmp_path):
    from adblock_collection import cli

    manifest: list = []
    cli._emit_layers(
        [parse_line("||ads.example.com^")],
        tmp_path,
        "adblock_collection_full",
        manifest,
        gen_dns=False,
        policy={"level": "all"},
    )
    files = {m["file"] for m in manifest}
    assert "adblock_collection_full_dns_abp.txt" not in files
    assert "adblock_collection_full_browser_network.txt" in files


def test_emit_layers_union_equals_full(tmp_path):
    from adblock_collection import cli

    rules = [
        parse_line("||ads.example.com^"),
        parse_line("||track.example.com^$third-party"),
        parse_line("example.com##.ad-banner"),
        parse_line("example.com##+js(set-constant, adblockDetected, false)"),
        parse_line("example.com#?#div:has(.advert)"),
    ]
    manifest: list = []
    cli._emit_layers(
        rules,
        tmp_path,
        "adblock_collection_full",
        manifest,
        gen_dns=True,
        policy={"level": "all"},
    )
    counts = {m["file"]: m["rules"] for m in manifest}
    assert (
        counts["adblock_collection_full_browser_network.txt"]
        + counts["adblock_collection_full_cosmetic.txt"]
        == len(rules)
    )


def test_dns_abp_matches_domains_set(tmp_path):
    from adblock_collection import writer

    rules = [
        parse_line("||ads.example.com^"),
        parse_line("||track.example.com^$third-party"),
        parse_line("@@||allow.example.com^"),
        parse_line("@@||doubleclick.net^$xhr,domain=yyets.click"),
        parse_line("example.com##.ad"),
    ]
    policy = {"level": "all"}
    abp = tmp_path / "a_dns_abp.txt"
    dom = tmp_path / "b_domains.txt"
    n1 = writer.write_domain_rules(rules, abp, "T", "D", policy)
    n2 = writer.write_domains(rules, dom, "T", policy)
    assert n1 == n2
    abp_domains = {
        line[2:-1]
        for line in abp.read_text(encoding="utf-8").splitlines()
        if line.startswith("||")
    }
    dom_domains = {
        line
        for line in dom.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    assert abp_domains == dom_domains


# ---------------- DNS 安全分级 ----------------


def test_classify_pure_domain_is_safe():
    v = classify_dns(parse_line("||ads.example.com^"))
    assert v.eligibility == DNS_SAFE
    assert v.confidence == 1.0


def test_classify_path_rule_is_reject():
    v = classify_dns(parse_line("||example.com/ads^"))
    assert v.eligibility == DNS_REJECT
    assert v.reason == "path_rule"


def test_classify_css_is_reject():
    v = classify_dns(parse_line("example.com##.ad-banner"))
    assert v.eligibility == DNS_REJECT


def test_classify_resource_type_rule_is_reject():
    # 资源类型限定无法在 DNS 层表达，任何档位都不得升级为整域拦截
    v = classify_dns(parse_line("||example.com^$script"))
    assert v.eligibility == DNS_REJECT
    assert v.reason == "resource_type_modifier"


def test_classify_party_rule_is_reject():
    v = classify_dns(parse_line("||example.com^$third-party"))
    assert v.eligibility == DNS_REJECT
    assert v.reason == "party_modifier"


def test_classify_unknown_modifier_rule_is_conditional():
    v = classify_dns(parse_line("||example.com^$some-unknown-opt"))
    assert v.eligibility == "CONDITIONAL"
    assert v.reason == "domain_modifier"


def test_classify_whole_domain_modifier_is_safe():
    for raw in (
        "||ads.example.com^$all",
        "||ads.example.com^$important",
        "||ads.example.com^$match-case",
        "||ads.example.com^$all,important",
    ):
        v = classify_dns(parse_line(raw))
        assert v.eligibility == DNS_SAFE, raw
        assert v.reason == "pure_domain_modifier", raw
        assert v.confidence == 1.0, raw
        assert is_dns_eligible(parse_line(raw), {"level": "all"}) is True, raw


def test_classify_whole_domain_modifier_rejects_scoped_or_path():
    # 带作用域或路径时仍不得升级为整域拦截
    assert classify_dns(parse_line("||ads.example.com^$all,domain=x.com")).reason == (
        "scoped_modifier"
    )
    assert classify_dns(parse_line("||ads.example.com/p^$all")).reason == "path_rule"


def test_classify_non_blocking_alias_is_reject():
    for raw in ("||ads.example.com^$ghide", "||ads.example.com^$shide"):
        v = classify_dns(parse_line(raw))
        assert v.reason == "non_blocking_modifier", raw
        assert is_dns_eligible(parse_line(raw), {"level": "safe"}) is False, raw


def test_classify_addheader_is_reject():
    r = parse_line("||site.example^$addheader=response:set-cookie:x=1")
    assert classify_dns(r).reason == "non_blocking_modifier"
    assert is_dns_eligible(r, {"level": "safe"}) is False


def test_type_and_party_modifiers_never_promoted_to_dns():
    # 资源类型与第一/第三方限定在 safe 档也不得升级为整域 DNS 拦截
    for raw in (
        "||ads.example.com^$third-party",
        "||ads.example.com^$script",
        "||ads.example.com^$subdocument",
        "||ads.example.com^$websocket",
        "||ads.example.com^$fetch",
        "||ads.example.com^$ping",
    ):
        r = parse_line(raw)
        assert is_dns_eligible(r, {"level": "all"}) is False, raw
        assert is_dns_eligible(r, {"level": "safe"}) is False, raw
        assert is_dns_eligible(r, {"level": "strict-safe"}) is False, raw


def test_classify_navigation_modifier_is_dns_eligible():
    for raw in (
        "||ads.example.com^$popup",
        "||ads.example.com^$doc",
        "||ads.example.com^$document",
        "||ads.example.com^$doc,popup",
    ):
        r = parse_line(raw)
        v = classify_dns(r)
        assert v.reason == "navigation_domain_modifier", raw
        # level: all 与 safe 都会输出；strict-safe 因置信度 0.8 被排除
        assert is_dns_eligible(r, {"level": "all"}) is True, raw
        assert is_dns_eligible(r, {"level": "safe"}) is True, raw
        assert is_dns_eligible(r, {"level": "strict-safe"}) is False, raw


def test_classify_navigation_modifier_scope_still_rejected():
    # 与作用域/资源类型/第三方限定混用时保持保守
    assert classify_dns(parse_line("||ads.example.com^$popup,domain=x.com")).reason == (
        "scoped_modifier"
    )
    assert classify_dns(parse_line("||ads.example.com^$popup,third-party")).reason == (
        "party_modifier"
    )
    assert (
        classify_dns(parse_line("||ads.example.com^$document,subdocument")).reason
        == "resource_type_modifier"
    )


def test_classify_app_scoped_rule_is_reject():
    # $app= 是 App 作用域限定，DNS 无法表达，任何档位都不得升级为整域拦截
    for raw in (
        "||snssdk.com^$app=com.dragon.read,important",
        "||fvedio.kuwo.cn^$app=cn.kuwo.player",
    ):
        v = classify_dns(parse_line(raw))
        assert v.eligibility == DNS_REJECT, raw
        assert v.reason == "scoped_modifier", raw
        assert is_dns_eligible(parse_line(raw), {"level": "safe"}) is False, raw


def test_classify_dnstype_scoped_rule_is_reject():
    r = parse_line("||wo.com.cn^$dnstype=A|CNAME")
    assert classify_dns(r).reason == "scoped_modifier"
    assert is_dns_eligible(r, {"level": "safe"}) is False


def test_classify_cname_rule_is_reject():
    r = parse_line("||example.com^$cname")
    assert classify_dns(r).reason == "match_method_modifier"
    assert is_dns_eligible(r, {"level": "safe"}) is False


def test_classify_negated_type_and_party_are_reject():
    # 取反形式同样限定了作用范围，不得当作未知修饰而放宽
    cases = {
        "||example.com^$~third-party": "party_modifier",
        "||example.com^$~3p": "party_modifier",
        "||example.com^$~script": "resource_type_modifier",
        "||example.com^$~image": "resource_type_modifier",
    }
    for raw, reason in cases.items():
        v = classify_dns(parse_line(raw))
        assert v.reason == reason, raw
        assert is_dns_eligible(parse_line(raw), {"level": "safe"}) is False, raw


def test_classify_reason_annotation_is_ignored():
    # $reason= 只是注解，不改变拦截语义
    v = classify_dns(parse_line("||ads.example.com^$all,reason=malicious"))
    assert v.eligibility == DNS_SAFE
    assert v.reason == "pure_domain_modifier"
    v = classify_dns(parse_line("||ads.example.com^$document,reason=malicious"))
    assert v.reason == "navigation_domain_modifier"


def test_classify_popunder_is_navigation():
    v = classify_dns(parse_line("||ads.example.com^$popunder"))
    assert v.reason == "navigation_domain_modifier"


def test_classify_empty_and_uritransform_are_non_blocking():
    assert (
        classify_dns(parse_line("||ads.example.com^$empty")).reason
        == "non_blocking_modifier"
    )
    assert (
        classify_dns(parse_line("||ads.example.com^$uritransform=/a//")).reason
        == "non_blocking_modifier"
    )


def test_cosmetic_rule_dollar_not_parsed_as_options():
    # 元素/脚本规则里的 $ 属于选择器或脚本参数，不能当选项解析
    css = parse_line("example.com#$#abort-current-inline-script $ popup")
    assert css.kind == "css"
    assert css.options == {}
    js = parse_line("example.com##+js(set-constant, $tieE3, true)")
    assert js.options == {}


def test_cosmetic_rule_norm_not_mangled_by_dollar():
    # 不同规则不得因 $ 被当作选项重排而折叠成同一去重键
    spaced = parse_line("example.com#$#abort-current-inline-script $ popup")
    joined = parse_line("example.com#$#abort-current-inline-script $popup")
    assert spaced.norm != joined.norm
    assert "$ popup" in spaced.norm
    assert spaced.norm == spaced.raw


def test_policy_all_rejects_modifier():
    # 未知修饰符是 CONDITIONAL 回退档：all 档拒绝、safe 档接受
    r = parse_line("||example.com^$some-unknown-opt")
    assert is_dns_eligible(r, {"level": "all"}) is False
    assert is_dns_eligible(r, {"level": "safe"}) is True


def test_policy_strict_safe_rejects_modifier():
    r = parse_line("||example.com^$some-unknown-opt")
    assert is_dns_eligible(r, {"level": "strict-safe"}) is False


def test_load_dns_policy_default_all(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n", encoding="utf-8"
    )
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

    assert writer._blocked_domains([parse_line("@@||example.com^")]) == set()


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


def test_check_allow_ignores_upstream_exception():
    # 上游例外不参与 DNS 剔除，误杀门禁按 DNS 阻断集合判定
    rules = [parse_line("||example.com^"), parse_line("@@||example.com^")]
    assert check_allow(rules, ["example.com"]) == [
        {"domain": "example.com", "blocked_by": "example.com"}
    ]


def test_check_allow_respects_custom_allowlist_exception():
    rules = [
        parse_line("||example.com^"),
        parse_line("@@||example.com^", source="LocalAllowlist"),
    ]
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
    cfg.write_text(
        "allow:\n  - google.com\nblock:\n  - doubleclick.net\n", encoding="utf-8"
    )
    fps = load_false_positives(cfg)
    assert fps["allow"] == ["google.com"]
    assert fps["block"] == ["doubleclick.net"]


def test_regression_end_to_end_via_cli(tmp_path):
    from adblock_collection.cli import regression_cmd

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\ndns_policy:\n  level: all\nsources:\n  - name: a\n    url: https://a\n",
        encoding="utf-8",
    )
    fp = tmp_path / "false_positives.yaml"
    fp.write_text(
        "allow:\n  - google.com\nblock:\n  - doubleclick.net\n", encoding="utf-8"
    )
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
    m = collect_metrics(
        rules, dns_domains=1, source_counts={"A": 2}, category_counts={"network": 2}
    )
    assert m.total_rules == 3
    assert m.dns_domains == 1
    assert m.root_domain_blocks == 1  # 仅 example.com（单点分隔）
    assert m.source_counts == {"A": 2}


def test_evaluate_passes_without_previous():
    from adblock_collection.quality_gate import Metrics

    m = Metrics(
        total_rules=100, dns_domains=10, source_counts={"A": 5}, category_counts={}
    )
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

    prev = Metrics(
        total_rules=1000, dns_domains=100, source_counts={"A": 500}, category_counts={}
    )
    cur = Metrics(
        total_rules=1500, dns_domains=100, source_counts={"A": 500}, category_counts={}
    )
    gate = evaluate(cur, prev, _default_thresholds())
    assert not gate.passed
    assert any("总规则数增长" in f for f in gate.failures)


def test_evaluate_flags_source_drop():
    from adblock_collection.quality_gate import Metrics

    prev = Metrics(
        total_rules=1000,
        dns_domains=100,
        source_counts={"A": 500, "B": 500},
        category_counts={},
    )
    cur = Metrics(
        total_rules=1000,
        dns_domains=100,
        source_counts={"A": 100, "B": 500},
        category_counts={},
    )
    gate = evaluate(cur, prev, _default_thresholds())
    assert not gate.passed
    assert any("骤降" in f for f in gate.failures)


def test_evaluate_flags_dns_surge():
    from adblock_collection.quality_gate import Metrics

    prev = Metrics(
        total_rules=1000, dns_domains=100, source_counts={"A": 500}, category_counts={}
    )
    cur = Metrics(
        total_rules=1000, dns_domains=200, source_counts={"A": 500}, category_counts={}
    )
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

    m = Metrics(
        total_rules=10, dns_domains=2, source_counts={"A": 1}, category_counts={}
    )
    save_previous(m, tmp_path)
    loaded = save_previous.__module__ and __import__(
        "adblock_collection.quality_gate", fromlist=["load_previous"]
    ).load_previous(tmp_path)
    assert loaded is not None
    assert loaded.total_rules == 10


def test_quality_gate_via_cli_build(tmp_path):

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
    # 直接调用 _run_quality_gate 逻辑：用 build 内部不便，单独构造
    from adblock_collection.merge import source_stats
    from adblock_collection.quality_gate import (
        collect_metrics,
        evaluate,
        load_previous,
        load_thresholds,
        save_previous,
        write_build_report,
    )
    from adblock_collection.rules import parse_line

    rules = [
        parse_line(x) for x in rules_txt.splitlines() if x and not x.startswith("!")
    ]
    sc = source_stats(rules)
    m1 = collect_metrics(rules, dns_domains=100, source_counts=sc, category_counts={})
    prev = load_previous(out)
    gate1 = evaluate(m1, prev, load_thresholds(cfg))
    write_build_report(out, m1, prev, gate1)
    save_previous(m1, out)
    assert gate1.passed

    # 第二轮：规则数暴增 200%，应失败
    rules_txt2 = "! t\n" + "\n".join(f"||b{i}.example.com^" for i in range(300)) + "\n"
    rules2 = [
        parse_line(x) for x in rules_txt2.splitlines() if x and not x.startswith("!")
    ]
    sc2 = source_stats(rules2)
    m2 = collect_metrics(rules2, dns_domains=300, source_counts=sc2, category_counts={})
    prev2 = load_previous(out)
    gate2 = evaluate(m2, prev2, load_thresholds(cfg))
    assert not gate2.passed


def test_quality_gate_failure_preserves_baseline(tmp_path):
    from adblock_collection.cli import _run_quality_gate
    from adblock_collection.merge import source_stats
    from adblock_collection.quality_gate import Metrics, load_previous, save_previous
    from adblock_collection.rules import parse_line

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nquality_gate:\n  total_rule_growth_percent: 10\n"
        "sources:\n  - name: a\n    url: https://a\n",
        encoding="utf-8",
    )
    out = tmp_path / "dist"
    out.mkdir()
    save_previous(Metrics(total_rules=10, dns_domains=10), out)

    rules = [parse_line(f"||a{i}.example.com^") for i in range(100)]
    failed, _ = _run_quality_gate(
        rules,
        source_stats(rules),
        {},
        {"domains": (out / "x.txt", 100)},
        out,
        cfg,
    )
    assert failed
    assert load_previous(out).total_rules == 10


def test_build_report_records_source_diff(tmp_path):
    from adblock_collection.quality_gate import GateResult, Metrics, write_build_report

    prev = Metrics(total_rules=10, source_counts={"a": 10, "gone": 5})
    cur = Metrics(total_rules=12, source_counts={"a": 12, "new": 3})
    report = write_build_report(tmp_path, cur, prev, GateResult(passed=True))
    sources = report["diff"]["sources"]
    assert sources["a"] == {
        "current": 12,
        "previous": 10,
        "delta": 2,
        "percent": 20.0,
    }
    assert sources["gone"]["delta"] == -5
    assert sources["new"]["previous"] == 0


def test_build_report_source_diff_empty_without_previous(tmp_path):
    from adblock_collection.quality_gate import GateResult, Metrics, write_build_report

    cur = Metrics(total_rules=10, source_counts={"a": 10})
    report = write_build_report(tmp_path, cur, None, GateResult(passed=True))
    assert report["diff"]["sources"] == {}


def test_quality_gate_warns_on_source_growth():
    from adblock_collection.quality_gate import (
        DEFAULT_THRESHOLDS,
        Metrics,
        evaluate,
    )

    prev = Metrics(source_counts={"a": 10})
    cur = Metrics(source_counts={"a": 20})
    gate = evaluate(cur, prev, dict(DEFAULT_THRESHOLDS))
    assert gate.passed
    assert any("上游 a" in warning and "增长" in warning for warning in gate.warnings)



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
    from adblock_collection.cli import _emit_security

    monkeypatch.chdir(tmp_path)
    rules = [
        parse_line("||malware.example.com^"),
        parse_line("||phishing.example.com^"),
        parse_line("||ads.example.com^"),
    ]
    sp = {"categories": ["malware", "phishing"], "source_drop_percent": 80.0}
    manifest = []
    _emit_security(
        rules, tmp_path, sp, manifest, gen_dns=True, dns_policy={"level": "all"}
    )

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
        'live.bilibili.com##[class*="recommend"]\n'
        "||ad.douyin.com^\n",
        encoding="utf-8",
    )
    assert validate_local_rules(cfg) == []


def test_validate_local_rules_blocks_wildcard(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("sources: []\n", encoding="utf-8")
    lr = tmp_path / "local_rules.txt"
    lr.write_text(
        'example.com##*\nexample.com##body\n##[class*="ad"]\n*##.banner\n',
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


# ---------------- hosts / 纯域名上游规范化 ----------------


def test_hosts_line_normalized_to_network_rule():
    r = parse_line("0.0.0.0 ads.example.com")
    assert r is not None
    assert r.kind == "network"
    assert r.raw == "||ads.example.com^"
    assert r.domains == ["ads.example.com"]


def test_hosts_line_skips_boilerplate_and_inline_comment():
    assert parse_line("127.0.0.1 localhost") is None
    assert parse_line("::1 ip6-localhost") is None
    assert parse_line("0.0.0.0") is None
    r = parse_line("127.0.0.1 tracker.example.com # comment")
    assert r is not None
    assert r.raw == "||tracker.example.com^"


def test_bare_domain_line_normalized():
    r = parse_line("ubmcmm.baidustatic.com")
    assert r is not None
    assert r.raw == "||ubmcmm.baidustatic.com^"
    # 单标签不是合法域名，原样保留且不产生 DNS 域名
    assert parse_line("notadomain").domains == []


def test_parse_lines_expands_multi_domain_hosts_line():
    rules = parse_lines(["0.0.0.0 a.example.com b.example.com", "||c.example.com^"])
    assert {r.raw for r in rules} == {
        "||a.example.com^",
        "||b.example.com^",
        "||c.example.com^",
    }


def test_hash_comment_skipped_but_no_domain_cosmetic_kept():
    assert parse_line("#189") is None
    r = parse_line("###AC_ad")
    assert r is not None
    assert r.kind == "css"


def test_hosts_source_domain_enters_dns():
    from adblock_collection import writer

    assert writer._blocked_domains([parse_line("0.0.0.0 ads.example.com")]) == {
        "ads.example.com"
    }


def test_collect_expands_hosts_source_into_dns(tmp_path, monkeypatch):
    import hashlib

    from adblock_collection import writer
    from adblock_collection.merge import collect

    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: h\n    url: https://h\n    category: network\n",
        encoding="utf-8",
    )
    cs = tmp_path / ".cache" / "sources"
    cs.mkdir(parents=True, exist_ok=True)
    cp = cs / hashlib.sha256(b"https://h").hexdigest()[:16]
    cp.write_text(
        "# 注释\n0.0.0.0 ads.example.com\n127.0.0.1 localhost\n",
        encoding="utf-8",
    )
    res = collect(cfg, use_cache=True, offline=True, use_stage_cache=False)
    rules = res["all"][0][1]
    assert {r.raw for r in rules} == {"||ads.example.com^"}
    assert writer._blocked_domains(rules) == {"ads.example.com"}


# ---------------- 非阻断修饰符不得进入 DNS ----------------


def test_removeparam_not_dns_eligible_even_safe_policy():
    r = parse_line("||sponichi.co.jp^$removeparam=ref")
    assert classify_dns(r).reason == "non_blocking_modifier"
    assert is_dns_eligible(r, {"level": "all"}) is False
    assert is_dns_eligible(r, {"level": "safe"}) is False


def test_non_blocking_modifiers_rejected_from_dns():
    raws = [
        "||example.com^$csp=script-src-attr 'none'",
        "||example.com^$replace=/a/b/",
        "||example.com^$permissions=geolocation=()",
        "||example.com^$header=vary:/x/i",
        "||example.com^$urlskip=x",
        "||example.com^$cookie=x",
    ]
    for raw in raws:
        assert is_dns_eligible(parse_line(raw), {"level": "safe"}) is False, raw


def test_redirect_rule_rejected_from_dns():
    r = parse_line("||acacdn.com/script/*.js$script,redirect-rule=noop.js")
    assert is_dns_eligible(r, {"level": "safe"}) is False


def test_third_party_modifier_never_eligible():
    r = parse_line("||example.com^$third-party")
    assert is_dns_eligible(r, {"level": "safe"}) is False
    assert is_dns_eligible(r, {"level": "all"}) is False


def test_unknown_modifier_conditional_at_safe_policy():
    r = parse_line("||example.com^$some-unknown-opt")
    assert is_dns_eligible(r, {"level": "safe"}) is True
    assert is_dns_eligible(r, {"level": "all"}) is False


def test_scoped_modifiers_rejected_from_dns():
    raws = [
        "||ads.example.com^$domain=shop.example.org",
        "||a.example.com^$to=b.example.org",
        "||a.example.com^$from=b.example.org",
        "||a.example.com^$denyallow=b.example.org",
        "||a.example.com^$ipaddress=1.2.3.4",
        "||a.example.com^$method=get",
    ]
    for raw in raws:
        r = parse_line(raw)
        assert classify_dns(r).reason == "scoped_modifier", raw
        assert is_dns_eligible(r, {"level": "safe"}) is False, raw
        assert is_dns_eligible(r, {"level": "all"}) is False, raw


# ---------------- domain= 是作用域，不是目标域名 ----------------


def test_domain_option_is_scope_not_target():
    assert parse_line("*$domain=a.com").domains == []
    assert parse_line("@@/banner/ad/*$image,domain=a.com").domains == []


def test_scoped_rule_does_not_drop_real_domain_rule():
    kept = remove_redundant_domains(
        [parse_line("||a.com^"), parse_line("*$domain=a.com")]
    )
    assert {r.raw for r in kept} == {"||a.com^", "*$domain=a.com"}


def test_scoped_exception_does_not_allowlist_target_domain():
    from adblock_collection import writer

    rules = [parse_line("||a.com^"), parse_line("@@/banner/ad/*$image,domain=a.com")]
    assert sorted(writer._blocked_domains(rules)) == ["a.com"]


def test_scoped_domain_exception_does_not_disable_dns_block():
    from adblock_collection import writer

    rules = [
        parse_line("||doubleclick.net^"),
        parse_line("@@||doubleclick.net^$xmlhttprequest,domain=yyets.click"),
    ]
    assert writer._blocked_domains(rules) == {"doubleclick.net"}


def test_path_exception_does_not_disable_dns_block():
    from adblock_collection import writer

    rules = [
        parse_line("||scorecardresearch.com^"),
        parse_line("@@||scorecardresearch.com^*/streamingtag_jwplayer.js"),
    ]
    assert writer._blocked_domains(rules) == {"scorecardresearch.com"}


def test_pure_domain_upstream_exception_keeps_dns_block():
    from adblock_collection import writer

    rules = [parse_line("||a.com^"), parse_line("@@||a.com^")]
    assert writer._blocked_domains(rules) == {"a.com"}


def test_pure_domain_custom_exception_disables_dns_block():
    from adblock_collection import writer

    rules = [
        parse_line("||a.com^"),
        parse_line("@@||a.com^", source="LocalAllowlist"),
    ]
    assert writer._blocked_domains(rules) == set()


# ---------------- 本地规则扩展分隔符校验 ----------------


def test_validate_local_rules_blocks_extended_separator_wildcards(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("sources: []\n", encoding="utf-8")
    lr = tmp_path / "local_rules.txt"
    lr.write_text(
        "example.com#?#*\n"
        "example.com$$*\n"
        "example.com#?#div:has(> a)\n"
        'example.com$$div[ad_dot_url="adclick"]\n',
        encoding="utf-8",
    )
    v = validate_local_rules(cfg)
    assert len(v) == 2
    assert any("#?#*" in x for x in v)
    assert any("$$*" in x for x in v)
