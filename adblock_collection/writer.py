"""生成多种格式的过滤器输出文件。

目标格式：
- adblock : 标准 Adblock Plus / uBlock Origin / AdGuard 语法
- hosts   : 0.0.0.0 域名 形式，供 Pi-hole / dnsmasq 使用
- hosts_ipv6 : :: 域名 形式，供 IPv6 环境 NXDOMAIN 使用
- domains : 每行一个域名，供 AdGuard Home / AdGuard DNS 使用
- domain_rules : 每行 ``||domain^``，DNS 等价的纯域名 adblock 清单（浏览器可导入）
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
    PARTY_MODIFIERS,
    RESOURCE_TYPE_MODIFIERS,
    SCOPED_MODIFIERS,
    classify_dns,
    is_dns_eligible,
    resolve_policy,
)
from .rules import _HOSTS_RESERVED, _PURE_DOMAIN_RE, Rule, _option_start

HOMEPAGE = "https://github.com/wansheng8/GZ"

# jsDelivr 对单个 gh 文件有 20MB 上限，超过会返回 403，订阅者将拿不到任何规则。
# 留出约 2MiB 安全余量：超过 18MiB 的 adblock 列表自动拆分为 !#include 主链。
JSDELIVR_MAX_BYTES = 18 * 1024 * 1024


def _adblock_header(title: str, desc: str, total: int) -> list[str]:
    """标准 adblock 列表头。

    首行 ``[Adblock Plus 2.0]`` 是 Adblock Plus 识别一个文件为过滤列表的前提；
    uBlock Origin / AdGuard 同样接受该头。缺少它时 ABP 会拒绝导入。
    """
    return [
        "[Adblock Plus 2.0]",
        f"! Title: {title}",
        f"! Description: {desc}",
        "! Expires: 1 day",
        f"! Homepage: {HOMEPAGE}",
        "! License: MIT",
        f"! Total Rules: {total}",
        "! ------------------------------------------",
    ]


def write_adblock(rules: Iterable[Rule], path: Path, title: str, desc: str) -> int:
    rules = list(rules)
    with path.open("w", encoding="utf-8") as fh:
        for line in _adblock_header(title, desc, len(rules)):
            fh.write(line + "\n")
        count = 0
        for r in rules:
            fh.write(r.raw + "\n")
            count += 1
    return count


def _write_adblock_part(
    output_dir: Path, prefix: str, part_no: int, lines: list[str], title: str
) -> tuple[str, int]:
    name = f"{prefix}_jsdelivr_part{part_no:02d}.txt"
    with (output_dir / name).open("w", encoding="utf-8") as fh:
        fh.write(f"! {title} (jsDelivr part {part_no:02d})\n")
        for line in lines:
            fh.write(line + "\n")
    return name, len(lines)


def write_adblock_split(
    rules: Iterable[Rule],
    output_dir: Path,
    prefix: str,
    title: str,
    desc: str,
    max_bytes: int = JSDELIVR_MAX_BYTES,
) -> tuple[str, list[str], int] | None:
    """把超出 jsDelivr 单文件上限的 adblock 列表拆成 ``!#include`` 主链。

    生成 ``{prefix}_jsdelivr.txt`` 主文件与 ``{prefix}_jsdelivr_partNN.txt`` 分片，
    每个分片都小于 ``max_bytes``。uBlock Origin / AdGuard 会递归跟随相对路径的
    ``!#include``，GitHub raw 与 jsDelivr 都能按相对路径取到分片，因此订阅方
    完全无感；规则内容不会因拆分丢失。

    返回 ``(主文件名, 分片文件名列表, 总规则数)``。规则为空时返回 ``None``。
    """
    rules = list(rules)
    if not rules:
        return None
    # 分片文件头的预留空间，保证分片本身也小于上限
    header_budget = 256
    parts: list[str] = []
    chunk: list[str] = []
    chunk_bytes = 0
    part_no = 0
    for r in rules:
        line_bytes = len(r.raw.encode("utf-8")) + 1
        if chunk and chunk_bytes + line_bytes > max_bytes - header_budget:
            part_no += 1
            name, _ = _write_adblock_part(output_dir, prefix, part_no, chunk, title)
            parts.append(name)
            chunk, chunk_bytes = [], 0
        chunk.append(r.raw)
        chunk_bytes += line_bytes
    if chunk:
        part_no += 1
        name, _ = _write_adblock_part(output_dir, prefix, part_no, chunk, title)
        parts.append(name)

    master_name = f"{prefix}_jsdelivr.txt"
    with (output_dir / master_name).open("w", encoding="utf-8") as fh:
        for line in _adblock_header(title, f"{desc}（jsDelivr 分片主链）", len(rules)):
            fh.write(line + "\n")
        for name in parts:
            fh.write(f"!#include {name}\n")
    return master_name, parts, len(rules)


def _is_global_domain_exception(rule: Rule) -> bool:
    """单域名例外是否「整域且全局」放行，可用于在 DNS 层抵消同名整域阻断。

    仅当例外同时满足：

    - 网络规则、单域名，且模式为纯域名（``@@||a.com^`` / ``@@||a.com``，无路径/通配）；
    - 不含作用域修饰符（``$domain`` / ``$from`` / ``$to`` / ``$denyallow`` /
      ``$ipaddress`` / ``$method``），也不含资源类型（``$script`` / ``$websocket`` …）
      与第一/第三方限定（``$third-party``）。

    这样 ``@@||a.com^$domain=x.com`` 这类站点作用域例外、``@@||a.com^$script`` 这类
    资源类型例外、以及 ``@@||a.com^*/path`` 这类路径例外都不会把 a.com 从整域阻断
    集合中移除，避免「某站点的局部放行导致整个广告域名在全球范围被放行」。
    """
    if not (rule.kind == "network" and rule.is_exception and len(rule.domains) == 1):
        return False
    if set(rule.options) & (SCOPED_MODIFIERS | RESOURCE_TYPE_MODIFIERS | PARTY_MODIFIERS):
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
        domain = r.domains[0]
        # 保留域名（localhost/local 等）不进入 DNS 产物：屏蔽它们会破坏本机解析，
        # 且 hosts 行解析时本就会剔除，写入后无法往返一致。
        if domain in _HOSTS_RESERVED:
            continue
        if r.is_exception:
            # 仅整域全局例外参与放行；作用域/路径例外无法在 DNS 层表达，不抵消整域阻断
            if _is_global_domain_exception(r):
                exceptions.add(domain)
            continue
        if not is_dns_eligible(r, policy):
            continue
        blocked.add(domain)
    blocked -= exceptions
    return blocked


def _global_exception_domains(rules: Iterable[Rule]) -> set[str]:
    """收集「整域全局例外」放行的域名，用于生成 DNS 白名单。"""
    return {
        r.domains[0]
        for r in rules
        if _is_global_domain_exception(r)
    }


def write_dns_allow(
    rules: Iterable[Rule], path: Path, title: str
) -> int:
    """生成 DNS 白名单：每行一个被整域全局例外放行的域名。

    供 AdGuard Home / Pi-hole 的「允许清单」分组直接导入。作用域/路径例外无法
    在 DNS 层表达，不在此列出。
    """
    domains = sorted(_global_exception_domains(rules))
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write(
            f"# Format: DNS allowlist (AdGuard Home / Pi-hole), total {len(domains)}\n"
        )
        for d in domains:
            fh.write(d + "\n")
    return len(domains)


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


def write_domain_rules(
    rules: Iterable[Rule],
    path: Path,
    title: str,
    desc: str,
    policy: dict | None = None,
) -> int:
    """生成「DNS 等价」纯域名 adblock 清单，每行 ``||domain^``。

    与 hosts/domains 同源（同一 _blocked_domains 集合），仅含整域阻断、无任何修饰符
    与元素隐藏规则。用途：不搭 DNS 的用户可用它把域名阻断层直接导入浏览器扩展；
    由于输出是纯 adblock 语法，也可作为 DNS 端「域名规则」形态导入 AdGuard Home。
    """
    domains = _blocked_domains(rules, policy)
    with path.open("w", encoding="utf-8") as fh:
        for line in _adblock_header(title, desc, len(domains)):
            fh.write(line + "\n")
        for d in sorted(domains):
            fh.write(f"||{d}^\n")
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
