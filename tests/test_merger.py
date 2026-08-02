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
