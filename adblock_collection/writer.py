"""生成多种格式的过滤器输出文件。

目标格式：
- adblock : 标准 Adblock Plus / uBlock Origin / AdGuard 语法
- hosts   : 0.0.0.0 域名 形式，供 Pi-hole / dnsmasq 使用
- hosts_ipv6 : :: 域名 形式，供 IPv6 环境 NXDOMAIN 使用
- domains : 每行一个域名，供 AdGuard Home / AdGuard DNS 使用
- stats   : 人类可读分类统计
- stats_json : 机器可读统计
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from .dns_policy import (
    DNS_REJECT,
    SCOPED_MODIFIERS,
    classify_dns,
    is_dns_eligible,
    resolve_policy,
)
from .rules import _PURE_DOMAIN_RE, Rule, _option_start

HOMEPAGE = "https://github.com/wansheng8/GZ"


def _to_hosts_line(rule: Rule, policy: dict | None = None) -> str | None:
    """将可进 DNS 的纯域名网络阻断规则转换为 hosts 行，无法转换返回 None。

    仅接受无路径的纯域名规则（如 ||a.com^），避免把 ||a.com/ads^ 误扩成整域拦截。
    是否接受带修饰符的单域名规则由 dns_policy 决定。
    """
    if not _dns_eligible(rule, policy):
        return None
    return f"0.0.0.0 {rule.domains[0]}"


def _to_hosts_ipv6_line(rule: Rule, policy: dict | None = None) -> str | None:
    if not _dns_eligible(rule, policy):
        return None
    return f":: {rule.domains[0]}"


def _to_domain(rule: Rule, policy: dict | None = None) -> str | None:
    if not _dns_eligible(rule, policy):
        return None
    if "/" not in rule.domains[0]:
        return rule.domains[0]
    return None


def _dns_eligible(rule: Rule, policy: dict | None) -> bool:
    if not (
        rule.kind == "network"
        and rule.domains
        and len(rule.domains) == 1
        and not rule.is_exception
    ):
        return False
    if not _PURE_DOMAIN_RE.search(rule.raw) and not rule.options:
        return False
    from .dns_policy import is_dns_eligible

    return is_dns_eligible(rule, policy)


def write_adblock(rules: Iterable[Rule], path: Path, title: str, desc: str) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"! Title: {title}\n")
        fh.write(f"! Description: {desc}\n")
        fh.write("! Expires: 1 day\n")
        fh.write(f"! Homepage: {HOMEPAGE}\n")
        fh.write("! License: MIT\n")
        fh.write(f"! Total Rules: {len(list(rules))}\n")
        fh.write("! ------------------------------------------\n")
        for r in rules:
            fh.write(r.raw + "\n")
            count += 1
    return count


def _is_global_domain_exception(rule: Rule) -> bool:
    """单域名例外是否「整域且全局」放行，可用于在 DNS 层抵消同名整域阻断。

    仅当例外同时满足：

    - 网络规则、单域名，且模式为纯域名（``@@||a.com^`` / ``@@||a.com``，无路径/通配）；
    - 不含作用域修饰符（``$domain`` / ``$from`` / ``$to`` / ``$denyallow`` /
      ``$ipaddress`` / ``$method``）。

    这样 ``@@||a.com^$domain=x.com`` 这类站点作用域例外、以及 ``@@||a.com^*/path``
    这类路径例外都不会把 a.com 从整域阻断集合中移除，避免「某站点的局部放行导致整个
    广告域名在全球范围被放行」。
    """
    if not (rule.kind == "network" and rule.is_exception and len(rule.domains) == 1):
        return False
    if set(rule.options) & SCOPED_MODIFIERS:
        return False
    idx = _option_start(rule.raw)
    pattern = rule.raw if idx is None else rule.raw[:idx]
    return bool(_PURE_DOMAIN_RE.search(pattern))


def _blocked_domains(rules: Iterable[Rule], policy: dict | None = None) -> set[str]:
    """从规则集提取「应拦截的纯域名」集合，并抵消整域全局例外放行的域名。

    仅统计满足 dns_policy 安全分级的单域名网络阻断规则（||a.com^ 或策略允许的修饰符规则），
    同时收集 @@||a.com^ / @@||a.com 这类**整域全局**例外，从拦截集中剔除，使 DNS/Hosts 版
    也尊重精确放行；作用域/路径例外（$domain=、含路径）不影响整域阻断判定。
    """
    blocked: set[str] = set()
    exceptions: set[str] = set()
    for r in rules:
        if r.kind != "network" or not r.domains or len(r.domains) != 1:
            continue
        if r.is_exception:
            # 仅整域全局例外参与放行；作用域/路径例外无法在 DNS 层表达，不抵消整域阻断
            if _is_global_domain_exception(r):
                exceptions.add(r.domains[0])
            continue
        if not is_dns_eligible(r, policy):
            continue
        blocked.add(r.domains[0])
    blocked -= exceptions
    return blocked


def write_hosts(
    rules: Iterable[Rule], path: Path, title: str, policy: dict | None = None
) -> int:
    domains = _blocked_domains(rules, policy)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write(f"# Format: hosts (0.0.0.0 domain), total {len(domains)}\n")
        for line in sorted(domains):
            fh.write(f"0.0.0.0 {line}\n")
    return len(domains)


def write_hosts_ipv6(
    rules: Iterable[Rule], path: Path, title: str, policy: dict | None = None
) -> int:
    domains = _blocked_domains(rules, policy)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write(f"# Format: hosts (:: domain, IPv6 NXDOMAIN), total {len(domains)}\n")
        for line in sorted(domains):
            fh.write(f":: {line}\n")
    return len(domains)


def write_domains(
    rules: Iterable[Rule], path: Path, title: str, policy: dict | None = None
) -> int:
    domains = _blocked_domains(rules, policy)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write(
            f"# Format: one domain per line (AdGuard DNS / AdGuard Home), total {len(domains)}\n"
        )
        for d in sorted(domains):
            fh.write(d + "\n")
    return len(domains)


def write_manifest(entries: list[dict], output_dir: Path) -> None:
    """写入 dist/manifest.json，列出所有生成的输出文件，便于订阅者程序化读取。"""
    payload = {
        "generator": "adblock-rule-collection",
        "generated_files": entries,
    }
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_summary(stats: dict[str, int], output_dir: Path, name: str) -> None:
    path = output_dir / f"{name}.stats.txt"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {name} 规则分类统计\n")
        total = sum(stats.values())
        fh.write(f"# 总规则数: {total}\n")
        for cat, cnt in stats.items():
            fh.write(f"{cat}: {cnt}\n")


def write_summary_json(
    category_counts: dict[str, int],
    kind_counts: dict[str, int],
    output_dir: Path,
    name: str,
    total: int,
    source_counts: dict[str, int] | None = None,
) -> None:
    path = output_dir / f"{name}.stats.json"
    payload = {
        "name": name,
        "total": total,
        "by_category": category_counts,
        "by_kind": kind_counts,
    }
    if source_counts:
        payload["by_source"] = source_counts
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_dns_safety_report(
    rules: Iterable[Rule], output_dir: Path, name: str, policy: dict | None = None
) -> dict:
    """统计 DNS 安全分级分布，输出 *dns_safety.json 并返回汇总。

    对每条网络规则做 classify_dns 分级，区分 SAFE / CONDITIONAL / REJECT，
    以及被策略允许或拒绝的原因计数，便于审计 DNS 误杀风险。
    """
    policy = resolve_policy(policy)
    counts: dict[str, int] = defaultdict(int)
    reason_counts: dict[str, int] = defaultdict(int)
    eligible = 0
    rejected = 0
    for r in rules:
        verdict = classify_dns(r)
        counts[verdict.eligibility] += 1
        reason_counts[verdict.reason] += 1
        if verdict.eligibility == DNS_REJECT:
            rejected += 1
            continue
        if verdict.reason == "domain_modifier" and not policy.get(
            "allow_modifier", False
        ):
            rejected += 1
            continue
        if verdict.confidence >= policy.get("min_confidence", 0.0):
            eligible += 1
        else:
            rejected += 1

    summary = {
        "policy_level": policy.get("level", "all"),
        "min_confidence": policy.get("min_confidence", 0.0),
        "allow_modifier": policy.get("allow_modifier", False),
        "dns_eligible_network_rules": eligible,
        "dns_rejected_network_rules": rejected,
        "by_eligibility": dict(counts),
        "by_reason": dict(reason_counts),
    }
    path = output_dir / f"{name}.dns_safety.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
