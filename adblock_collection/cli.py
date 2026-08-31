"""Adblock Rule Collection 命令行入口。

子命令：
    build     下载上游列表、合并、去重并生成多种格式过滤器
    sources   列出当前配置中的上游列表
    regression 基于已构建输出运行误杀回归校验

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
    remove_redundant_css,
    source_stats,
)
from .dns_policy import load_dns_policy
from .quality_gate import (
    collect_metrics,
    evaluate,
    load_previous,
    load_thresholds,
    save_previous,
    write_build_report,
)
from .regression import load_false_positives, run_regression
from .provenance import (
    build_provenance,
    build_relation_graph,
    cross_source_duplicate_count,
    detect_exception_conflicts,
    load_security_policy,
)
from .writer import (
    write_adblock,
    write_domains,
    write_dns_safety_report,
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


def _emit(rules, output_dir, prefix, title, desc, gen_dns, source_counts, manifest, policy):
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
        nh = write_hosts(rules, hp, title, policy)
        results["hosts"] = (hp, nh)
        manifest.append({"name": prefix, "file": f"{prefix}_dns.txt", "format": "hosts", "rules": nh})
        ipv6p = output_dir / f"{prefix}_dns_ipv6.txt"
        n6 = write_hosts_ipv6(rules, ipv6p, title, policy)
        results["hosts_ipv6"] = (ipv6p, n6)
        manifest.append({"name": prefix, "file": f"{prefix}_dns_ipv6.txt", "format": "hosts_ipv6", "rules": n6})
        dp = output_dir / f"{prefix}_domains.txt"
        nd = write_domains(rules, dp, title, policy)
        results["domains"] = (dp, nd)
        manifest.append({"name": prefix, "file": f"{prefix}_domains.txt", "format": "domains", "rules": nd})
        write_dns_safety_report(rules, output_dir, prefix, policy)
    return results


def _emit_by_category(rules, output_dir, base_prefix, title_prefix, gen_dns, manifest, policy):
    """按类别筛选全局去重后的规则集，分别生成子列表（不二次去重）。"""
    by_cat: dict[str, list] = {}
    for r in rules:
        by_cat.setdefault(r.category, []).append(r)
    for cat, cat_rules in sorted(by_cat.items()):
        prefix = f"{base_prefix}_{cat}"
        title = f"{title_prefix} ({cat})"
        desc = f"按类型拆分：{cat}"
        _emit(cat_rules, output_dir, prefix, title, desc, gen_dns, source_counts=None, manifest=manifest, policy=policy)


def _emit_security(rules, output_dir, security_policy, manifest, gen_dns, dns_policy):
    """将安全类（malware/phishing/mining 等）规则独立发行到 security/ 子目录。

    安全源与普通广告源的更新频率、误报容忍度、生命周期不同，独立输出便于订阅者
    单独使用，并采用独立健康策略（更宽松的单源骤降阈值）。
    """
    sec_cats = set(security_policy.get("categories", []))
    sec_rules = [r for r in rules if r.category in sec_cats]
    if not sec_rules:
        LOG.info("无安全类规则，跳过 security/ 独立发行")
        return
    sec_dir = output_dir / "security"
    sec_dir.mkdir(parents=True, exist_ok=True)
    title = "Adblock Rule Collection (Security)"
    desc = f"安全类规则（{', '.join(sorted(sec_cats))}）独立发行"
    _emit(sec_rules, sec_dir, "adblock_collection_security", title, desc,
          gen_dns=gen_dns, source_counts=None, manifest=manifest, policy=dns_policy)
    LOG.info("安全类独立发行: %d 条 -> security/", len(sec_rules))


def _write_provenance_report(rules, output_dir) -> dict:
    """生成来源血缘报告 provenance.json、语义关系图 relation_graph.json 与冲突报告。

    返回汇总信息（跨源重复数、例外冲突数、父域子域关系数、高置信度规则占比）。
    """
    prov = build_provenance(rules)
    conflicts = detect_exception_conflicts(rules)
    relations = build_relation_graph(rules)
    parent_child = [r for r in relations if r.kind == "PARENT_CHILD"]
    report = {
        "total_rules": len(prov),
        "cross_source_duplicates": cross_source_duplicate_count(prov),
        "exception_conflicts": {k: v for k, v in conflicts.items()},
        "parent_child_relations": len(parent_child),
        "high_confidence_rules": sum(1 for p in prov.values() if p.confidence >= 0.9),
        "entries": [p.to_dict() for p in prov.values()],
    }
    (output_dir / "provenance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 语义关系图：供调试/审计，记录每条关系
    (output_dir / "relation_graph.json").write_text(
        json.dumps(
            [{"kind": r.kind, "a": r.a, "b": r.b} for r in relations],
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    if conflicts:
        LOG.warning("检测到 %d 个域名存在阻断/例外冲突", len(conflicts))
        for d, norms in conflicts.items():
            LOG.warning("  冲突域名 %s: %d 条相关规则", d, len(norms))
    if parent_child:
        LOG.info("语义关系: %d 条父域/子域冗余关系已记录", len(parent_child))
    return {
        "cross_source_duplicates": report["cross_source_duplicates"],
        "exception_conflicts": len(conflicts),
        "parent_child_relations": len(parent_child),
    }


def build(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        LOG.error("配置文件不存在: %s", config_path)
        return 1

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    sources_meta = load_sources(config_path)
    dns_policy = load_dns_policy(config_path)
    if args.dns_policy:
        from .dns_policy import DNS_LEVELS

        if args.dns_policy in DNS_LEVELS:
            dns_policy = dict(DNS_LEVELS[args.dns_policy])
            dns_policy["level"] = args.dns_policy
    security_policy = load_security_policy(config_path)
    collected = collect(config_path, use_cache=not args.no_cache, offline=args.offline,
                       use_stage_cache=not args.no_stage_cache)
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
        deduped = remove_redundant_css(deduped)

    full_title, full_desc = DEFAULT_HEADERS["full"]
    manifest: list = []
    full_results = _emit(deduped, output_dir, "adblock_collection_full", full_title, full_desc,
                          gen_dns=not args.no_dns, source_counts=src_counts, manifest=manifest,
                          policy=dns_policy)
    if args.split_by_category:
        _emit_by_category(deduped, output_dir, "adblock_collection_full", full_title,
                           gen_dns=not args.no_dns, manifest=manifest, policy=dns_policy)
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

    # 安全类独立发行（malware/phishing/mining 等）
    _emit_security(deduped, output_dir, security_policy, manifest, gen_dns=not args.no_dns, dns_policy=dns_policy)

    # 来源血缘与语义关系图报告
    prov_summary = _write_provenance_report(deduped, output_dir)
    LOG.info("来源血缘: 跨源重复 %d, 例外冲突 %d, 父子域关系 %d",
             prov_summary["cross_source_duplicates"], prov_summary["exception_conflicts"],
             prov_summary["parent_child_relations"])

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

    # 误杀回归校验：把大站被整域误封拦在发生前
    regression_failed = _run_regression(deduped, config_path, dns_policy, output_dir)

    # 质量门禁与构建变化检测
    gate_failed, _ = _run_quality_gate(deduped, src_counts, category_stats(deduped),
                                       full_results, output_dir, config_path)

    write_manifest(manifest, output_dir)
    LOG.info("生成完成:")
    for label, res in (("完整版", full_results),):
        if not res:
            continue
        for fmt, (path, cnt) in res.items():
            LOG.info("  %s %s: %s (%d)", label, fmt, path, cnt)
    return 1 if (regression_failed or gate_failed) else 0


def _run_quality_gate(rules, src_counts, cat_counts, full_results, output_dir, config_path):
    """执行质量门禁与构建变化检测，写 build_report.json 并返回 (失败标记, 报告)。"""
    dns_domains = 0
    if "domains" in full_results:
        dns_domains = full_results["domains"][1]
    thresholds = load_thresholds(config_path)
    metrics = collect_metrics(rules, dns_domains, src_counts, cat_counts)
    prev = load_previous(output_dir)
    gate = evaluate(metrics, prev, thresholds)
    report = write_build_report(output_dir, metrics, prev, gate)
    save_previous(metrics, output_dir)

    if gate.failures:
        LOG.error("质量门禁失败：")
        for f in gate.failures:
            LOG.error("  - %s", f)
    else:
        LOG.info("质量门禁通过")
    if gate.warnings:
        for w in gate.warnings:
            LOG.warning("  - %s", w)
    return (not gate.passed), report


def _run_regression(rules, config_path, dns_policy, output_dir) -> bool:
    """执行误杀/漏拦回归校验，写报告并返回是否失败。"""
    fps = load_false_positives(config_path)
    if not fps.get("allow") and not fps.get("block"):
        LOG.info("未配置误杀回归清单，跳过回归校验")
        return False
    result = run_regression(rules, fps, dns_policy)
    allow_v = result["allow_violations"]
    block_m = result["block_missing"]
    report = {
        "allow_violations": allow_v,
        "block_missing": block_m,
    }
    (output_dir / "regression_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if allow_v:
        LOG.error("误杀回归失败：%d 个域名被整域误封", len(allow_v))
        for v in allow_v:
            LOG.error("  误杀 %s (被 %s 阻断)", v["domain"], v["blocked_by"])
    if block_m:
        LOG.warning("漏拦提示：%d 个预期域名未被整域阻断", len(block_m))
        for m in block_m:
            LOG.warning("  未拦截 %s", m["domain"])
    return bool(allow_v)


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


def regression_cmd(args: argparse.Namespace) -> int:
    """独立运行误杀回归校验（基于已构建规则，不重新下载）。"""
    config_path = Path(args.config)
    if not config_path.exists():
        LOG.error("配置文件不存在: %s", config_path)
        return 1
    output_dir = Path(args.out)
    if not output_dir.exists():
        LOG.error("输出目录不存在: %s", output_dir)
        return 1
    from .rules import parse_line

    rules: list = []
    for txt in output_dir.glob("adblock_collection_full*.txt"):
        for line in txt.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(("!", "#")):
                continue
            r = parse_line(line, source="reload")
            if r is not None:
                rules.append(r)
    dns_policy = load_dns_policy(config_path)
    failed = _run_regression(rules, config_path, dns_policy, output_dir)
    return 1 if failed else 0


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
    p_build.add_argument("--no-stage-cache", action="store_true", help="禁用阶段解析缓存（每次重新解析上游）")
    p_build.add_argument("--offline", action="store_true", help="离线模式，仅使用缓存")
    p_build.add_argument("--no-dns", action="store_true", help="不生成 DNS/hosts/domains 文件")
    p_build.add_argument("--redundant", action="store_true", help="启用冗余域名规则消除")
    p_build.add_argument("--split-by-category", action="store_true", help="split output by category")
    p_build.add_argument("--dns-policy", default=None, choices=["all", "safe", "strict-safe"],
                         help="DNS 安全分级策略（覆盖 config 中的 dns_policy.level）")
    p_build.set_defaults(func=build)

    p_stats = sub.add_parser("stats", help="基于已有输出目录重新生成统计")
    p_stats.add_argument("--out", default="dist", help="输出目录")
    p_stats.set_defaults(func=stats_cmd)

    p_sources = sub.add_parser("sources", help="列出配置中的上游列表")
    p_sources.add_argument("--config", default="config/sources.yaml")
    p_sources.set_defaults(func=sources_cmd)

    p_reg = sub.add_parser("regression", help="基于已构建输出运行误杀回归校验")
    p_reg.add_argument("--config", default="config/sources.yaml")
    p_reg.add_argument("--out", default="dist", help="已构建输出目录")
    p_reg.set_defaults(func=regression_cmd)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
