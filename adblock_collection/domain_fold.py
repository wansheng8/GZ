"""域名层级折叠：父域整域拦截覆盖子域时折叠冗余规则。

与 ``merge.remove_redundant_domains`` 的旧行为兼容，并额外支持：

- 子域存在精确例外规则时保留该子域阻断规则（避免隐式改变放行意图）；
- 输出折叠前后的条数与被折叠域名清单，便于审计。

折叠只会用更宽的父域拦截替换更窄的子域拦截，拦截范围保持或扩大，不会造成漏拦。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .merge import _is_full_domain_block
from .rules import Rule


@dataclass
class DomainFoldReport:
    folded: int = 0
    domains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"folded": self.folded, "domains": self.domains}


def fold_domains(
    rules: Iterable[Rule], *, protect_exception_children: bool = True
) -> tuple[list[Rule], DomainFoldReport]:
    """折叠被祖先域整域拦截覆盖的子域规则。

    ``protect_exception_children`` 为 True 时，若子域自身存在精确例外规则，
    则保留该子域的阻断规则；为 False 时与旧版 ``remove_redundant_domains`` 等价。
    """
    rules = list(rules)

    # 每个域名的整域全量拦截代表（优先 $important）
    full_block: dict[str, Rule] = {}
    for rule in rules:
        if _is_full_domain_block(rule) and len(rule.domains) == 1:
            domain = rule.domains[0]
            prev = full_block.get(domain)
            if prev is None or (rule.is_important and not prev.is_important):
                full_block[domain] = rule

    protected: set[str] = set()
    if protect_exception_children:
        protected = {
            rule.domains[0]
            for rule in rules
            if rule.is_exception and rule.kind == "network" and len(rule.domains) == 1
        }

    kept: list[Rule] = []
    report = DomainFoldReport()
    folded_domains: set[str] = set()
    for rule in rules:
        if (
            rule.kind == "network"
            and not rule.is_exception
            and len(rule.domains) == 1
        ):
            domain = rule.domains[0]
            parts = domain.split(".")
            covered = any(
                ".".join(parts[i:]) in full_block for i in range(1, len(parts))
            )
            if covered:
                if domain in protected:
                    kept.append(rule)
                    continue
                report.folded += 1
                folded_domains.add(domain)
                continue
            if domain in full_block:
                if rule is full_block[domain]:
                    kept.append(rule)
                else:
                    report.folded += 1
                    folded_domains.add(domain)
                continue
        kept.append(rule)

    report.domains = sorted(folded_domains)
    return kept, report
