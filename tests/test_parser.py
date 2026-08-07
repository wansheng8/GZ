"""测试解析器模块"""

from src.config import SourceConfig
from src.parser import (
    parse_rules,
    is_metadata_line,
    classify_rule,
    extract_domain,
    parse_options,
    Rule,
    RULE_BLOCK,
    RULE_EXCEPTION,
    RULE_HIDE,
    RULE_HIDE_EXCEPTION,
    RULE_CSS_EXT,
    RULE_SCRIPTLET,
    RULE_CSS_INJECT,
    RULE_HTML,
    RULE_HTML_EXCEPTION,
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


def test_classify_extended_syntax():
    """测试扩展语法分类：隐藏例外/扩展 CSS/脚本注入/HTML 过滤"""
    assert classify_rule("example.com#@#.important-banner") == RULE_HIDE_EXCEPTION
    assert classify_rule("example.com#?#div:has(.ad)") == RULE_CSS_EXT
    assert classify_rule("example.com#@?#div:has(.ad)") == RULE_CSS_EXT
    assert classify_rule("example.com##+js(setTimeout-defuser.js, adInit, 100)") == RULE_SCRIPTLET
    assert classify_rule("example.com#%#//scriptlet('abort-on-property-read.js', 'I10C')") == RULE_SCRIPTLET
    assert classify_rule("example.com$$div[class=\"ad\"]") == RULE_HTML


def test_classify_css_inject_and_exceptions():
    """测试样式注入与例外：#$#/#%# 按内容嗅探区分脚本/样式"""
    # 样式注入（非脚本内容）
    assert classify_rule("example.com#$#body { background: #fff !important; }") == RULE_CSS_INJECT
    assert classify_rule("example.com#%#.ad-banner { display: none !important; }") == RULE_CSS_INJECT
    # 样式注入例外
    assert classify_rule("example.com#@$#.ad-banner { display: none !important; }") == RULE_CSS_INJECT
    assert classify_rule("example.com#@%#.ad-banner { display: none !important; }") == RULE_CSS_INJECT
    # 脚本注入仍归 scriptlet（script: / //scriptlet 前缀）
    assert classify_rule("example.com#$#script:inject(abort-on-property-read.js, I10C)") == RULE_SCRIPTLET
    assert classify_rule("example.com#%#//scriptlet('abort-on-property-read.js', 'I10C')") == RULE_SCRIPTLET
    assert classify_rule("example.com##+js(abort.js, x)") == RULE_SCRIPTLET


def test_classify_html_exceptions():
    """测试 HTML 过滤例外：#@$$ 与 #@#^"""
    assert classify_rule("example.com#@$$div[class=\"ad\"]") == RULE_HTML_EXCEPTION
    # uBO HTML 过滤例外（#@#^）与过滤（##^）
    assert classify_rule("example.com#@#^script:has-text(important)") == RULE_HIDE_EXCEPTION
    assert classify_rule("example.com##^script:has-text(advertisement.js)") == RULE_HIDE


def test_parse_options():
    """测试 $options 结构化解析"""
    options, pattern = parse_options("||example.com^$script,image,domain=a.com|~b.com,important")
    assert pattern == "||example.com^"
    assert options["script"] is True
    assert options["image"] is True
    assert options["important"] is True
    assert options["domain"] == "a.com|~b.com"

    # 无选项时返回空字典与原文
    options, pattern = parse_options("||example.com^")
    assert options == {}
    assert pattern == "||example.com^"

    # 带值选项
    options, _ = parse_options("||example.com^$redirect=noop.txt")
    assert options["redirect"] == "noop.txt"


def test_parse_options_regex_values():
    """测试正则形式选项值（内部含逗号/转义斜杠）不被误拆"""
    # replace 正则内含逗号
    options, pattern = parse_options("||example.com^$replace=/(a,b)/g,script")
    assert pattern == "||example.com^"
    assert options["replace"] == "/(a,b)/g"
    assert options["script"] is True

    # replace 正则含转义斜杠，且后随其他选项
    options, _ = parse_options("||example.com^$replace=/\\/ads\\//g,image")
    assert options["replace"] == "/\\/ads\\//g"
    assert options["image"] is True

    # removeparam 正则形式
    options, _ = parse_options("||example.com^$removeparam=/^utm_/")
    assert options["removeparam"] == "/^utm_/"


def test_parse_options_dollar_in_pattern():
    """测试 pattern 中裸 $ 的回退：$ 后无合法选项时按无选项处理"""
    options, pattern = parse_options("|http://example.com/$/ads|")
    assert options == {}
    assert pattern == "|http://example.com/$/ads|"

    # 正常选项区不受影响
    options, pattern = parse_options("|http://example.com/ads|$script")
    assert options["script"] is True
    assert pattern == "|http://example.com/ads|"


def test_parse_options_escaped_comma():
    """测试选项值内 \\, 转义逗号（$permissions 等）不被拆分"""
    options, pattern = parse_options(
        "||example.com^$permissions=autoplay=()\\, camera=(),script"
    )
    assert pattern == "||example.com^"
    assert options["permissions"] == "autoplay=()\\, camera=()"
    assert options["script"] is True

    # 别名选项 xhr / rewrite / stealth 可被识别为合法选项
    options, _ = parse_options("||example.com^$xhr,rewrite=/a/b/,stealth")
    assert options["xhr"] is True
    assert options["rewrite"] == "/a/b/"
    assert options["stealth"] is True


def test_parse_rules_extended_types():
    """测试解析后各扩展类型的 rule_type 与 options"""
    content = """@@||example.com^$important
||tracker.com^$script,domain=example.com
example.com#@#.important-banner
example.com##+js(abort-on-property-read.js, I10C)
example.com$$div[class="ad"]
"""
    source = make_source()
    rules = parse_rules(content, source)

    types = {r.rule_type for r in rules}
    assert types == {
        RULE_EXCEPTION, RULE_BLOCK, RULE_HIDE_EXCEPTION, RULE_SCRIPTLET, RULE_HTML,
    }

    # 网络规则的 options 被结构化解析
    block = [r for r in rules if r.rule_type == RULE_BLOCK][0]
    assert block.options["script"] is True
    assert block.options["domain"] == "example.com"
    assert block.pattern == "||tracker.com^"

    exception = [r for r in rules if r.rule_type == RULE_EXCEPTION][0]
    assert exception.options["important"] is True


def test_parse_rules_options_not_applied_to_hide():
    """测试元素规则不误解析 $options"""
    content = "example.com##div:has-text(广告)\n"
    source = make_source()
    rules = parse_rules(content, source)
    assert rules[0].rule_type == RULE_HIDE
    assert rules[0].options == {}
    assert rules[0].pattern == "example.com##div:has-text(广告)"


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


def test_parse_hosts_with_comments():
    """测试 hosts 行内注释剥离与整行 # 注释跳过"""
    content = """127.0.0.1 ad.tracker.com   # 追踪服务器
# 下面这行是临时屏蔽
0.0.0.0 bad.ad.com
##.global-hide
"""
    source = make_source()
    rules = parse_rules(content, source)

    normalized_texts = [r.normalized for r in rules]
    raw_texts = [r.raw for r in rules]

    # 行内注释被剥除，不生成含注释的非法 hosts 规则
    assert "||ad.tracker.com^" in normalized_texts
    assert "||bad.ad.com^" in normalized_texts
    assert not any(n.startswith("||") and "#" in n for n in normalized_texts)
    # 整行 # 注释不产生规则
    assert len(rules) == 3
    # ##.global-hide 是合法全局元素规则，不被误判为注释
    assert "##.global-hide" in raw_texts


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


def test_parse_metadata_homepage_kept_version_dropped():
    """测试元数据行: Homepage 保留为 header，Version 被丢弃（聚合器自生成）"""
    content = """! Title: Test List
! Expires: 4 days
! Homepage: https://example.com
! Version: 20240101
! Contact: someone@example.com
"""
    source = make_source()
    rules = parse_rules(content, source)

    header_texts = [r.raw for r in rules]
    assert "! Title: Test List" in header_texts
    assert "! Expires: 4 days" in header_texts
    assert "! Homepage: https://example.com" in header_texts
    # Version 与普通注释不被保留为 header
    assert "! Version: 20240101" not in header_texts
    assert "! Contact: someone@example.com" not in header_texts


def test_parse_rules_multi_site_domains():
    """测试多站点限定元素规则的域名结构化与顺序无关去重键"""
    source = make_source()
    rules = parse_rules(
        "example.com,foo.org##.sponsor\n##.ad-banner\n||tracker.com^\n",
        source,
    )

    multi = rules[0]
    assert multi.rule_type == RULE_HIDE
    assert multi.domains == ["example.com", "foo.org"]
    # domain 字段保持兼容（取首个域名）
    assert multi.domain == "example.com"

    # 全局规则无站点限定
    assert rules[1].domains == []

    # 网络规则不解析多站点
    assert rules[2].domains == []

    # 顺序无关：两个语义相同的多站点规则去重键一致
    a = parse_rules("example.com,foo.org##.sponsor\n", source)[0]
    b = parse_rules("foo.org,example.com##.sponsor\n", source)[0]
    assert a.normalized == b.normalized == "example.com,foo.org##.sponsor"
    assert a.raw != b.raw  # 原文各自保留


def test_parse_multi_site_negation_and_other_types():
    """测试多站点提取对否定域名与扩展分隔符的兼容"""
    source = make_source()

    # 否定域名保留 ~ 前缀
    r = parse_rules("example.com,~foo.org#@#.x\n", source)[0]
    assert r.domains == ["example.com", "~foo.org"]

    # 扩展 CSS 与脚本注入同样支持多站点限定
    r = parse_rules("example.com,foo.org#?#div:has(.ad)\n", source)[0]
    assert r.domains == ["example.com", "foo.org"]
    r = parse_rules("example.com,foo.org##+js(abort.js, x)\n", source)[0]
    assert r.domains == ["example.com", "foo.org"]
    assert r.rule_type == RULE_SCRIPTLET
