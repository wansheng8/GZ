"""选项别名归一化。

把 AdGuard / uBlock Origin 明确定义为同义的旧选项名折叠为规范名，使「同一规则
的不同别名写法」在去重时合并。仅处理语义等价的别名（含 ``frame`` -> ``subdocument``）；
语义可能不同的旧修饰符（``popup`` / ``other`` / ``websocket`` / ``app`` / ``csp`` /
``genericblock``）保持原样。

默认关闭，由 ``build --alias-normalize`` 开启。关闭时产物与开启前逐字节一致。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from .rules import Rule, _normalize, _option_start, _split_options, parse_options

# 别名 -> 规范名。键为小写选项名（不带前导 ~）。
OPTION_ALIASES: dict[str, str] = {
    "xmlhttprequest": "xhr",
    "doc": "document",
    "frame": "subdocument",
    "ghide": "generichide",
    # uBO 的 elemhide（关闭全部外观过滤）与 generichide（仅关闭通用外观过滤）
    # 语义不同，不能互相折叠；ehide 只是 elemhide 的别名。
    "ehide": "elemhide",
    "shide": "specifichide",
    "css": "stylesheet",
    # uBO 短名与 AdGuard 长名同义
    "strict-first-party": "strict1p",
    "strict-third-party": "strict3p",
}


@dataclass
class AliasReport:
    """别名归一化结果：改写条数、折叠条数、各别名命中次数。"""

    normalized: int = 0
    collapsed: int = 0
    by_alias: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "normalized": self.normalized,
            "collapsed": self.collapsed,
            "by_alias": dict(sorted(self.by_alias.items())),
        }


def _canonical_option(part: str) -> str:
    """把单个选项片段中的别名替换为规范名，保留取值与取反前缀。"""
    body = part
    negated = body.startswith("~")
    if negated:
        body = body[1:]
    if "=" in body:
        name, value = body.split("=", 1)
        stripped = name.strip()
        canonical = OPTION_ALIASES.get(stripped.lower(), stripped)
        return f"{'~' if negated else ''}{canonical}={value}"
    stripped = body.strip()
    canonical = OPTION_ALIASES.get(stripped.lower(), stripped)
    return f"{'~' if negated else ''}{canonical}"


def _canonicalize(rule: Rule, report: AliasReport) -> Rule:
    """改写单条规则的 raw / norm / options；无别名时原样返回。"""
    # 选项别名只适用于网络规则；元素/脚本规则里的 `$` 属于选择器或脚本参数，
    # 若按选项改写会把脚本实参（如 `$frame` / `$doc`）替换成别名，破坏规则。
    if rule.kind != "network":
        return rule
    idx = _option_start(rule.raw)
    if idx is None:
        return rule
    parts = _split_options(rule.raw[idx + 1 :])
    canonical = [_canonical_option(p) for p in parts]
    if canonical == parts:
        return rule
    for before, after in zip(parts, canonical):
        if before != after:
            name = before.lstrip("~").split("=", 1)[0].strip().lower()
            report.by_alias[name] = report.by_alias.get(name, 0) + 1
    report.normalized += 1
    option_text = ",".join(canonical)
    raw = rule.raw[:idx] + "$" + option_text
    return replace(
        rule,
        raw=raw,
        norm=_normalize(raw),
        options=parse_options(option_text),
    )


def normalize_aliases(rules: Iterable[Rule]) -> tuple[list[Rule], AliasReport]:
    """归一化选项别名并按规范键折叠重复规则，合并跨源来源。

    返回 ``(规则列表, 报告)``。该函数幂等：对已归一化的规则再次执行结果不变。
    """
    report = AliasReport()
    seen: dict[str, Rule] = {}
    out: list[Rule] = []
    for original in rules:
        rule = _canonicalize(original, report)
        if rule.norm in seen:
            kept = seen[rule.norm]
            if rule.source and rule.source not in kept.sources:
                kept.sources.append(rule.source)
            report.collapsed += 1
            continue
        seen[rule.norm] = rule
        out.append(rule)
    return out, report
