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

from .adapters import load_publish_config, write_adapters
from .aliases import normalize_aliases
from .arbitrate import arbitrate
from .baseline import compare_baseline
from .build_diff import (
    DIFF_NAME,
    diff_fingerprint,
    load_previous_fingerprint,
    review_new_domains,
    save_fingerprint,
    write_build_diff,
)
from .build_pipeline import (
    BuildContext,
    BuildError,
    BuildFlags,
    FunctionStage,
    InvariantError,
    Pipeline,
)
from .dns_policy import load_dns_policy
from .domain_fold import fold_domains
from .maintenance import update_history, write_maintenance_report
from .merge import (
    CUSTOM_LIST_FILES,
    _normalize_custom_line,
    apply_allowlist,
    apply_badfilter,
    category_stats,
    collect,
    dedupe,
    kind_stats,
    load_sources,
    remove_redundant_css,
    remove_redundant_domains,
    source_stats,
    validate_custom_lists,
    validate_local_rules,
)
from .pipeline import CLASSIFIER_VERSION, NORMALIZER_VERSION, PARSER_VERSION
from .provenance import (
    build_provenance,
    build_relation_graph,
    cross_source_duplicate_count,
    detect_exception_conflicts,
    load_security_policy,
)
from .quality_gate import (
    collect_metrics,
    evaluate,
    load_previous,
    load_thresholds,
    save_previous,
    write_build_report,
)
from .regression import load_false_positives, load_regression_options, run_regression
from .roundtrip import check_roundtrip
from .rules import classify_per_rule, is_ubo_enhanced
from .rules_jsonl import DEFAULT_JSONL_PATH, dump_rules_jsonl, safe_load_rules_jsonl
from .writer import (
    JSDELIVR_MAX_BYTES,
    _blocked_domains,
    _custom_allow_domains,
    _scan_dns_domains,
    write_adblock,
    write_adblock_split,
    write_dns_allow,
    write_dns_safety_report,
    write_domain_rules,
    write_domains,
    write_hosts,
    write_hosts_ipv6,
    write_manifest,
    write_rulesets,
    write_summary,
    write_summary_json,
)

LOG = logging.getLogger("adblock_collection")


def _positive_int(text: str) -> int:
    """argparse 类型：只接受正整数，避免 0/负数把全部规则误判为过期。"""
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"需要正整数: {text!r}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError(f"需要正整数: {text!r}")
    return value

DEFAULT_HEADERS = {
    "full": (
        "Adblock Rule Collection (Full)",
        "完整版广告拦截与 DNS 过滤规则集合，含大量上游列表，可能有误杀。",
    ),
}


def _emit_adblock_file(
    rules, output_dir, prefix, title, desc, manifest, rel_prefix=""
) -> tuple[Path, int]:
    """写一个 adblock 列表文件；超过 jsDelivr 单文件上限时自动生成分片主链。

    ``rel_prefix`` 为 ``dist`` 内的相对目录前缀（如 ``security/``），写入 manifest 的
    ``file`` 因此始终可相对 manifest 定位。
    """
    rules = list(rules)
    path = output_dir / f"{prefix}.txt"
    n = write_adblock(rules, path, title, desc)
    manifest.append(
        {
            "name": prefix,
            "file": f"{rel_prefix}{prefix}.txt",
            "format": "adblock",
            "rules": n,
        }
    )
    if path.stat().st_size > JSDELIVR_MAX_BYTES:
        split = write_adblock_split(
            rules, output_dir, prefix, title, desc, max_bytes=JSDELIVR_MAX_BYTES
        )
        if split:
            master, parts, total = split
            LOG.info(
                "adblock 列表 %s (%.2f MiB) 超过 jsDelivr 上限，已拆分为 %d 个分片主链 %s",
                path.name,
                path.stat().st_size / 1048576,
                len(parts),
                master,
            )
            manifest.append(
                {
                    "name": prefix,
                    "file": f"{rel_prefix}{master}",
                    "format": "adblock_include",
                    "rules": total,
                    "parts": parts,
                }
            )
    return path, n


def _emit(
    rules,
    output_dir,
    prefix,
    title,
    desc,
    gen_dns,
    source_counts,
    manifest,
    policy,
    domains=None,
    rel_prefix="",
):
    rules = list(rules)
    results = {}
    ap, n = _emit_adblock_file(
        rules, output_dir, prefix, title, desc, manifest, rel_prefix
    )
    results["adblock"] = (ap, n)
    src_counts = source_stats(rules) if source_counts is None else source_counts
    write_summary(category_stats(rules), output_dir, prefix)
    write_summary_json(
        category_stats(rules),
        kind_stats(rules),
        output_dir,
        prefix,
        len(rules),
        src_counts,
    )
    if gen_dns:
        # 域名集合在 hosts / ipv6 / domains 三份产物间共享，只结算一次
        if domains is None:
            domains = _blocked_domains(rules, policy)
        hp = output_dir / f"{prefix}_dns.txt"
        nh = write_hosts(rules, hp, title, policy, domains=domains)
        results["hosts"] = (hp, nh)
        manifest.append(
            {
                "name": prefix,
                "file": f"{rel_prefix}{prefix}_dns.txt",
                "format": "hosts",
                "rules": nh,
            }
        )
        ipv6p = output_dir / f"{prefix}_dns_ipv6.txt"
        n6 = write_hosts_ipv6(rules, ipv6p, title, policy, domains=domains)
        results["hosts_ipv6"] = (ipv6p, n6)
        manifest.append(
            {
                "name": prefix,
                "file": f"{rel_prefix}{prefix}_dns_ipv6.txt",
                "format": "hosts_ipv6",
                "rules": n6,
            }
        )
        dp = output_dir / f"{prefix}_domains.txt"
        nd = write_domains(rules, dp, title, policy, domains=domains)
        results["domains"] = (dp, nd)
        manifest.append(
            {
                "name": prefix,
                "file": f"{rel_prefix}{prefix}_domains.txt",
                "format": "domains",
                "rules": nd,
            }
        )
        write_dns_safety_report(rules, output_dir, prefix, policy)
    return results


def _emit_by_category(
    rules, output_dir, base_prefix, title_prefix, gen_dns, manifest, policy
):
    """按类别筛选全局去重后的规则集，分别生成子列表（不二次去重）。"""
    by_cat: dict[str, list] = {}
    for r in rules:
        by_cat.setdefault(r.category, []).append(r)
    for cat, cat_rules in sorted(by_cat.items()):
        prefix = f"{base_prefix}_{cat}"
        title = f"{title_prefix} ({cat})"
        desc = f"按类型拆分：{cat}"
        _emit(
            cat_rules,
            output_dir,
            prefix,
            title,
            desc,
            gen_dns,
            source_counts=None,
            manifest=manifest,
            policy=policy,
        )


_COSMETIC_KINDS = ("css", "scriptlet", "html", "js")


def _emit_layers(
    rules, output_dir, base_prefix, manifest, gen_dns, policy, domains=None
) -> None:
    """按「规则类型」产出三层防护清单，对应 DNS / 扩展网络 / 扩展元素隐藏。

    - 扩展网络拦截层：``kind=network``，请求阻断规则（含修饰符与站点例外）
    - 扩展元素隐藏层：``css/scriptlet/html/js``，DOM 隐藏与脚本注入
    - DNS 等价清单：整域阻断的纯域名 ``||domain^`` 规则，无修饰符

    类别拆分按来源类别（network/privacy/...）分组，本函数按规则类型分组，二者互补。
    """
    rules = list(rules)
    network = [r for r in rules if r.kind == "network"]
    cosmetic = [r for r in rules if r.kind in _COSMETIC_KINDS]
    _emit_adblock_file(
        network,
        output_dir,
        f"{base_prefix}_browser_network",
        "Adblock Rule Collection (Browser Network)",
        "扩展网络拦截层：域名/URL/资源请求阻断，含修饰符与站点例外，不含元素隐藏",
        manifest,
    )
    _emit_adblock_file(
        cosmetic,
        output_dir,
        f"{base_prefix}_cosmetic",
        "Adblock Rule Collection (Cosmetic)",
        "扩展元素隐藏层：CSS 隐藏 / 扩展选择器 / scriptlet 脚本注入 / HTML 过滤",
        manifest,
    )
    if gen_dns:
        dp = output_dir / f"{base_prefix}_dns_abp.txt"
        nd = write_domain_rules(
            rules,
            dp,
            "Adblock Rule Collection (DNS-domain rules)",
            "DNS 等价域名阻断：整域 ||domain^ 纯域名规则，无修饰符，浏览器与 DNS 端均可导入",
            policy,
            domains=domains,
        )
        manifest.append(
            {
                "name": f"{base_prefix}_dns_abp",
                "file": dp.name,
                "format": "adblock_domains",
                "rules": nd,
            }
        )
    LOG.info("三层产物: 网络拦截 %d 条, 元素隐藏 %d 条", len(network), len(cosmetic))


def _emit_ubo_enhance(rules, output_dir, manifest) -> None:
    """uBO/AdGuard 高级增强清单：聚合 ABP 不识别的增强规则。

    含两类：网络层高级修饰符（``$redirect`` / ``$csp`` / ``$removeparam`` …），以及
    元素/脚本类专有语法（``##+js`` scriptlet、``##^`` HTML 过滤、``#?#`` 过程式选择器、
    ``:remove()`` DOM 移除）。单独成一份便于支持该能力的扩展订阅；文件名为
    ``adblock_collection_ubo_enhance.txt``，不参与类别并集不变量。
    """
    rules = list(rules)
    enhanced = [r for r in rules if is_ubo_enhanced(r)]
    path = output_dir / "adblock_collection_ubo_enhance.txt"
    n = write_adblock(
        enhanced,
        path,
        "Adblock Rule Collection (uBO enhance)",
        "uBlock Origin / AdGuard 高级增强规则：$redirect/$csp/$removeparam 与 scriptlet/HTML 过滤/过程式选择器，ABP 不识别",
    )
    manifest.append(
        {
            "name": "adblock_collection_ubo_enhance",
            "file": path.name,
            "format": "adblock_ubo",
            "rules": n,
        }
    )
    LOG.info("uBO 增强清单: %d 条 -> %s", n, path.name)


def _emit_dns_allow(rules, output_dir, manifest) -> None:
    """DNS 白名单：仅来自自定义白名单（config/lists/allowlist.txt）的整域全局例外。"""
    path = output_dir / "dns_allow.txt"
    n = write_dns_allow(rules, path, "Adblock Rule Collection (DNS allowlist)")
    manifest.append(
        {
            "name": "dns_allow",
            "file": path.name,
            "format": "dns_allow",
            "source": "custom_allowlist",
            "rules": n,
        }
    )
    LOG.info("DNS 白名单: %d 个域名 -> %s", n, path.name)


def _emit_rulesets(
    rules, output_dir, manifest, policy, domains=None, exact_domains=None
) -> None:
    """连接层规则集：mihomo / sing-box / Surge / Quantumult X。

    内容与 DNS 域名集合完全一致，供 TUN 模式按 TLS/QUIC SNI 在连接层拒绝广告域，
    从而绕过 App 的 HTTPDNS / IP 直连。含子域来源（``||domain^``）用后缀算子；精确
    来源（hosts / domains-only 行）用精确算子（DOMAIN / domain / host）。
    """
    counts = write_rulesets(
        rules,
        output_dir,
        policy,
        "Adblock Rule Collection (connection-layer ruleset)",
        domains=domains,
        exact_domains=exact_domains,
    )
    for fmt, fname, fmt_name in (
        ("clash", "adblock_clash.yaml", "clash_ruleset"),
        ("singbox", "adblock_singbox.json", "singbox_ruleset"),
        ("surge", "adblock_surge.list", "surge_ruleset"),
        ("surge_domain_set", "adblock_surge_domain_set.txt", "surge_domain_set"),
        ("quanx", "adblock_quanx.list", "quanx_ruleset"),
    ):
        manifest.append(
            {
                "name": f"ruleset_{fmt}",
                "file": f"rulesets/{fname}",
                "format": fmt_name,
                "rules": counts[fmt],
            }
        )
    # Surge / Quantumult X 文本规则集超 jsDelivr 上限时生成 _partNN 分片，单独登记
    rdir = output_dir / "rulesets"
    for fmt, base in (("surge", "adblock_surge"), ("quanx", "adblock_quanx")):
        for part in sorted(rdir.glob(f"{base}_part*.list")):
            rules_n = sum(
                1
                for line in part.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")
            )
            manifest.append(
                {
                    "name": f"ruleset_{fmt}_part",
                    "file": f"rulesets/{part.name}",
                    "format": f"{fmt}_ruleset_part",
                    "rules": rules_n,
                }
            )
    LOG.info("连接层规则集: %d 个域名 -> rulesets/", counts["clash"])


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
    _emit(
        sec_rules,
        sec_dir,
        "adblock_collection_security",
        title,
        desc,
        gen_dns=gen_dns,
        source_counts=None,
        manifest=manifest,
        policy=dns_policy,
        rel_prefix="security/",
    )
    LOG.info("安全类独立发行: %d 条 -> security/", len(sec_rules))


def _check_layers_invariant(manifest: list) -> None:
    """P1：网络拦截层 + 元素隐藏层必须等于完整版（三层并集无损）。"""
    full_n = next(
        r["rules"] for r in manifest if r["file"] == "adblock_collection_full.txt"
    )
    layer_n = sum(
        r["rules"]
        for r in manifest
        if r["file"].endswith(("_browser_network.txt", "_cosmetic.txt"))
    )
    if layer_n != full_n:
        raise InvariantError(
            f"三层产物不变量被破坏: 网络+元素隐藏 {layer_n} != 完整版 {full_n}"
        )


def _check_category_invariant(manifest: list) -> None:
    """P3：按类别拆分的子列表并集必须等于完整版。"""
    cat_total = sum(
        r["rules"]
        for r in manifest
        if r["name"].startswith("adblock_collection_full_")
        and not any(
            r["file"].endswith(s)
            for s in (
                "_dns.txt",
                "_domains.txt",
                "_dns_ipv6.txt",
                "_dns_abp.txt",
                "_browser_network.txt",
                "_cosmetic.txt",
            )
        )
        and "_jsdelivr" not in r["file"]
        and r["file"] != "adblock_collection_full.txt"
    )
    full_n = next(
        r["rules"] for r in manifest if r["file"] == "adblock_collection_full.txt"
    )
    if cat_total != full_n:
        raise InvariantError(
            f"类别拆分不变量被破坏: 子列表总和 {cat_total} != 完整版 {full_n}"
        )


def emit_outputs(rules, ctx, output_dir=None) -> tuple[list, dict]:
    """写出完整版、三层、类别拆分与安全类产物，并校验不变量。

    复用现有 writer 逻辑，不发起网络请求，可由 ``rules_jsonl.emit_from_jsonl``
    在离线场景下调用。
    """
    target = Path(output_dir) if output_dir is not None else ctx.output_dir
    gen_dns = ctx.flags.gen_dns
    title, desc = DEFAULT_HEADERS["full"]
    manifest: list = []
    # 完整版规则的拦截域名集合只结算一次，供 hosts / domains / DNS 等价 / 连接层规则集共享，
    # 避免对同一份 78 万条规则重复全量扫描。同时区分「含子域」与「精确」两条来源：
    # hosts / domains 文本层本身就是精确匹配，连接层规则集则按来源选择算子。
    if gen_dns:
        split_suffix, split_exact = _scan_dns_domains(rules, ctx.dns_policy)
        blocked = split_suffix | split_exact
    else:
        split_exact = None
        blocked = None
    full_results = _emit(
        rules,
        target,
        "adblock_collection_full",
        title,
        desc,
        gen_dns=gen_dns,
        source_counts=ctx.artifacts.get("source_counts"),
        manifest=manifest,
        policy=ctx.dns_policy,
        domains=blocked,
    )
    _emit_layers(
        rules,
        target,
        "adblock_collection_full",
        manifest,
        gen_dns=gen_dns,
        policy=ctx.dns_policy,
        domains=blocked,
    )
    _check_layers_invariant(manifest)
    _emit_ubo_enhance(rules, target, manifest)
    if gen_dns:
        _emit_dns_allow(rules, target, manifest)
    if gen_dns and ctx.flags.gen_rulesets:
        _emit_rulesets(
            rules,
            target,
            manifest,
            ctx.dns_policy,
            domains=blocked,
            exact_domains=split_exact,
        )
    if gen_dns:
        # 客户端适配产物：只引用规范规则集，不新增拦截判定；连接层适配依赖 rulesets/。
        write_adapters(
            target,
            load_publish_config(ctx.config_path),
            manifest,
            rulesets_dir=(target / "rulesets") if ctx.flags.gen_rulesets else None,
        )
    if ctx.flags.split_by_category:
        _emit_by_category(
            rules,
            target,
            "adblock_collection_full",
            title,
            gen_dns=gen_dns,
            manifest=manifest,
            policy=ctx.dns_policy,
        )
        _check_category_invariant(manifest)
    _emit_security(
        rules,
        target,
        ctx.security_policy,
        manifest,
        gen_dns=gen_dns,
        dns_policy=ctx.dns_policy,
    )
    roundtrip_paths = {fmt: p for fmt, (p, _n) in full_results.items()}
    for entry in manifest:
        if entry.get("format") == "adblock_domains":
            roundtrip_paths["adblock_domains"] = target / entry["file"]
            break
    issues = check_roundtrip(roundtrip_paths, rules, ctx.dns_policy)
    if issues:
        raise InvariantError("往返校验失败(P9): " + "; ".join(issues))
    return manifest, full_results


def _validate_invariants(rules, dns_policy) -> list[str]:
    """dry-run 场景下的内存不变量校验（不写盘）。"""
    problems: list[str] = []
    network = [r for r in rules if r.kind == "network"]
    cosmetic = [r for r in rules if r.kind in _COSMETIC_KINDS]
    if len(network) + len(cosmetic) != len(rules):
        problems.append(
            f"P1 类型互斥完备: 网络 {len(network)} + 元素 {len(cosmetic)} != 总数 {len(rules)}"
        )
    domains = _blocked_domains(rules, dns_policy)
    if any(not d or "." not in d for d in domains):
        problems.append("P2 DNS 等价: 域名集合含非法条目")
    # P3 DNS 白名单：自定义白名单整域全局例外域名必须合法（供 AGH/Pi-hole 直接导入）
    allow = _custom_allow_domains(rules)
    bad_allow = sorted(d for d in allow if not d or "." not in d or "*" in d)
    if bad_allow:
        problems.append(
            f"P3 DNS 白名单: {len(bad_allow)} 个非法域名, 例: {bad_allow[:3]}"
        )
    # P4 uBO 增强清单：只应包含网络层高级修饰符与元素/脚本类专有语法，
    # 不允许出现无法归入网络或元素层的规则。
    enhanced = [r for r in rules if is_ubo_enhanced(r)]
    allowed_kinds = {"network", *_COSMETIC_KINDS}
    if any(r.kind not in allowed_kinds for r in enhanced):
        problems.append("P4 uBO 增强: 含既非网络层也非元素层的规则")
    return problems


def _write_provenance_report(rules, output_dir) -> dict:
    """生成来源血缘报告 provenance.json、语义关系图 relation_graph.json 与冲突报告。

    返回汇总信息（跨源重复数、例外冲突数、父域子域关系数、高置信度规则占比）。
    """
    prov = build_provenance(rules)
    conflicts = detect_exception_conflicts(rules)
    relations = build_relation_graph(rules, prov)
    parent_child = [r for r in relations if r.kind == "PARENT_CHILD"]
    report = {
        "total_rules": len(prov),
        "cross_source_duplicates": cross_source_duplicate_count(prov),
        "exception_conflicts": {k: v for k, v in conflicts.items()},
        "parent_child_relations": len(parent_child),
        "high_confidence_rules": sum(1 for p in prov.values() if p.confidence >= 0.9),
    }
    (output_dir / "provenance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 语义关系图：供调试/审计，记录每条关系
    (output_dir / "relation_graph.json").write_text(
        json.dumps(
            [
                {"kind": r.kind, "a": r.a, "b": r.b}
                for r in relations
                if r.kind != "CROSS_SOURCE" or len(r.b.split(",")) > 1
            ],
            ensure_ascii=False,
            indent=2,
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
    if not getattr(args, "dry_run", False):
        output_dir.mkdir(parents=True, exist_ok=True)

    dns_policy = load_dns_policy(config_path)
    if args.dns_policy:
        from .dns_policy import DNS_LEVELS

        if args.dns_policy in DNS_LEVELS:
            dns_policy = dict(DNS_LEVELS[args.dns_policy])
            dns_policy["level"] = args.dns_policy
    # C5：导航修饰（$popup/$document）整域放大默认纳入；显式关闭后仅保留纯域名/整域语义规则。
    if not getattr(args, "navigation_domains", True):
        dns_policy = dict(dns_policy)
        dns_policy["include_navigation_domains"] = False
    security_policy = load_security_policy(config_path)
    # 安全类源名单：门禁对其使用更宽松的 security_policy.source_drop_percent，
    # 与 _emit_security 的独立发行策略保持一致。
    sec_cats = set(security_policy.get("categories", []))
    security_sources = {
        src.get("name")
        for src in load_sources(config_path)
        if src.get("category") in sec_cats
    }

    # 本地增强规则静态校验：禁止通配误伤规则，违规则阻断构建，落实「宁愿少拦截」
    lr_violations = validate_local_rules(config_path)
    if lr_violations:
        for v in lr_violations:
            LOG.error("本地增强规则违规: %s", v)
        LOG.error(
            "local_rules.txt 含 %d 条可能误伤整页/整站的通配规则，已阻断构建。请改为精确选择器。",
            len(lr_violations),
        )
        return 2

    # 自定义黑/白名单静态校验：同样禁止通配误伤规则
    cl_violations = validate_custom_lists(config_path)
    if cl_violations:
        for v in cl_violations:
            LOG.error("自定义名单违规: %s", v)
        LOG.error(
            "config/lists/ 含 %d 条可能误伤整页/整站的通配规则，已阻断构建。请改为精确选择器。",
            len(cl_violations),
        )
        return 2

    flags = BuildFlags(
        alias_normalize=args.alias_normalize,
        resolve_conflicts=args.resolve_conflicts,
        per_rule_classify=args.per_rule_classify,
        domain_fold=args.domain_fold,
        redundant=args.redundant,
        split_by_category=args.split_by_category,
        gen_dns=not args.no_dns,
        gen_rulesets=not getattr(args, "no_rulesets", False),
        dry_run=getattr(args, "dry_run", False),
    )
    ctx = BuildContext(
        config_path=config_path,
        output_dir=output_dir,
        dns_policy=dns_policy,
        security_policy=security_policy,
        flags=flags,
    )

    # dry-run 不写盘，依赖写盘后动作的选项会被跳过；显式告警避免「给了参数却没效果」
    if flags.dry_run and getattr(args, "history", False):
        LOG.warning("--dry-run 与 --history 同时给出：dry-run 不写任何产物，维护跟踪已跳过")
    if flags.dry_run and getattr(args, "baseline", None):
        LOG.warning("--dry-run 与 --baseline 同时给出：dry-run 不写产物，字节基线比对已跳过")

    def collect_stage(rules, context):
        collected = collect(
            config_path,
            use_cache=not args.no_cache,
            offline=args.offline,
            use_stage_cache=not args.no_stage_cache,
        )
        context.artifacts["failed_sources"] = collected.get("_failed", [])
        all_rules: list = []
        for _name, source_rules in collected.get("all", []):
            all_rules.extend(source_rules)
        return all_rules

    def alias_stage(rules, context):
        out, report = normalize_aliases(rules)
        context.artifacts.setdefault("enhancements", {})["alias_normalize"] = (
            report.to_dict()
        )
        LOG.info(
            "别名归一化: 改写 %d 条, 折叠 %d 条", report.normalized, report.collapsed
        )
        return out

    def source_stats_stage(rules, context):
        stats = source_stats(rules)
        context.artifacts["source_counts"] = stats
        for name, cnt in stats.items():
            LOG.info("上游贡献规则: %-35s %d", name, cnt)
        failed = context.artifacts.get("failed_sources") or []
        if failed:
            LOG.warning("本次下载失败的源 (%d): %s", len(failed), ", ".join(failed))
        LOG.info("原始规则总数: %d", len(rules))
        return rules

    def dedupe_stage(rules, context):
        out = dedupe(rules)
        LOG.info("去重后规则总数: %d", len(out))
        return out

    def allowlist_stage(rules, context):
        fps = load_false_positives(config_path)
        if not fps.get("allow"):
            return rules
        before = len(rules)
        out = apply_allowlist(rules, fps["allow"])
        LOG.info("白名单强制放行移除规则: %d", before - len(out))
        return out

    def badfilter_stage(rules, context):
        return apply_badfilter(rules)

    def classify_stage(rules, context):
        before_cats = [r.category for r in rules]
        out = classify_per_rule(rules)
        changed = sum(
            1
            for rule, prev in zip(out, before_cats, strict=True)
            if rule.category != prev
        )
        context.artifacts.setdefault("enhancements", {})["per_rule_classify"] = {
            "reclassified": changed
        }
        LOG.info("逐条多信号分类: 改写类别 %d 条", changed)
        return out

    def arbitrate_stage(rules, context):
        out, records = arbitrate(rules)
        removed = sum(len(r.losers) for r in records)
        if not context.flags.dry_run:
            (context.output_dir / "arbitration.json").write_text(
                json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        context.artifacts.setdefault("enhancements", {})["resolve_conflicts"] = {
            "removed": removed,
            "records": len(records),
        }
        LOG.info(
            "冲突仲裁: 移除 %d 条, 记录 %d 条 %s",
            removed,
            len(records),
            "(dry-run 不写盘)" if context.flags.dry_run else "-> arbitration.json",
        )
        return out

    def fold_stage(rules, context):
        out, report = fold_domains(rules)
        if not context.flags.dry_run:
            (context.output_dir / "domain_fold.json").write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        context.artifacts.setdefault("enhancements", {})["domain_fold"] = {
            "folded": report.folded,
            "domains": len(report.domains),
        }
        LOG.info(
            "域名层级折叠: 折叠 %d 条, 涉及 %d 个域名 %s",
            report.folded,
            len(report.domains),
            "(dry-run 不写盘)" if context.flags.dry_run else "-> domain_fold.json",
        )
        return out

    def legacy_redundant_stage(rules, context):
        # 兼容旧 --redundant：增强折叠关闭时用于复现重构前产物
        return remove_redundant_domains(rules)

    def css_dedupe_stage(rules, context):
        before = len(rules)
        out = remove_redundant_css(rules)
        LOG.info("CSS 冗余消除: %d -> %d 条", before, len(out))
        return out

    stages = [FunctionStage("collect", collect_stage)]
    stages.append(FunctionStage("source_stats", source_stats_stage))
    stages.append(FunctionStage("dedupe", dedupe_stage))
    if flags.alias_normalize:
        stages.append(FunctionStage("alias", alias_stage))
    stages.append(FunctionStage("allowlist", allowlist_stage))
    stages.append(FunctionStage("badfilter", badfilter_stage))
    if flags.per_rule_classify:
        stages.append(FunctionStage("classify", classify_stage))
    if flags.resolve_conflicts:
        stages.append(FunctionStage("arbitrate", arbitrate_stage))
    if flags.domain_fold:
        stages.append(FunctionStage("domain_fold", fold_stage))
    elif flags.redundant:
        stages.append(FunctionStage("redundant", legacy_redundant_stage))
    stages.append(FunctionStage("css_dedupe", css_dedupe_stage))

    try:
        deduped, pipeline_report = Pipeline(stages).run([], ctx)
    except BuildError as exc:
        LOG.error("构建失败: %s", exc)
        return 3
    enhancements = ctx.artifacts.get("enhancements", {})

    # 中间产物：无条件落盘，输出阶段由其派生（可离线重建）；
    # dry-run 承诺不写任何产物，故跳过落盘，改用内存规则集继续校验
    if flags.dry_run:
        LOG.info("dry-run: 跳过中间产物落盘（.cache/build/rules.jsonl）")
    else:
        dump_rules_jsonl(deduped, DEFAULT_JSONL_PATH)
        reloaded = safe_load_rules_jsonl(DEFAULT_JSONL_PATH)
        if reloaded is not None:
            deduped = reloaded

    if flags.dry_run:
        problems = _validate_invariants(deduped, dns_policy)
        for problem in problems:
            LOG.error("dry-run 不变量校验失败: %s", problem)
        LOG.info(
            "dry-run 完成: %d 条规则, %d 个阶段, 共 %d ms",
            len(deduped),
            len(pipeline_report.stages),
            pipeline_report.total_elapsed_ms,
        )
        return 3 if problems else 0

    src_counts = ctx.artifacts.get("source_counts", {})

    # 输出阶段：由中间产物派生的规则集写出全部产物并校验不变量
    try:
        manifest, full_results = emit_outputs(deduped, ctx)
    except BuildError as exc:
        LOG.error("构建失败: %s", exc)
        return 3

    # 来源血缘与语义关系图报告
    prov_summary = _write_provenance_report(deduped, output_dir)
    LOG.info(
        "来源血缘: 跨源重复 %d, 例外冲突 %d, 父子域关系 %d",
        prov_summary["cross_source_duplicates"],
        prov_summary["exception_conflicts"],
        prov_summary["parent_child_relations"],
    )

    # 相邻两次构建的逐条规则差异（本地/连续构建；CI 全新 checkout 跳过）
    prev_fingerprint = load_previous_fingerprint()
    if prev_fingerprint is not None:
        added, removed = diff_fingerprint(prev_fingerprint, deduped)
        diff_summary = write_build_diff(output_dir, added, removed)
        LOG.info(
            "构建差异: 新增 %d 条, 移除 %d 条 -> %s",
            diff_summary["added"],
            diff_summary["removed"],
            DIFF_NAME,
        )
        # C6-2：对逐条新增里「新出现的整域阻断」输出待人工确认清单
        review_new_domains(
            output_dir, added, load_false_positives(config_path).get("allow", [])
        )
    else:
        LOG.info("无上一批规则指纹，跳过逐条构建差异（首次构建）")

    # 写入上游健康报告（供订阅者判断数据完整性）
    status_path = output_dir / "sources_status.json"
    failed_sources = ctx.artifacts.get("failed_sources", [])
    sources_status_payload = {
        "total_sources": len(load_sources(config_path)),
        "failed_sources": failed_sources,
        # C3：数据完整性显式标注，供订阅端程序化判断本次产物是否缺少上游源
        "complete": not failed_sources,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    status_path.write_text(
        json.dumps(sources_status_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    LOG.info(
        "上游健康报告已写入: %s（失败 %d 个）",
        status_path.name,
        len(failed_sources),
    )

    # 误杀回归校验：把大站被整域误封拦在发生前
    regression_failed = _run_regression(deduped, config_path, dns_policy, output_dir)

    # 质量门禁与构建变化检测
    gate_failed, _ = _run_quality_gate(
        deduped,
        src_counts,
        category_stats(deduped),
        full_results,
        output_dir,
        config_path,
        enhancements=enhancements,
        security_sources=security_sources,
    )

    write_manifest(
        manifest,
        output_dir,
        versions={
            "parser": PARSER_VERSION,
            "normalizer": NORMALIZER_VERSION,
            "classifier": CLASSIFIER_VERSION,
        },
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        sources_status=sources_status_payload,
    )

    # 字节级基线比对（骨架迁移阶段门禁；迁移完成后为诊断工具）
    baseline_dir = getattr(args, "baseline", None)
    if baseline_dir:
        diff = compare_baseline(Path(baseline_dir), output_dir)
        if diff.passed:
            LOG.info("字节基线比对通过: %d 个文件一致", len(diff.files))
        else:
            for f in diff.mismatches:
                LOG.error(
                    "字节基线差异: %s (missing=%s, 首个差异行=%s, 差异行数=%d)",
                    f.name,
                    f.missing,
                    f.first_diff_line,
                    f.diff_lines,
                )
            return 3

    LOG.info("生成完成:")
    for label, res in (("完整版", full_results),):
        if not res:
            continue
        for fmt, (path, cnt) in res.items():
            LOG.info("  %s %s: %s (%d)", label, fmt, path, cnt)

    # 成功构建才推进下批基准与维护历史：失败批次的规则不应成为下次比对/在册的基线，
    # 否则回归会在下一次构建被静默掩盖
    if regression_failed or gate_failed:
        LOG.warning("本次构建未通过回归/门禁，跳过更新规则指纹与维护历史")
        return 1

    save_fingerprint(deduped)

    if getattr(args, "history", False):
        maint = update_history(deduped, stale_days=getattr(args, "stale_days", 30))
        write_maintenance_report(output_dir, maint)
        LOG.info(
            "维护跟踪: 在册 %d 条, 其中 %d 条连续缺席 >= %d 天 -> %s",
            maint["tracked"],
            len(maint["stale"]),
            maint["stale_days"],
            "maintenance_report.json",
        )
    return 0


def _run_quality_gate(
    rules,
    src_counts,
    cat_counts,
    full_results,
    output_dir,
    config_path,
    enhancements=None,
    security_sources=None,
):
    """执行质量门禁与构建变化检测，写 build_report.json 并返回 (失败标记, 报告)。"""
    dns_domains = 0
    if "domains" in full_results:
        dns_domains = full_results["domains"][1]
    thresholds = load_thresholds(config_path)
    metrics = collect_metrics(rules, dns_domains, src_counts, cat_counts)
    prev = load_previous(output_dir)
    gate = evaluate(metrics, prev, thresholds, security_sources=security_sources)
    report = write_build_report(
        output_dir, metrics, prev, gate, enhancements=enhancements
    )
    if gate.passed:
        save_previous(metrics, output_dir)
    else:
        LOG.warning("门禁未通过，保留上一批 metrics 作为基线（不推进 previous_metrics.json）")

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
    options = load_regression_options(config_path)
    strict = options["block_missing_strict"]
    result = run_regression(rules, fps, dns_policy)
    allow_v = result["allow_violations"]
    block_m = result["block_missing"]
    report = {
        "allow_violations": allow_v,
        "block_missing": block_m,
        "block_missing_strict": strict,
    }
    (output_dir / "regression_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if allow_v:
        LOG.error("误杀回归失败：%d 个域名被整域误封", len(allow_v))
        for v in allow_v:
            LOG.error("  误杀 %s (被 %s 阻断)", v["domain"], v["blocked_by"])
    if block_m:
        level = LOG.error if strict else LOG.warning
        level(
            "%s：%d 个预期域名未被整域阻断%s",
            "漏拦回归失败" if strict else "漏拦提示",
            len(block_m),
            "（block_missing_strict=true，构建中止）" if strict else "",
        )
        for m in block_m:
            level("  未拦截 %s", m["domain"])
    return bool(allow_v) or (strict and bool(block_m))


def stats_cmd(args: argparse.Namespace) -> int:
    """基于已有 dist 目录重新生成 manifest 中各文件的规则计数（不重新下载）。

    注意：本命令仅刷新 manifest.json 的 rules 字段，不重写 *stats.txt / *stats.json，
    因为重新解析会丢失每条规则的原始来源（source）与 yaml 主分类（category_hint），
    导致分类与来源统计失真。精确的分类/来源统计由 build 命令生成。

    若目录内已有 manifest.json，则按 ``file`` 合并——保留 ``name``/``format``/
    ``source``/``parts`` 与连接层规则集条目，仅对 ``.txt`` 重算 rules，避免把 build
    生成的富 manifest 降级为只含 ``*.txt``、``format`` 全为 ``auto`` 的残缺版本。
    """
    output_dir = Path(args.out)
    if not output_dir.exists():
        LOG.error("输出目录不存在: %s", output_dir)
        return 1
    from .rules import parse_line

    def count_txt_rules(txt: Path) -> int:
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
        return rule_count

    manifest_path = output_dir / "manifest.json"
    entries: list[dict] = []
    existing_payload: dict = {}
    if manifest_path.exists():
        try:
            existing_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = list(existing_payload.get("generated_files", []))
        except (ValueError, OSError) as exc:
            LOG.warning("无法读取既有 manifest，回退为按 *.txt 重建: %s", exc)
            entries = []
    if entries:
        refreshed = 0
        for entry in entries:
            fname = entry["file"]
            f = output_dir / fname
            if (
                fname.endswith(".txt")
                and not fname.endswith(".stats.txt")
                and not fname.startswith("adapters/")
                and f.exists()
            ):
                entry["rules"] = count_txt_rules(f)
                refreshed += 1
        manifest = entries
        LOG.info(
            "manifest 已按既有条目刷新: %d 个文件（%d 个 .txt 重算）",
            len(manifest),
            refreshed,
        )
    else:
        manifest = []
        for txt in sorted(output_dir.glob("*.txt")):
            if txt.name.endswith((".stats.txt", "manifest.json")):
                continue
            manifest.append(
                {
                    "name": txt.stem,
                    "file": txt.name,
                    "format": "auto",
                    "rules": count_txt_rules(txt),
                }
            )
        LOG.info("manifest 已重建: %d 个文件", len(manifest))
    # 保留既有顶层溯源字段，避免 stats 把 build 生成的富 manifest 降级
    write_manifest(
        manifest,
        output_dir,
        versions=existing_payload.get("versions"),
        generated_at=existing_payload.get("generated_at"),
        sources_status=existing_payload.get("sources_status"),
    )
    return 0


def sources_cmd(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        LOG.error("配置文件不存在: %s", config_path)
        return 1
    for src in load_sources(config_path):
        lite = "lite" if src.get("lite") else "full"
        print(
            f"{src.get('name', '?'):<35} {lite:<5} {src.get('category', 'other'):<12} {src.get('url', '')}"
        )
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
    full_path = output_dir / "adblock_collection_full.txt"
    if full_path.exists():
        # 完整版已含全部子集，只读它即可；避免把三层/类别/uBO 增强产物重复读入
        txt_files = [full_path]
    else:
        txt_files = [
            p
            for p in sorted(output_dir.glob("adblock_collection_full*.txt"))
            if not p.name.endswith(("_ubo_enhance.txt", "_jsdelivr.txt"))
        ]
    for txt in txt_files:
        for line in txt.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(("!", "#")):
                continue
            r = parse_line(line, source="reload")
            if r is not None:
                rules.append(r)
    dns_policy = load_dns_policy(config_path)
    failed = _run_regression(rules, config_path, dns_policy, output_dir)
    return 1 if failed else 0


def lint_cmd(args: argparse.Namespace) -> int:
    """校验规则文件的语法与冲突，并拆分 DNS 域名与浏览器规则（不修改输入）。"""
    from .dns_policy import DNS_LEVELS
    from .lint import LintReport, lint_text

    config_path = Path(args.config)
    paths = [Path(p) for p in args.rules]
    existing: list[Path] = []
    for p in paths:
        if p.exists():
            existing.append(p)
        else:
            LOG.warning("规则文件不存在，跳过: %s", p)
    if not existing:
        LOG.error("没有可校验的规则文件")
        return 1
    if args.dns_policy:
        policy = dict(DNS_LEVELS[args.dns_policy])
        policy["level"] = args.dns_policy
    else:
        policy = load_dns_policy(config_path) if config_path.exists() else None

    custom_names = {
        (config_path.parent / rel).resolve(): name for name, rel in CUSTOM_LIST_FILES
    }

    merged = LintReport()
    for rules_path in existing:
        text = rules_path.read_text(encoding="utf-8", errors="replace")
        custom_name = custom_names.get(rules_path.resolve())
        if custom_name:
            is_allow = custom_name == "LocalAllowlist"
            text = "\n".join(
                norm
                for raw in text.splitlines()
                if (norm := _normalize_custom_line(raw, is_allow)) is not None
            )
        report = lint_text(text, source=str(rules_path), policy=policy)
        for issue in report.issues:
            LOG.info(
                "%s:%d: %s: %s | %s",
                rules_path,
                issue.line,
                issue.level,
                issue.message,
                issue.text,
            )
        merged.issues.extend(report.issues)
        merged.dns_domains.extend(report.dns_domains)
        merged.browser_rules.extend(report.browser_rules)

    merged.dns_domains = sorted(set(merged.dns_domains))
    LOG.info(
        "lint 完成: %d error / %d warning; DNS 域名 %d 条, 浏览器规则 %d 条",
        len(merged.errors),
        len(merged.warnings),
        len(merged.dns_domains),
        len(merged.browser_rules),
    )
    if args.split_dir:
        split_dir = Path(args.split_dir)
        split_dir.mkdir(parents=True, exist_ok=True)
        dns_path = split_dir / "lint_dns_domains.txt"
        browser_path = split_dir / "lint_browser_rules.txt"
        dns_path.write_text(
            "# lint 拆分：可安全进入 DNS 的整域阻断域名\n"
            + "".join(f"{d}\n" for d in merged.dns_domains),
            encoding="utf-8",
        )
        browser_path.write_text(
            "# lint 拆分：仅浏览器扩展可用的规则\n"
            + "".join(f"{r}\n" for r in merged.browser_rules),
            encoding="utf-8",
        )
        LOG.info("拆分产物: %s, %s", dns_path, browser_path)
    if merged.errors or (args.strict and merged.warnings):
        return 2
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adblock-rule-collection",
        description="合并、去重、生成 Adblock / DNS 过滤器规则",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="下载上游列表并生成过滤器")
    p_build.add_argument(
        "--config", default="config/sources.yaml", help="上游列表配置文件"
    )
    p_build.add_argument("--out", default="dist", help="输出目录")
    p_build.add_argument("--no-cache", action="store_true", help="禁用下载缓存")
    p_build.add_argument(
        "--no-stage-cache",
        action="store_true",
        help="禁用阶段解析缓存（每次重新解析上游）",
    )
    p_build.add_argument("--offline", action="store_true", help="离线模式，仅使用缓存")
    p_build.add_argument(
        "--no-dns", action="store_true", help="不生成 DNS/hosts/domains 文件"
    )
    p_build.add_argument(
        "--no-rulesets",
        action="store_true",
        help="不生成连接层规则集（mihomo / sing-box / Surge / Quantumult X）",
    )
    p_build.add_argument(
        "--redundant",
        action="store_true",
        help="[兼容保留] 旧版冗余域名消除；增强折叠开启时自动忽略",
    )
    p_build.add_argument(
        "--alias-normalize",
        action="store_true",
        default=True,
        help="[默认开启] 归一化等价选项别名（xmlhttprequest/doc/ghide/elemhide）并折叠重复规则",
    )
    p_build.add_argument(
        "--no-alias-normalize",
        dest="alias_normalize",
        action="store_false",
        default=argparse.SUPPRESS,
        help="关闭别名归一化",
    )
    p_build.add_argument(
        "--resolve-conflicts",
        action="store_true",
        default=True,
        help="[默认开启] 对整域目标仲裁阻断与例外（例外 > $important > 普通阻断），记录 arbitration.json",
    )
    p_build.add_argument(
        "--no-resolve-conflicts",
        dest="resolve_conflicts",
        action="store_false",
        default=argparse.SUPPRESS,
        help="关闭冲突仲裁",
    )
    p_build.add_argument(
        "--per-rule-classify",
        action="store_true",
        default=True,
        help="[默认开启] 逐条多信号分类：安全信号与泛化提示可覆盖上游类别提示",
    )
    p_build.add_argument(
        "--no-per-rule-classify",
        dest="per_rule_classify",
        action="store_false",
        default=argparse.SUPPRESS,
        help="关闭逐条多信号分类",
    )
    p_build.add_argument(
        "--domain-fold",
        action="store_true",
        default=True,
        help="[默认开启] 折叠被祖先域整域拦截覆盖的子域规则，记录 domain_fold.json",
    )
    p_build.add_argument(
        "--no-domain-fold",
        dest="domain_fold",
        action="store_false",
        default=argparse.SUPPRESS,
        help="关闭域名层级折叠",
    )
    p_build.add_argument(
        "--split-by-category", action="store_true", help="split output by category"
    )
    p_build.add_argument(
        "--dns-policy",
        default=None,
        choices=["all", "safe", "strict-safe"],
        help="DNS 安全分级策略（覆盖 config 中的 dns_policy.level）",
    )
    p_build.add_argument(
        "--navigation-domains",
        action="store_true",
        default=True,
        help="[默认开启] 允许 $popup/$document 等导航修饰放大为整域拦截（confidence=0.8）",
    )
    p_build.add_argument(
        "--no-navigation-domains",
        dest="navigation_domains",
        action="store_false",
        default=argparse.SUPPRESS,
        help="关闭导航修饰的整域放大，仅保留纯域名/整域语义规则",
    )
    p_build.add_argument(
        "--dry-run",
        action="store_true",
        help="只执行全部阶段与不变量校验，不写入任何产物",
    )
    p_build.add_argument(
        "--baseline",
        default=None,
        help="与给定产物目录逐字节比对（忽略 sources_status.json 的 generated_at）",
    )
    p_build.add_argument(
        "--history",
        action="store_true",
        help="启用规则过期跟踪：更新 .cache/build/rule_history.tsv 并输出 maintenance_report.json",
    )
    p_build.add_argument(
        "--stale-days",
        type=_positive_int,
        default=30,
        help="规则连续缺席多少天后计入维护报告的过期清单（正整数，默认 30，需配合 --history）",
    )
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

    p_lint = sub.add_parser(
        "lint", help="校验规则语法/冲突，并拆分 DNS 域名与浏览器规则"
    )
    p_lint.add_argument(
        "--rules",
        nargs="+",
        default=[
            "config/local_rules.txt",
            "config/lists/blocklist.txt",
            "config/lists/allowlist.txt",
        ],
        help="待校验的规则文件（可多个；默认校验本地增强与自定义黑/白名单）",
    )
    p_lint.add_argument(
        "--config", default="config/sources.yaml", help="读取 dns_policy 的配置文件"
    )
    p_lint.add_argument(
        "--dns-policy",
        default=None,
        choices=["all", "safe", "strict-safe"],
        help="DNS 分层策略（覆盖 config 中的 dns_policy.level）",
    )
    p_lint.add_argument(
        "--split-dir", default=None, help="把 DNS 域名与浏览器规则分别写入该目录"
    )
    p_lint.add_argument(
        "--strict", action="store_true", help="警告也视为失败（退出码 2）"
    )
    p_lint.set_defaults(func=lint_cmd)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        sys.exit(args.func(args))
    except BuildError as exc:
        LOG.error("内部一致性失败: %s", exc)
        sys.exit(3)


if __name__ == "__main__":
    sys.exit(main())
