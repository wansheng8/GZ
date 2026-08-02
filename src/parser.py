"""解析器模块 - 解析 adblock 语法规则，分类为结构化 Rule 对象"""

import re
from dataclasses import dataclass

from src.config import SourceConfig


@dataclass
class Rule:
    """单条广告过滤规则"""
    raw: str          # 原始规则文本
    normalized: str   # 标准化后的规则文本（用于去重比较）
    rule_type: str    # "block" | "exception" | "hide" | "header"
    domain: str       # 规则匹配的域名部分
    source: str       # 来源名称
    priority: int     # 来源优先级


# 匹配以 ! 开头的注释行
METADATA_PATTERN = re.compile(r'^!')

# 匹配 [Adblock Plus x.x] 等元数据块标记
ADGUARD_META_PATTERN = re.compile(r'^\[.*\]$')

# 匹配例外规则 @@
EXCEPTION_PATTERN = re.compile(r'^@@')

# 匹配元素隐藏规则 ##
HIDE_PATTERN = re.compile(r'##')

# 匹配域名模式的规则 ||domain^
DOMAIN_PATTERN = re.compile(r'\|\|([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*)')

# 匹配 hosts 格式的规则 127.0.0.1 domain 或 0.0.0.0 domain
HOSTS_PATTERN = re.compile(r'^(?:127\.0\.0\.1|0\.0\.0\.0)\s+(.+)')


def is_metadata_line(line: str) -> bool:
    """判断是否为元数据/注释行"""
    stripped = line.strip()
    if not stripped:
        return True
    if METADATA_PATTERN.match(stripped):
        return True
    if ADGUARD_META_PATTERN.match(stripped):
        return True
    return False


def classify_rule(line: str) -> str:
    """分类规则类型

    Returns:
        "exception" | "hide" | "block"
    """
    stripped = line.strip()
    if EXCEPTION_PATTERN.match(stripped):
        return "exception"
    if "##" in stripped:
        return "hide"
    return "block"


def extract_domain(rule_text: str) -> str:
    """从规则中提取域名

    Args:
        rule_text: 规则文本

    Returns:
        提取的域名字符串，若无法提取则返回空字符串
    """
    # 先尝试匹配 ||domain^ 模式
    match = DOMAIN_PATTERN.search(rule_text)
    if match:
        return match.group(1).lower()

    # 尝试匹配 hosts 格式
    match = HOSTS_PATTERN.match(rule_text.strip())
    if match:
        return match.group(1).strip().lower()

    # 尝试从 URL 模式中提取域名
    # 简单模式: 移除协议、端口和路径
    cleaned = rule_text.strip()
    # 移除 @@ 前缀（例外规则）
    if cleaned.startswith("@@||"):
        cleaned = cleaned[4:]
    elif cleaned.startswith("@@"):
        cleaned = cleaned[2:]
    if cleaned.startswith("||"):
        cleaned = cleaned[2:]

    # 匹配可能包含通配符的域名模式
    domain_match = re.match(
        r'([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+)',
        cleaned,
    )
    if domain_match:
        return domain_match.group(1).lower()

    return ""


def parse_rules(raw_content: str, source: SourceConfig) -> list[Rule]:
    """解析原始规则文本，转换为 Rule 对象列表

    Args:
        raw_content: 从上游下载的原始规则文本
        source: 来源配置

    Returns:
        Rule 对象列表
    """
    rules: list[Rule] = []
    skipped = 0

    for line in raw_content.splitlines():
        stripped = line.strip()

        # 跳过元数据和空行
        if is_metadata_line(stripped):
            # 保留重要的元数据行作为 header 类型规则
            if stripped.startswith("! Title:") or stripped.startswith("! Expires:"):
                rules.append(Rule(
                    raw=stripped,
                    normalized=stripped.lower(),
                    rule_type="header",
                    domain="",
                    source=source.name,
                    priority=source.priority,
                ))
            continue

        # 跳过 hosts 格式的行 (127.0.0.1 / 0.0.0.0)
        if HOSTS_PATTERN.match(stripped):
            # 将 hosts 格式转换为 adblock 格式: ||domain^
            host_match = HOSTS_PATTERN.match(stripped)
            if host_match:
                domain = host_match.group(1).strip()
                converted = f"||{domain}^"
                rules.append(Rule(
                    raw=converted,
                    normalized=converted.lower(),
                    rule_type="block",
                    domain=domain.lower(),
                    source=source.name,
                    priority=source.priority,
                ))
            continue

        # 分类规则
        rule_type = classify_rule(stripped)
        domain = extract_domain(stripped)

        rules.append(Rule(
            raw=stripped,
            normalized=stripped.lower().strip(),
            rule_type=rule_type,
            domain=domain,
            source=source.name,
            priority=source.priority,
        ))

    return rules
