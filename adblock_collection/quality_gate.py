"""质量门禁与构建变化检测。

在每次构建后执行，基于当前产物与上一版（dist/previous_metrics.json）对比，检测异常
突变，防止「某次上游更新把大站误封、规则数暴增、DNS 数量暴涨」等风险被悄悄发布。

门禁检查项：
1. 单源突然减少 > source_drop_percent
2. 总规则突然增加 > total_rule_growth_percent
3. DNS/Hosts 域名数突然增加 > dns_growth_percent
4. 根域级规则（阻断裸域名）数量是否异常

任一触发即 FAIL，build 退出码非零，阻止发布。同时输出 build_report.json，
记录本次与上次的关键指标与增量，便于审计。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .rules import Rule


@dataclass
class Metrics:
    total_rules: int = 0
    dns_domains: int = 0
    source_counts: dict[str, int] = field(default_factory=dict)
    category_counts: dict[str, int] = field(default_factory=dict)
    root_domain_blocks: int = 0

    def to_dict(self) -> dict:
        return {
            "total_rules": self.total_rules,
            "dns_domains": self.dns_domains,
            "source_counts": self.source_counts,
            "category_counts": self.category_counts,
            "root_domain_blocks": self.root_domain_blocks,
        }


@dataclass
class GateResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_failure(self, msg: str) -> None:
        self.failures.append(msg)
        self.passed = False


# 阈值默认值（均可通过 config 的 quality_gate 段覆盖）
DEFAULT_THRESHOLDS = {
    "total_rule_growth_percent": 20.0,
    "dns_growth_percent": 15.0,
    "source_drop_percent": 50.0,
    "category_growth_percent": 30.0,
    "max_root_domain_blocks": 0,  # 0 表示不检查；>0 时根域阻断数超过即失败
}


def collect_metrics(rules: list[Rule], dns_domains: int, source_counts: dict, category_counts: dict) -> Metrics:
    """从构建产物收集关键指标。"""
    root_blocks = 0
    for r in rules:
        if (
            r.kind == "network"
            and not r.is_exception
            and r.domains
            and len(r.domains) == 1
            and r.domains[0].count(".") == 1
        ):
            root_blocks += 1
    return Metrics(
        total_rules=len(rules),
        dns_domains=dns_domains,
        source_counts=dict(source_counts),
        category_counts=dict(category_counts),
        root_domain_blocks=root_blocks,
    )


def _pct_change(cur: float, prev: float) -> float:
    if prev <= 0:
        return 0.0 if cur == 0 else 100.0
    return (cur - prev) / prev * 100.0


def load_thresholds(config_path: Path) -> dict:
    import yaml

    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    raw = data.get("quality_gate", {}) or {}
    spec = dict(DEFAULT_THRESHOLDS)
    for k in DEFAULT_THRESHOLDS:
        if k in raw:
            spec[k] = float(raw[k])
    return spec


def evaluate(metrics: Metrics, prev: Optional[Metrics], thresholds: dict) -> GateResult:
    res = GateResult(passed=True)

    # 1. 单源突然减少
    if prev is not None:
        for src, cnt in prev.source_counts.items():
            now = metrics.source_counts.get(src, 0)
            if cnt > 0 and _pct_change(now, cnt) <= -thresholds["source_drop_percent"]:
                res.add_failure(
                    f"上游 {src} 规则数骤降 {abs(_pct_change(now, cnt)):.1f}% ({cnt} -> {now})"
                )

        # 2. 总规则增长
        g = _pct_change(metrics.total_rules, prev.total_rules)
        if g > thresholds["total_rule_growth_percent"]:
            res.add_failure(
                f"总规则数增长 {g:.1f}% 超过阈值 {thresholds['total_rule_growth_percent']:.0f}% "
                f"({prev.total_rules} -> {metrics.total_rules})"
            )

        # 3. DNS 增长
        dg = _pct_change(metrics.dns_domains, prev.dns_domains)
        if dg > thresholds["dns_growth_percent"]:
            res.add_failure(
                f"DNS 域名数增长 {dg:.1f}% 超过阈值 {thresholds['dns_growth_percent']:.0f}% "
                f"({prev.dns_domains} -> {metrics.dns_domains})"
            )

        # 4. 分类增长（任一类别突增）
        for cat, cnt in metrics.category_counts.items():
            pc = prev.category_counts.get(cat, 0)
            cg = _pct_change(cnt, pc)
            if pc > 0 and cg > thresholds["category_growth_percent"]:
                res.warnings.append(
                    f"类别 {cat} 增长 {cg:.1f}% ({pc} -> {cnt})"
                )

    # 5. 根域阻断数
    if thresholds["max_root_domain_blocks"] > 0 and metrics.root_domain_blocks > thresholds["max_root_domain_blocks"]:
        res.add_failure(
            f"根域级阻断规则 {metrics.root_domain_blocks} 超过阈值 {int(thresholds['max_root_domain_blocks'])}"
        )

    return res


def load_previous(output_dir: Path) -> Optional[Metrics]:
    path = output_dir / "previous_metrics.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return Metrics(
        total_rules=data.get("total_rules", 0),
        dns_domains=data.get("dns_domains", 0),
        source_counts=data.get("source_counts", {}) or {},
        category_counts=data.get("category_counts", {}) or {},
        root_domain_blocks=data.get("root_domain_blocks", 0),
    )


def save_previous(metrics: Metrics, output_dir: Path) -> None:
    path = output_dir / "previous_metrics.json"
    path.write_text(json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def write_build_report(output_dir: Path, metrics: Metrics, prev: Optional[Metrics], gate: GateResult) -> dict:
    diff = {
        "total_rules": _diff_value(metrics.total_rules, prev.total_rules if prev else None),
        "dns_domains": _diff_value(metrics.dns_domains, prev.dns_domains if prev else None),
    }
    report = {
        "passed": gate.passed,
        "failures": gate.failures,
        "warnings": gate.warnings,
        "metrics": metrics.to_dict(),
        "diff": diff,
        "previous": prev.to_dict() if prev else None,
    }
    path = output_dir / "build_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _diff_value(cur: int, prev: Optional[int]) -> dict:
    if prev is None:
        return {"current": cur, "previous": None, "delta": None, "percent": None}
    return {
        "current": cur,
        "previous": prev,
        "delta": cur - prev,
        "percent": round(_pct_change(cur, prev), 2),
    }
