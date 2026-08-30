"""Adblock Rule Collection 命令行入口。

子命令：
    build     下载上游列表、合并、去重并生成多种格式过滤器
    stats     仅基于已有输出目录重新生成统计（离线）
    sources   列出当前配置中的上游列表

用法示例：
    python -m adblock_collection build
    python -m adblock_collection build --out dist --no-cache --offline
    python -m adblock_collection build --no-lite --no-dns
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .merge import (
    apply_badfilter,
    category_stats,
    collect,
    dedupe,
    kind_stats,
    load_sources,
    remove_redundant_domains,
    source_stats,
    split_lite,
)
from .writer import (
    write_adblock,
    write_domains,
    write_hosts,
    write_hosts_ipv6,
    write_summary,
    write_summary_json,
)

LOG = logging.getLogger("adblock_collection")

DEFAULT_HEADERS = {
    "full": ("Adblock Rule Collection (Full)", "完整版广告拦截与 DNS 过滤规则集合，含大量上游列表，可能有误杀。"),
    "lite": ("Adblock Rule Collection (Lite)", "精简版，仅含 AdGuard 官方列表，误杀风险低，推荐日常使用。"),
}


def _emit(rules, output_dir, prefix, title, desc, gen_dns, source_counts):
    results = {}
    ap = output_dir / f"{prefix}.txt"
    n = write_adblock(rules, ap, title, desc)
    results["adblock"] = (ap, n)
    write_summary(category_stats(rules), output_dir, prefix)
    write_summary_json(category_stats(rules), kind_stats(rules), output_dir, prefix, len(rules), source_counts)
    if gen_dns:
        hp = output_dir / f"{prefix}_dns.txt"
        nh = write_hosts(rules, hp, title)
        results["hosts"] = (hp, nh)
        ipv6p = output_dir / f"{prefix}_dns_ipv6.txt"
        n6 = write_hosts_ipv6(rules, ipv6p, title)
        results["hosts_ipv6"] = (ipv6p, n6)
        dp = output_dir / f"{prefix}_domains.txt"
        nd = write_domains(rules, dp, title)
        results["domains"] = (dp, nd)
    return results


def build(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        LOG.error("配置文件不存在: %s", config_path)
        return 1

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    sources_meta = load_sources(config_path)
    collected = collect(config_path, use_cache=not args.no_cache, offline=args.offline)

    all_rules: list = []
    for _name, rules in collected.get("all", []):
        all_rules.extend(rules)

    src_counts = source_stats(all_rules)
    for name, cnt in src_counts.items():
        LOG.info("上游贡献规则: %-35s %d", name, cnt)

    LOG.info("原始规则总数: %d", len(all_rules))
    deduped = dedupe(all_rules)
    LOG.info("去重后规则总数: %d", len(deduped))
    deduped = apply_badfilter(deduped)
    if args.redundant:
        deduped = remove_redundant_domains(deduped)

    full_title, full_desc = DEFAULT_HEADERS["full"]
    full_results = _emit(deduped, output_dir, "adblock_collection_full", full_title, full_desc,
                         gen_dns=not args.no_dns, source_counts=src_counts)

    lite_rules: list = []
    if not args.no_lite:
        lite_rules = dedupe(split_lite(all_rules, sources_meta))
        lite_rules = apply_badfilter(lite_rules)
        if args.redundant:
            lite_rules = remove_redundant_domains(lite_rules)
        lite_title, lite_desc = DEFAULT_HEADERS["lite"]
        lite_results = _emit(lite_rules, output_dir, "adblock_collection_lite", lite_title, lite_desc,
                             gen_dns=not args.no_dns, source_counts=None)
    else:
        lite_results = {}

    LOG.info("生成完成:")
    for label, res in (("完整版", full_results), ("精简版", lite_results)):
        if not res:
            continue
        for fmt, (path, cnt) in res.items():
            LOG.info("  %s %s: %s (%d)", label, fmt, path, cnt)
    return 0


def sources_cmd(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        LOG.error("配置文件不存在: %s", config_path)
        return 1
    for src in load_sources(config_path):
        lite = "lite" if src.get("lite") else "full"
        print(f"{src.get('name', '?'):<35} {lite:<5} {src.get('category', 'other'):<12} {src.get('url', '')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="adblock-rule-collection",
        description="合并、去重、生成 Adblock / DNS 过滤器规则",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="下载上游列表并生成过滤器")
    p_build.add_argument("--config", default="config/sources.yaml", help="上游列表配置文件")
    p_build.add_argument("--out", default="dist", help="输出目录")
    p_build.add_argument("--no-cache", action="store_true", help="禁用下载缓存")
    p_build.add_argument("--offline", action="store_true", help="离线模式，仅使用缓存")
    p_build.add_argument("--no-lite", action="store_true", help="不生成精简版")
    p_build.add_argument("--no-dns", action="store_true", help="不生成 DNS/hosts/domains 文件")
    p_build.add_argument("--redundant", action="store_true", help="启用冗余域名规则消除")
    p_build.set_defaults(func=build)

    p_sources = sub.add_parser("sources", help="列出配置中的上游列表")
    p_sources.add_argument("--config", default="config/sources.yaml")
    p_sources.set_defaults(func=sources_cmd)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
