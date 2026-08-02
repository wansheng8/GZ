"""测试解析器模块"""

from src.config import SourceConfig
from src.parser import (
    parse_rules,
    is_metadata_line,
    classify_rule,
    extract_domain,
    Rule,
)


def make_source(name="TestSource", priority=1):
    return SourceConfig(name=name, url="http://example.com", priority=priority)


def test_is_metadata_line():
    """测试元数据行判断"""
    assert is_metadata_line("! This is a comment") is True
    assert is_metadata_line("! Title: Test") is True
    assert is_metadata_line("[Adblock Plus 2.0]") is True
    assert is_metadata_line("") is True
    assert is_metadata_line("   ") is True
    assert is_metadata_line("||example.com^") is False
    assert is_metadata_line("@@||example.com^") is False
    assert is_metadata_line("example.com##.ad") is False


def test_classify_rule():
    """测试规则分类"""
    assert classify_rule("@@||example.com^") == "exception"
    assert classify_rule("@@||example.com^$document") == "exception"
    assert classify_rule("example.com##.ad-banner") == "hide"
    assert classify_rule("##.ad-banner") == "hide"
    assert classify_rule("||example.com^") == "block"
    assert classify_rule("||example.com/ads/*") == "block"


def test_extract_domain():
    """测试域名提取"""
    assert extract_domain("||example.com^") == "example.com"
    assert extract_domain("||ads.example.com^") == "ads.example.com"
    assert extract_domain("@@||example.com^") == "example.com"
    assert extract_domain("127.0.0.1 tracker.com") == "tracker.com"
    assert extract_domain("0.0.0.0 ads.example.com") == "ads.example.com"
    assert extract_domain("##.ad-banner") == ""


def test_parse_basic_rules():
    """测试基本规则解析"""
    content = """[Adblock Plus 2.0]
! Title: Test List
! Comment line
||example.com^
@@||whitelist.com^
example.com##.ad-banner
! Another comment
||tracker.com/ads/*
"""

    source = make_source()
    rules = parse_rules(content, source)

    # 应有 4 个有效规则: example.com^, @@whitelist.com^, hide rule, tracker.com/ads/*
    # 加上 Title: 元数据行
    assert len(rules) >= 4

    rule_texts = [r.raw for r in rules]
    assert "||example.com^" in rule_texts
    assert "@@||whitelist.com^" in rule_texts
    assert "example.com##.ad-banner" in rule_texts
    assert "||tracker.com/ads/*" in rule_texts


def test_parse_hosts_rules():
    """测试 hosts 格式规则转换"""
    content = """127.0.0.1 ad.tracker.com
0.0.0.0 bad.ad.server.com
||normal.rule.com^
"""

    source = make_source()
    rules = parse_rules(content, source)

    # hosts 规则应被转换为 adblock 格式
    normalized_texts = [r.normalized for r in rules]
    assert "||ad.tracker.com^" in normalized_texts
    assert "||bad.ad.server.com^" in normalized_texts
    assert "||normal.rule.com^" in normalized_texts


def test_rule_metadata():
    """测试 Rule 对象元数据"""
    content = "||example.com^\n"

    source = make_source("EasyList", priority=1)
    rules = parse_rules(content, source)

    assert len(rules) == 1
    rule = rules[0]
    assert rule.raw == "||example.com^"
    assert rule.source == "EasyList"
    assert rule.priority == 1
    assert rule.domain == "example.com"
    assert rule.rule_type == "block"
