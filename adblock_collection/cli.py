"""Adblock Rule Collection 命令行入口。

子命令：
    build     下载上游列表、合并、去重并生成多种格式过滤器
    sources   列出当前配置中的上游列表

用法示例：
    python -m adblock_collection build
    python -m adblock_collection build --out dist --no-cache --offline
     python -m adblock_collection build --no-dns
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
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
)
from .writer import (
    write_adblock,
    write_domains,
    write_hosts,
    write_hosts_ipv6,
    write_summary,
    write_summary_json,
    write_manifest,
)

LOG = logging.getLogger("adblock_collection")

DEFAULT_HEADERS = {
    "full": ("Adblock Rule Collection (Full)", "完整版广告拦截与 DNS 过滤规则集合，含大量上游列表，可能有误杀。"),
}


def _emit(rules, output_dir, prefix, title, desc, gen_dns, source_counts, manifest):
    rules = list(rules)
    results = {}
    ap = output_dir / f"{prefix}.txt"
    n = write_adblock(rules, ap, title, desc)
    results["adblock"] = (ap, n)
    manifest.append({"name": prefix, "file": f"{prefix}.txt", "format": "adblock", "rules": n})
    src_counts = source_stats(rules) if source_counts is None else source_counts
    write_summary(category_stats(rules), output_dir, prefix)
    write_summary_json(category_stats(rules), kind_stats(rules), output_dir, prefix, len(rules), src_counts)
    if gen_dns:
        hp = output_dir / f"{prefix}_dns.txt"
        nh = write_hosts(rules, hp, title)
        results["hosts"] = (hp, nh)
        manifest.append({"name": prefix, "file": f"{prefix}_dns.txt", "format": "hosts", "rules": nh})
        ipv6p = output_dir / f"{prefix}_dns_ipv6.txt"
        n6 = write_hosts_ipv6(rules, ipv6p, title)
        results["hosts_ipv6"] = (ipv6p, n6)
        manifest.append({"name": prefix, "file": f"{prefix}_dns_ipv6.txt", "format": "hosts_ipv6", "rules": n6})
        dp = output_dir / f"{prefix}_domains.txt"
        nd = write_domains(rules, dp, title)
        results["domains"] = (dp, nd)
        manifest.append({"name": prefix, "file": f"{prefix}_domains.txt", "format": "domains", "rules": nd})
    return results


def _emit_by_category(rules, output_dir, base_prefix, title_prefix, gen_dns, manifest):
    """按类别筛选全局去重后的规则集，分别生成子列表（不二次去重）。"""
    by_cat: dict[str, list] = {}
    for r in rules:
        by_cat.setdefault(r.category, []).append(r)
    for cat, cat_rules in sorted(by_cat.items()):
        prefix = f"{base_prefix}_{cat}"
        title = f"{title_prefix} ({cat})"
        desc = f"按类型拆分：{cat}"
        _emit(cat_rules, output_dir, prefix, title, desc, gen_dns, source_counts=None, manifest=manifest)


def build(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        LOG.error("配置文件不存在: %s", config_path)
        return 1

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    sources_meta = load_sources(config_path)
    collected = collect(config_path, use_cache=not args.no_cache, offline=args.offline)
    failed_sources = collected.get("_failed", [])

    all_rules: list = []
    for _name, rules in collected.get("all", []):
        all_rules.extend(rules)

    src_counts = source_stats(all_rules)
    for name, cnt in src_counts.items():
        LOG.info("上游贡献规则: %-35s %d", name, cnt)
    if failed_sources:
        LOG.warning("本次下载失败的源 (%d): %s", len(failed_sources), ", ".join(failed_sources))

    LOG.info("原始规则总数: %d", len(all_rules))
    deduped = dedupe(all_rules)
    LOG.info("去重后规则总数: %d", len(deduped))
    deduped = apply_badfilter(deduped)
    if args.redundant:
        deduped = remove_redundant_domains(deduped)

    full_title, full_desc = DEFAULT_HEADERS["full"]
    manifest: list = []
    full_results = _emit(deduped, output_dir, "adblock_collection_full", full_title, full_desc,
                         gen_dns=not args.no_dns, source_counts=src_counts, manifest=manifest)
    if args.split_by_category:
        _emit_by_category(deduped, output_dir, "adblock_collection_full", full_title, gen_dns=not args.no_dns, manifest=manifest)
        # 不变量校验：按类别拆分的子列表并集必须等于完整版
        cat_total = sum(
            r["rules"] for r in manifest
            if r["name"].startswith("adblock_collection_full_")
            and not any(r["file"].endswith(s) for s in ("_dns.txt", "_domains.txt", "_dns_ipv6.txt"))
            and r["file"] != "adblock_collection_full.txt"
        )
        full_n = next(r["rules"] for r in manifest if r["file"] == "adblock_collection_full.txt")
        if cat_total != full_n:
            LOG.error("类别拆分不变量被破坏: 子列表总和 %d != 完整版 %d", cat_total, full_n)

    # 写入上游健康报告（供订阅者判断数据完整性）
    status_path = output_dir / "sources_status.json"
    status_path.write_text(
        json.dumps(
            {
                "total_sources": len(load_sources(config_path)),
                "failed_sources": failed_sources,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    LOG.info("上游健康报告已写入: %s", status_path.name)

    write_manifest(manifest, output_dir)
    LOG.info("生成完成:")
    for label, res in (("完整版", full_results),):
        if not res:
            continue
        for fmt, (path, cnt) in res.items():
            LOG.info("  %s %s: %s (%d)", label, fmt, path, cnt)
    return 0


def stats_cmd(args: argparse.Namespace) -> int:
    """基于已有 dist 目录重新生成 manifest 中各文件的规则计数（不重新下载）。

    注意：本命令仅刷新 manifest.json 的 rules 字段，不重写 *stats.txt / *stats.json，
    因为重新解析会丢失每条规则的原始来源（source）与 yaml 主分类（category_hint），
    导致分类与来源统计失真。精确的分类/来源统计由 build 命令生成。
    """
    output_dir = Path(args.out)
    if not output_dir.exists():
        LOG.error("输出目录不存在: %s", output_dir)
        return 1
    from .rules import parse_line
    manifest = []
    for txt in sorted(output_dir.glob("*.txt")):
        if txt.name.endswith((".stats.txt", "manifest.json")):
            continue
        rule_count = 0
        for line in txt.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(("!", "#")):
                continue
            if txt.name.endswith(("_dns.txt", "_dns_ipv6.txt")):
                if line.startswith(("0.0.0.0 ", ":: ")):
                    rule_count += 1
            else:
                r = parse_line(line, source="reload")
                if r is not None:
                    rule_count += 1
        manifest.append({"name": txt.stem, "file": txt.name, "format": "auto", "rules": rule_count})
    write_manifest(manifest, output_dir)
    LOG.info("manifest 已刷新: %d 个文件", len(manifest))
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
    p_build.add_argument("--no-dns", action="store_true", help="不生成 DNS/hosts/domains 文件")
    p_build.add_argument("--redundant", action="store_true", help="启用冗余域名规则消除")
    p_build.add_argument("--split-by-category", action="store_true", help="split output by category")
    p_build.set_defaults(func=build)

    p_stats = sub.add_parser("stats", help="基于已有输出目录重新生成统计")
    p_stats.add_argument("--out", default="dist", help="输出目录")
    p_stats.set_defaults(func=stats_cmd)

    p_sources = sub.add_parser("sources", help="列出配置中的上游列表")
    p_sources.add_argument("--config", default="config/sources.yaml")
    p_sources.set_defaults(func=sources_cmd)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
