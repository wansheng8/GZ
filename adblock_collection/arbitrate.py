"""阻断与例外的确定性仲裁。

同一整域目标上同时出现「整域全局例外」与「整域阻断」时，按
「整域全局例外 > ``$important`` 整域阻断 > 普通整域阻断」产出唯一结果，避免
订阅端出现「先拦截再放行」的无效堆叠。

安全边界（与 ``writer._is_global_domain_exception`` 一致）：作用域例外
（``$domain`` / ``$from`` / ``$to`` / ``$denyallow`` / ``$ipaddress`` / ``$method``）
与路径例外无法在整域层面表达，本模块保持其原文输出，且不使用它们抵消整域阻断，
避免「某站点的局部放行导致广告域名在全球范围被放行」。

默认关闭，由 ``build --resolve-conflicts`` 开启。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from .rules import _PURE_DOMAIN_RE, Rule, _option_start
from .writer import _is_global_domain_exception

# 不改变整域拦截范围的选项集合：$important 只提升优先级。
_FULL_BLOCK_OPTIONS = frozenset({"important"})


def _is_custom_block(rule: Rule) -> bool:
    """是否为自定义黑名单中的单域名阻断规则（含带修饰符的阻断）。"""
    return (
        rule.source == "LocalBlocklist"
        and rule.kind == "network"
        and not rule.is_exception
        and len(rule.domains) == 1
    )


@dataclass
class ArbitrationRecord:
    """一条仲裁记录：目标、胜出规则、败出规则与依据。"""

    target: str
    winner: str
    losers: list[str]
    reason: str

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "winner": self.winner,
            "losers": self.losers,
            "reason": self.reason,
        }


def _pattern(raw: str) -> str:
    idx = _option_start(raw)
    return raw if idx is None else raw[:idx]


def _is_whole_domain_block(rule: Rule) -> bool:
    """是否为「拦截整域全部请求」的规则（无路径、无作用域、无其他修饰符）。"""
    if rule.kind != "network" or rule.is_exception or len(rule.domains) != 1:
        return False
    if set(rule.options) - _FULL_BLOCK_OPTIONS:
        return False
    return bool(_PURE_DOMAIN_RE.search(_pattern(rule.raw)))


def arbitrate(rules: Iterable[Rule]) -> tuple[list[Rule], list[ArbitrationRecord]]:
    """对整域目标做确定性仲裁，返回 ``(规则列表, 仲裁记录)``。

    被例外或更高优先级规则覆盖的规则从结果中移除；作用域/路径规则原样保留。
    """
    rules = list(rules)
    by_domain: dict[str, list[int]] = defaultdict(list)
    for i, rule in enumerate(rules):
        if rule.kind == "network" and len(rule.domains) == 1:
            by_domain[rule.domains[0]].append(i)

    dropped: set[int] = set()
    records: list[ArbitrationRecord] = []
    for domain in sorted(by_domain):
        indices = by_domain[domain]
        custom_exceptions = [
            i
            for i in indices
            if rules[i].source == "LocalAllowlist"
            and _is_global_domain_exception(rules[i])
        ]
        custom_blocks = [i for i in indices if _is_custom_block(rules[i])]
        exceptions = [i for i in indices if _is_global_domain_exception(rules[i])]
        important = [
            i
            for i in indices
            if _is_whole_domain_block(rules[i]) and rules[i].is_important
        ]
        normal = [
            i
            for i in indices
            if _is_whole_domain_block(rules[i]) and not rules[i].is_important
        ]
        if custom_exceptions:
            # 自定义白名单优先级最高：移除同域全部阻断（上游与自定义）
            losers = [
                i
                for i in indices
                if _is_whole_domain_block(rules[i]) or _is_custom_block(rules[i])
            ]
            dropped.update(losers)
            records.append(
                ArbitrationRecord(
                    target=domain,
                    winner=rules[custom_exceptions[0]].norm,
                    losers=[rules[i].norm for i in losers],
                    reason="自定义白名单优先于阻断",
                )
            )
        elif custom_blocks:
            # 自定义黑名单优先于上游：移除同域上游例外与上游整域阻断
            losers = [
                i
                for i in exceptions + important + normal
                if i not in custom_blocks
            ]
            dropped.update(losers)
            records.append(
                ArbitrationRecord(
                    target=domain,
                    winner=rules[custom_blocks[0]].norm,
                    losers=[rules[i].norm for i in losers],
                    reason="自定义黑名单优先于上游规则",
                )
            )
        elif exceptions and (important or normal):
            losers = important + normal
            dropped.update(losers)
            records.append(
                ArbitrationRecord(
                    target=domain,
                    winner=rules[exceptions[0]].norm,
                    losers=[rules[i].norm for i in losers],
                    reason="整域全局例外优先于整域阻断",
                )
            )
        elif important and normal:
            dropped.update(normal)
            records.append(
                ArbitrationRecord(
                    target=domain,
                    winner=rules[important[0]].norm,
                    losers=[rules[i].norm for i in normal],
                    reason="$important 阻断优先于普通阻断",
                )
            )

    kept = [rule for i, rule in enumerate(rules) if i not in dropped]
    return kept, records
