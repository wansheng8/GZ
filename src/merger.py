"""合并去重模块 - 合并多条规则并执行精确去重和子集去重"""

import logging
from collections import defaultdict

from src.parser import Rule, RULE_HEADER, RULE_BLOCK, RULE_EXCEPTION, HIDE_TYPES

logger = logging.getLogger(__name__)


class RuleMerger:
    """规则合并器，支持精确去重和子集去重"""

    def __init__(self) -> None:
        # 按源的规则列表
        self._source_rules: dict[str, list[Rule]] = defaultdict(list)
        # 所有源的优先级信息
        self._source_priorities: dict[str, int] = {}

    def add_source(self, rules: list[Rule]) -> None:
        """添加一个源的规则

        Args:
            rules: 规则列表
        """
        if not rules:
            return
        source_name = rules[0].source
        self._source_rules[source_name].extend(rules)
        self._source_priorities[source_name] = rules[0].priority

    def merge(self) -> list[Rule]:
        """执行合并和去重

        流程:
        1. 按 priority 升序排列所有规则（priority 小的先处理，优先保留）
        2. 精确去重：相同 normalized 文本只保留首次出现的
        3. 子集去重：检测是否存在更宽泛的规则覆盖当前规则

        输出顺序:
        header 元数据 → 网络例外 @@ → 网络拦截 → 元素类规则（隐藏例外在前）

        Returns:
            去重后的规则列表
        """
        # 收集所有规则并按 priority 排序
        all_rules: list[Rule] = []
        for rules in self._source_rules.values():
            all_rules.extend(rules)

        # 按 priority 升序排列（数值越小优先级越高，先处理先保留）
        all_rules.sort(key=lambda r: r.priority)

        # 分组：header / 网络例外 / 网络拦截 / 元素类规则
        headers: list[Rule] = []
        exceptions: list[Rule] = []
        blocks: list[Rule] = []
        hide_group: list[Rule] = []

        for rule in all_rules:
            if rule.rule_type == RULE_HEADER:
                headers.append(rule)
            elif rule.rule_type == RULE_EXCEPTION:
                exceptions.append(rule)
            elif rule.rule_type == RULE_BLOCK:
                blocks.append(rule)
            else:
                # 元素类规则（hide / hide-exception / css-ext / scriptlet / html）
                hide_group.append(rule)

        # Step 1: 精确去重
        headers = _deduplicate_exact(headers)
        exceptions = _deduplicate_exact(exceptions)
        blocks = _deduplicate_exact(blocks)
        hide_group = _deduplicate_exact(hide_group)

        # Step 2: 子集去重（仅对网络拦截规则）
        blocks = _deduplicate_subset(blocks)

        # Step 3: 元素类规则内部分组，隐藏例外优先输出
        hide_exceptions = [r for r in hide_group if r.rule_type == "hide-exception"]
        rest_hide = [r for r in hide_group if r.rule_type != "hide-exception"]

        logger.info(
            "Merge result: %d header + %d exception + %d block + %d hide = %d total",
            len(headers),
            len(exceptions),
            len(blocks),
            len(hide_group),
            len(headers) + len(exceptions) + len(blocks) + len(hide_group),
        )

        # 合并: header 元数据在前，网络例外其次，随后是拦截规则和元素类规则
        return headers + exceptions + blocks + hide_exceptions + rest_hide


def _deduplicate_exact(rules: list[Rule]) -> list[Rule]:
    """精确去重：相同 normalized 文本只保留首次出现的（已按 priority 排序）

    Args:
        rules: 已按 priority 排序的规则列表

    Returns:
        去重后的规则列表
    """
    seen: set[str] = set()
    result: list[Rule] = []

    for rule in rules:
        if rule.normalized not in seen:
            seen.add(rule.normalized)
            result.append(rule)

    if len(rules) > 0:
        removed = len(rules) - len(result)
        logger.info("Exact dedup removed %d duplicate rules", removed)

    return result


def _deduplicate_subset(rules: list[Rule]) -> list[Rule]:
    """子集去重：检测并移除被更宽泛规则覆盖的冗余规则

    策略:
    - 建立域名索引，对每个域名查找是否存在父域名规则
    - 如果规则 A 覆盖规则 B（如 ||example.com^ 覆盖 ||ads.example.com^），移除 B
    - 子集检测保留高优先级源中的宽泛规则

    Args:
        rules: 已精确去重的规则列表（按 priority 排序）

    Returns:
        子集去重后的规则列表
    """
    # 构建域名到规则索引的映射
    domain_index: dict[str, list[tuple[int, Rule]]] = defaultdict(list)
    for idx, rule in enumerate(rules):
        if rule.domain:
            domain_index[rule.domain].append((idx, rule))

    # 标记需要移除的规则索引
    to_remove: set[int] = set()

    for idx, rule in enumerate(rules):
        if idx in to_remove:
            continue
        if not rule.domain:
            continue

        # 检查是否存在父域名规则覆盖当前规则
        domain = rule.domain
        parts = domain.split(".")

        # 对每个可能的父域名进行检查
        for i in range(1, len(parts)):
            parent_domain = ".".join(parts[i:])

            if parent_domain in domain_index:
                for parent_idx, parent_rule in domain_index[parent_domain]:
                    if parent_idx == idx:
                        continue
                    # 判断父规则是否更宽泛:
                    # 父规则只匹配域名级别（以 ^ 结尾），当前规则是子域名
                    parent_norm = parent_rule.normalized
                    if _is_broader_rule(parent_norm, rule.normalized):
                        to_remove.add(idx)
                        break

            if idx in to_remove:
                break

    if to_remove:
        logger.info("Subset dedup removed %d redundant rules", len(to_remove))

    return [rule for idx, rule in enumerate(rules) if idx not in to_remove]


def _is_broader_rule(parent: str, child: str) -> bool:
    """判断父规则是否比子规则更宽泛（父规则覆盖子规则的场景）

    Args:
        parent: 父规则的 normalized 文本
        child: 子规则的 normalized 文本

    Returns:
        如果父规则覆盖子规则则返回 True
    """
    if parent == child:
        return False

    # 去掉 @@ 前缀
    parent_clean = parent.lstrip("@")
    child_clean = child.lstrip("@")

    # 提取父规则的域名
    p_domain = _extract_domain_from_rule(parent_clean)
    c_domain = _extract_domain_from_rule(child_clean)

    if not p_domain or not c_domain:
        return False

    # 子域名是父域名的子集（如 ads.example.com 是 example.com 的子域名）
    if c_domain.endswith("." + p_domain):
        return True

    # 检查路径覆盖: parent=||example.com^, child=||example.com/path^
    if "||" in parent_clean and "||" in child_clean:
        parent_body = parent_clean[2:]  # Remove ||
        child_body = child_clean[2:]    # Remove ||

        # 父规则以 ^ 结尾（域名级别通配）
        p_caret = parent_body.find("^")
        if p_caret >= 0:
            parent_prefix = parent_body[:p_caret]
            # 子规则以相同域名开头但有额外路径
            if child_body.startswith(parent_prefix + "/"):
                return True

    return False


def _extract_domain_from_rule(rule_text: str) -> str:
    """从规则文本中提取域名，去除 ||、^ 等修饰符"""
    import re
    # 匹配 ||domain^ 或 domain 模式
    match = re.match(r'\|*([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+)', rule_text)
    if match:
        return match.group(1).lower()
    return ""
