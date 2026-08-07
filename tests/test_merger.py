"""测试合并去重模块"""

from src.config import SourceConfig
from src.parser import parse_rules, Rule
from src.merger import RuleMerger, _deduplicate_exact, _deduplicate_subset, _is_broader_rule


def make_source(name, priority):
    return SourceConfig(name=name, url=f"http://{name}.com", priority=priority)


def make_rule(raw, normalized, rule_type, source, priority, domain=""):
    return Rule(
        raw=raw,
        normalized=normalized,
        rule_type=rule_type,
        domain=domain,
        source=source,
        priority=priority,
    )


def test_merger_multi_site_dedup():
    """测试多站点限定的 hide 规则：域名顺序不同视为重复"""
    merger = RuleMerger()
    src = make_source("Test", 1)

    # 两条语义相同、域名顺序不同的多站点规则
    rules = parse_rules(
        "example.com,foo.org##.sponsor\nfoo.org,example.com##.sponsor\n",
        src,
    )
    assert len(rules) == 2
    merger.add_source(rules)

    merged = merger.merge()
    assert len(merged) == 1
    # 保留高优先级源的原文（此处同源，保留先出现的一条）
    assert merged[0].raw == "example.com,foo.org##.sponsor"


def test_merger_does_not_merge_distinct_multi_site():
    """测试不同多站点组合的 hide 规则不会被误合并"""
    merger = RuleMerger()
    src = make_source("Test", 1)

    rules = parse_rules(
        "example.com,foo.org##.sponsor\nexample.com,bar.org##.sponsor\n",
        src,
    )
    merger.add_source(rules)

    merged = merger.merge()
    assert len(merged) == 2


def test_exact_dedup_priority():
    """测试精确去重：保留高优先级源的规则"""
    rules = [
        make_rule("||example.com^", "||example.com^", "block", "EasyList", 1, "example.com"),
        make_rule("||example.com^", "||example.com^", "block", "AdGuard", 3, "example.com"),
        make_rule("||foo.com^", "||foo.com^", "block", "AdGuard", 3, "foo.com"),
        make_rule("||foo.com^", "||foo.com^", "block", "AntiAD", 6, "foo.com"),
    ]

    result = _deduplicate_exact(rules)

    assert len(result) == 2
    # EasyList (priority 1) 的 example.com 规则应被保留
    assert result[0].source == "EasyList"
    # AdGuard (priority 3) 的 foo.com 应被保留（相比 AntiAD priority 6）
    assert result[1].source == "AdGuard"


def test_exact_dedup_no_duplicates():
    """测试无重复规则"""
    rules = [
        make_rule("||a.com^", "||a.com^", "block", "EasyList", 1),
        make_rule("||b.com^", "||b.com^", "block", "EasyList", 1),
        make_rule("||c.com^", "||c.com^", "block", "EasyList", 1),
    ]

    result = _deduplicate_exact(rules)
    assert len(result) == 3


def test_merger_merge_order():
    """测试合并后的规则顺序：exception 在前，block 在后"""
    merger = RuleMerger()

    rules = [
        make_rule("||block.com^", "||block.com^", "block", "Test", 1, "block.com"),
        make_rule("@@||safe.com^", "@@||safe.com^", "exception", "Test", 1, "safe.com"),
        make_rule("example.com##.ad", "example.com##.ad", "hide", "Test", 1, "example.com"),
    ]
    merger.add_source(rules)

    merged = merger.merge()

    # exception 规则应最先出现
    assert merged[0].rule_type == "exception"
    # block 规则随后
    assert merged[1].rule_type == "block"
    # hide 规则最后
    assert merged[2].rule_type == "hide"


def test_subset_dedup():
    """测试子集去重"""
    rules = [
        make_rule("||example.com^", "||example.com^", "block", "EasyList", 1, "example.com"),
        make_rule("||ads.example.com^", "||ads.example.com^", "block", "EasyList", 1, "ads.example.com"),
    ]

    result = _deduplicate_subset(rules)

    # ads.example.com 是 example.com 的子域名，应被移除
    assert len(result) == 1
    assert result[0].domain == "example.com"


def test_is_broader_rule():
    """测试父子规则关系判断"""
    # 父规则覆盖子域名
    assert _is_broader_rule("||example.com^", "||ads.example.com^") is True
    # 父规则覆盖子路径
    assert _is_broader_rule("||example.com^", "||example.com/ads^") is True
    # 不相关的域名
    assert _is_broader_rule("||example.com^", "||other.com^") is False
    # 相同的规则
    assert _is_broader_rule("||example.com^", "||example.com^") is False


def test_merger_multi_source():
    """测试多源合并"""
    merger = RuleMerger()

    source1 = make_source("EasyList", 1)
    content1 = "||same-rule.com^\n||easy-only.com^\n"
    rules1 = parse_rules(content1, source1)

    source2 = make_source("AdGuard", 3)
    content2 = "||same-rule.com^\n||adguard-only.com^\n"
    rules2 = parse_rules(content2, source2)

    merger.add_source(rules1)
    merger.add_source(rules2)

    merged = merger.merge()

    # 应保留 2 条唯一规则（same-rule.com 去重）
    normals = {r.normalized for r in merged}
    assert "||same-rule.com^" in normals
    assert "||easy-only.com^" in normals
    assert "||adguard-only.com^" in normals
    assert len(normals) == 3


def test_merger_preserves_headers():
    """测试 header 元数据规则被保留并置于最前"""
    merger = RuleMerger()

    rules = [
        make_rule("! Title: EasyList", "! title: easylist", "header", "EasyList", 1),
        make_rule("||example.com^", "||example.com^", "block", "EasyList", 1, "example.com"),
        make_rule("! Title: EasyList", "! title: easylist", "header", "AdGuard", 3),
    ]
    merger.add_source(rules)

    merged = merger.merge()

    headers = [r for r in merged if r.rule_type == "header"]
    # 重复的 header 行应被去重为 1 条
    assert len(headers) == 1
    assert headers[0].raw == "! Title: EasyList"
    # header 规则应位于输出最前
    assert merged[0].rule_type == "header"
    # 非 header 规则仍正常保留
    assert any(r.rule_type == "block" for r in merged)


def test_merger_hide_exception_before_hide():
    """测试元素隐藏例外 (#@#) 排在普通隐藏规则 (##) 之前"""
    merger = RuleMerger()

    rules = [
        make_rule("example.com##.ad", "example.com##.ad", "hide", "Test", 1, "example.com"),
        make_rule("example.com#@#.ad", "example.com#@#.ad", "hide-exception", "Test", 1, "example.com"),
        make_rule("example.com##+js(abort.js, x)", "example.com##+js(abort.js, x)", "scriptlet", "Test", 1, "example.com"),
        make_rule("example.com$$div.ad", "example.com$$div.ad", "html", "Test", 1, "example.com"),
    ]
    merger.add_source(rules)

    merged = merger.merge()

    hide_types = [r.rule_type for r in merged]
    # 元素类规则整体在 block 之后
    assert merged[0].rule_type == "hide-exception"
    # 隐藏例外排在普通隐藏之前
    assert hide_types.index("hide-exception") < hide_types.index("hide")
    # 脚本注入与 HTML 过滤均在 hide section 内
    assert "scriptlet" in hide_types
    assert "html" in hide_types
