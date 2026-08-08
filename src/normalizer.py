"""标准化模块 - 规则标准化，确保语义相同的规则归一化为同一形式"""

import re

# 元素规则分隔符（按特异性从高到低，与 parser 分类顺序一致）
_ELEMENT_SEPS = (
    "#@?#",    # 扩展 CSS 例外 (uBO)
    "#@#",     # 元素隐藏例外（含 #@#^ uBO HTML 例外）
    "#?#",     # 扩展 CSS (uBO)
    "#@$$",    # HTML 过滤例外 (AdGuard)
    "#@$#",    # 样式注入例外 (AdGuard)
    "#@%#",    # 样式注入例外 (AdGuard)
    "#@$?#",   # 扩展选择器样式注入例外 (AdGuard)
    "#$?#",    # 扩展选择器样式注入 (AdGuard)
    "#%#",     # 脚本/样式注入 (AdGuard)
    "#$#",     # 脚本/样式注入 (AdGuard)
    "##+js(",  # 脚本注入 (uBO)
    "$$",      # HTML 过滤 (AdGuard)
    "##",      # 普通元素隐藏（含 ##^ uBO HTML 过滤）
)


def normalize_rule(rule_text: str) -> str:
    """标准化规则文本

    标准化步骤：
    1. 去除首尾空白
    2. 分离 $options 部分；除非规则带 match-case 选项，否则统一小写
    3. 折叠连续空白为单个空格
    4. 去除 www. 域名前缀（规则匹配层面等价时）
    5. 对 $domain= 选项内的域名排序（参数顺序不影响语义）

    Args:
        rule_text: 原始规则文本

    Returns:
        标准化后的规则文本
    """
    normalized = rule_text.strip()
    if not normalized:
        return normalized

    # 元素规则（含 ##/#@#/#?#/#$#/$$ 等分隔符）不解析 $options，
    # 其中的 $ 属于规则内容（如 #$# 样式注入、选择器属性值），不是选项分隔符
    is_element_rule = any(sep in normalized for sep in _ELEMENT_SEPS)

    # 分离 $options 部分（第一个 $ 之后为选项区）
    pattern = normalized
    options_part = ""
    if "$" in normalized and not is_element_rule:
        pattern, _, options_part = normalized.partition("$")

    # 大小写处理：match-case 选项要求区分大小写，匹配部分保留原样
    option_keys = {p.split("=")[0].strip() for p in options_part.split(",") if p.strip()}
    match_case = "match-case" in option_keys
    if not match_case:
        pattern = pattern.lower()
    # 选项名本身大小写不敏感，统一小写以消除差异
    options_part = options_part.lower()

    # 折叠连续空白
    pattern = re.sub(r'\s+', ' ', pattern)

    # 去除 www. 前缀（在 || 引出的域名模式中）
    pattern = re.sub(r'([^a-z0-9])www\.', r'\1', pattern)

    # 多站点元素规则: 分隔符前的域名列表排序（域名顺序不影响语义）
    # 如 example.com,foo.org##.x 与 foo.org,example.com##.x 视为同一规则
    for sep in _ELEMENT_SEPS:
        if sep in pattern:
            prefix, _, selector = pattern.partition(sep)
            if "," in prefix:
                domains = sorted(d.strip() for d in prefix.split(",") if d.strip())
                pattern = ",".join(domains) + sep + selector
            break

    # 将 $domain= 后的参数排序（确保参数顺序不影响语义）
    def sort_domain_options(match):
        """对 $domain= 选项进行排序"""
        prefix = match.group(1)
        domains = match.group(2)
        parts = sorted([d.strip() for d in domains.split("|")])
        return prefix + "|".join(parts)

    if options_part:
        options_part = re.sub(
            r'(domain=)([^,$]+)',
            sort_domain_options,
            options_part,
        )

    return pattern + ("$" + options_part if options_part else "")
