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
    assert "domain=a.com|m.com|z.com" in result


def test_match_case_preserves_case():
    """测试 match-case 选项保留匹配部分大小写"""
    result = normalize_rule("||Example.COM/Ads^$match-case")
    assert "Example.COM/Ads" in result
    assert result == "||Example.COM/Ads^$match-case"

    # 无 match-case 时仍统一小写
    assert normalize_rule("||Example.COM/Ads^") == "||example.com/ads^"


def test_options_separated_from_pattern():
    """测试选项区与匹配模式分离处理，选项顺序不受 www 剥离影响"""
    result = normalize_rule("||www.example.com^$domain=z.com|a.com")
    assert result == "||example.com^$domain=a.com|z.com"


def test_idempotent():
    """测试幂等性：多次标准化结果相同"""
    rule = "  ||www.Example.COM^$domain=z.com|a.com  "
    first = normalize_rule(rule)
    second = normalize_rule(first)
    assert first == second


def test_multi_site_domain_sorting():
    """测试多站点元素规则的域名顺序无关标准化"""
    a = normalize_rule("example.com,foo.org##.sponsor")
    b = normalize_rule("foo.org,example.com##.sponsor")
    assert a == b == "example.com,foo.org##.sponsor"

    # 含否定域名、空格与扩展分隔符
    c = normalize_rule("~foo.org, example.com#@#.x")
    d = normalize_rule("example.com,~foo.org#@#.x")
    assert c == d == "example.com,~foo.org#@#.x"

    # 脚本注入分隔符
    e = normalize_rule("example.com,foo.org##+js(abort.js, x)")
    f = normalize_rule("foo.org,example.com##+js(abort.js, x)")
    assert e == f == "example.com,foo.org##+js(abort.js, x)"

    # 单站点与全局规则不受影响
    assert normalize_rule("example.com##.ad") == "example.com##.ad"
    assert normalize_rule("##.ad") == "##.ad"

    # 新增分隔符: 样式注入例外 / HTML 过滤例外
    g = normalize_rule("example.com,foo.org#@$#.ad { display: none; }")
    h = normalize_rule("foo.org,example.com#@$#.ad { display: none; }")
    assert g == h == "example.com,foo.org#@$#.ad { display: none; }"
    i = normalize_rule("example.com,foo.org#@$$div")
    j = normalize_rule("foo.org,example.com#@$$div")
    assert i == j == "example.com,foo.org#@$$div"
