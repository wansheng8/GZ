"""生成多种格式的过滤器输出文件。

目标格式：
- adblock : 标准 Adblock Plus / uBlock Origin / AdGuard 语法
- hosts   : 0.0.0.0 域名 形式，供 Pi-hole / dnsmasq 使用
- domains : 每行一个域名，供 AdGuard Home / AdGuard DNS 使用
- stats   : 人类可读分类统计
- stats_json : 机器可读统计
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .rules import Rule

HOMEPAGE = "https://github.com/wansheng8/GZ"


def _to_hosts_line(rule: Rule) -> str | None:
    """将纯域名网络规则转换为 hosts 行，无法转换返回 None。"""
    if rule.kind == "network" and rule.domains and len(rule.domains) == 1 and not rule.is_exception:
        return f"0.0.0.0 {rule.domains[0]}"
    return None


def _to_hosts_ipv6_line(rule: Rule) -> str | None:
    if rule.kind == "network" and rule.domains and len(rule.domains) == 1 and not rule.is_exception:
        return f":: {rule.domains[0]}"
    return None


def _to_domain(rule: Rule) -> str | None:
    if rule.kind == "network" and rule.domains and len(rule.domains) == 1 and not rule.is_exception:
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
        fh.write("! ------------------------------------------\n")
        for r in rules:
            fh.write(r.raw + "\n")
            count += 1
    return count


def write_hosts(rules: Iterable[Rule], path: Path, title: str) -> int:
    domains: set[str] = set()
    for r in rules:
        line = _to_hosts_line(r)
        if line:
            domains.add(line)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write("# Format: hosts (0.0.0.0 domain)\n")
        for line in sorted(domains):
            fh.write(line + "\n")
    return len(domains)


def write_hosts_ipv6(rules: Iterable[Rule], path: Path, title: str) -> int:
    domains: set[str] = set()
    for r in rules:
        line = _to_hosts_ipv6_line(r)
        if line:
            domains.add(line)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write("# Format: hosts (:: domain, IPv6 NXDOMAIN)\n")
        for line in sorted(domains):
            fh.write(line + "\n")
    return len(domains)


def write_domains(rules: Iterable[Rule], path: Path, title: str) -> int:
    domains: set[str] = set()
    for r in rules:
        d = _to_domain(r)
        if d:
            domains.add(d)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write("# Format: one domain per line (AdGuard DNS / AdGuard Home)\n")
        for d in sorted(domains):
            fh.write(d + "\n")
    return len(domains)


def write_summary(stats: dict[str, int], output_dir: Path, name: str) -> None:
    path = output_dir / f"{name}.stats.txt"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {name} 规则分类统计\n")
        total = sum(stats.values())
        fh.write(f"# 总规则数: {total}\n")
        for cat, cnt in stats.items():
            fh.write(f"{cat}: {cnt}\n")


def write_summary_json(category_counts: dict[str, int], kind_counts: dict[str, int],
                       output_dir: Path, name: str, total: int) -> None:
    path = output_dir / f"{name}.stats.json"
    payload = {
        "name": name,
        "total": total,
        "by_category": category_counts,
        "by_kind": kind_counts,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
