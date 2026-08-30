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
from pathlib import Path
from typing import Iterable

from .rules import Rule, _PURE_DOMAIN_RE


HOMEPAGE = "https://github.com/wansheng8/GZ"


def _to_hosts_line(rule: Rule) -> str | None:
    """将纯域名网络阻断规则转换为 hosts 行，无法转换返回 None。

    仅接受无路径的纯域名规则（如 ||a.com^），避免把 ||a.com/ads^ 误扩成整域拦截。
    """
    if (
        rule.kind == "network"
        and rule.domains
        and len(rule.domains) == 1
        and not rule.is_exception
        and _PURE_DOMAIN_RE.match(rule.raw)
    ):
        return f"0.0.0.0 {rule.domains[0]}"
    return None


def _to_hosts_ipv6_line(rule: Rule) -> str | None:
    if (
        rule.kind == "network"
        and rule.domains
        and len(rule.domains) == 1
        and not rule.is_exception
        and _PURE_DOMAIN_RE.match(rule.raw)
    ):
        return f":: {rule.domains[0]}"
    return None


def _to_domain(rule: Rule) -> str | None:
    if (
        rule.kind == "network"
        and rule.domains
        and len(rule.domains) == 1
        and not rule.is_exception
        and _PURE_DOMAIN_RE.search(rule.raw)
    ):
        if "/" not in rule.domains[0]:
            return rule.domains[0]
    return None


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


def _blocked_domains(rules: Iterable[Rule]) -> set[str]:
    """从规则集提取「应拦截的纯域名」集合，并抵消例外规则放行的域名。

    仅统计无路径的纯域名网络阻断规则（||a.com^），同时收集 @@||a.com^ / @@||a.com
    这类单域名例外，从拦截集中剔除，使 DNS/Hosts 版也尊重精确放行。
    """
    blocked: set[str] = set()
    exceptions: set[str] = set()
    for r in rules:
        if r.kind != "network" or not r.domains or len(r.domains) != 1 or not _PURE_DOMAIN_RE.search(r.raw):
            continue
        if r.is_exception:
            exceptions.add(r.domains[0])
        else:
            blocked.add(r.domains[0])
    blocked -= exceptions
    return blocked


def write_hosts(rules: Iterable[Rule], path: Path, title: str) -> int:
    domains = _blocked_domains(rules)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write(f"# Format: hosts (0.0.0.0 domain), total {len(domains)}\n")
        for line in sorted(domains):
            fh.write(f"0.0.0.0 {line}\n")
    return len(domains)


def write_hosts_ipv6(rules: Iterable[Rule], path: Path, title: str) -> int:
    domains = _blocked_domains(rules)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write(f"# Format: hosts (:: domain, IPv6 NXDOMAIN), total {len(domains)}\n")
        for line in sorted(domains):
            fh.write(f":: {line}\n")
    return len(domains)


def write_domains(rules: Iterable[Rule], path: Path, title: str) -> int:
    domains = _blocked_domains(rules)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write(f"# Format: one domain per line (AdGuard DNS / AdGuard Home), total {len(domains)}\n")
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


def write_summary_json(category_counts: dict[str, int], kind_counts: dict[str, int],
                       output_dir: Path, name: str, total: int,
                       source_counts: dict[str, int] | None = None) -> None:
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
