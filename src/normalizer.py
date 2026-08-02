"""标准化模块 - 规则标准化，确保语义相同的规则归一化为同一形式"""

import re


def normalize_rule(rule_text: str) -> str:
    """标准化规则文本

    标准化步骤：
    1. 去除首尾空白
    2. 折叠连续空白为单个空格
    3. 统一大小写
    4. 去除 www. 域名前缀（规则匹配层面等价时）
    5. 移除查询参数中的无关差异

    Args:
        rule_text: 原始规则文本

    Returns:
        标准化后的规则文本
    """
    normalized = rule_text.strip()
    if not normalized:
        return normalized

    # 统一小写
    normalized = normalized.lower()

    # 折叠连续空白
    normalized = re.sub(r'\s+', ' ', normalized)

    # 去除 www. 前缀（在 || 引出的域名模式中）
    normalized = re.sub(r'\|([*])\|(www\.)', r'|*\1|', normalized)
    normalized = re.sub(r'([^a-z0-9])www\.', r'\1', normalized)

    # 将 $domain= 后的参数排序（确保参数顺序不影响语义）
    def sort_domain_options(match):
        """对 $domain= 选项进行排序"""
        prefix = match.group(1)
        domains = match.group(2)
        parts = sorted([d.strip() for d in domains.split("|")])
        return prefix + ",".join(parts)

    normalized = re.sub(
        r'(\$domain=)([^,$]+)',
        sort_domain_options,
        normalized,
    )

    return normalized
