"""测试标准化模块"""

from src.normalizer import normalize_rule


def test_strip_whitespace():
    """测试去除空白"""
    assert normalize_rule("  ||example.com^  ") == "||example.com^"
    assert normalize_rule("\t||example.com^\t") == "||example.com^"


def test_lowercase():
    """测试统一小写"""
    assert normalize_rule("||Example.COM^") == "||example.com^"
    assert normalize_rule("@@||WhiteList.Com^") == "@@||whitelist.com^"


def test_collapse_spaces():
    """测试空白折叠"""
    result = normalize_rule("||example.com^$domain=example.com   |   foo.com")
    assert "  " not in result


def test_remove_www_prefix():
    """测试去除 www. 前缀"""
    assert "www.example.com" not in normalize_rule("||www.example.com^")
    assert normalize_rule("||www.example.com^") == "||example.com^"


def test_domain_options_sorting():
    """测试 $domain= 参数排序"""
    result = normalize_rule("||example.com^$domain=z.com|a.com|m.com")
    assert "domain=a.com,m.com,z.com" in result


def test_idempotent():
    """测试幂等性：多次标准化结果相同"""
    rule = "  ||www.Example.COM^$domain=z.com|a.com  "
    first = normalize_rule(rule)
    second = normalize_rule(first)
    assert first == second
