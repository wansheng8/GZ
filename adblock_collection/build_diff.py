"""需求 8：相邻两次构建的规则差异。

逐条差异在本地/连续构建场景下最有价值：把上一批规则的归一化指纹保存在
``.cache/build/previous_rules.txt``（与 ``rules.jsonl`` 同目录，均不入库），
本次构建与之比对，输出 ``dist/build_diff.txt``：

- ``+ norm``：本次新增规则
- ``- norm``：本次移除规则

缺少上一批指纹（如 CI 全新 checkout）时跳过并记录日志；此时仍可通过
``build_report.json#diff.sources`` 查看每个上游源的贡献变化与质量门禁告警。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path

from .rules import Rule, parse_line

LOG = logging.getLogger(__name__)

DEFAULT_FINGERPRINT_PATH = Path(".cache/build/previous_rules.txt")
DIFF_NAME = "build_diff.txt"
REVIEW_NAME = "new_domain_review.json"

# 单个方向最多写出的明细行数；超出时在文件末尾注明实际条数，避免异常变更产生超大文件
MAX_LINES_PER_SIDE = 20000

# 复核清单最多保留的条目数。
MAX_REVIEW_ENTRIES = 5000

# 常见的「两级公共后缀」（ccTLD 的第二层），用于近似估算可注册域。
_TWO_LEVEL_SUFFIXES = frozenset(
    {
        "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "net.uk", "sch.uk",
        "com.cn", "net.cn", "org.cn", "gov.cn", "edu.cn", "ac.cn",
        "com.au", "net.au", "org.au", "edu.au", "gov.au",
        "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp",
        "co.kr", "or.kr", "ne.kr", "go.kr",
        "co.in", "net.in", "org.in", "gov.in", "ac.in",
        "com.br", "net.br", "org.br", "gov.br",
        "com.tw", "org.tw", "net.tw",
        "com.hk", "org.hk", "net.hk", "edu.hk", "gov.hk",
        "com.sg", "org.sg", "net.sg", "edu.sg", "gov.sg",
        "com.mx", "com.ar", "com.co", "com.pe", "com.ve", "com.ec",
        "com.uy", "com.bo", "com.py", "com.do", "com.gt", "com.sv",
        "com.hn", "com.ni", "com.pa",
        "com.tr", "com.pl", "com.ua", "co.il", "com.my", "com.vn",
        "com.ph", "com.pk", "com.sa", "com.eg", "com.ng",
        "co.nz", "co.za", "co.th", "co.id",
    }
)


def fingerprint(rules: Iterable[Rule]) -> list[str]:
    """规则集的归一化指纹：去重并按字典序排序的 ``norm`` 列表。"""
    return sorted({r.norm for r in rules if r.norm})


def load_previous_fingerprint(
    path: Path = DEFAULT_FINGERPRINT_PATH,
) -> set[str] | None:
    """读取上一批规则指纹；文件不存在时返回 ``None``。"""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return {line for line in text.splitlines() if line}


def save_fingerprint(
    rules: Iterable[Rule], path: Path = DEFAULT_FINGERPRINT_PATH
) -> None:
    """保存本批规则指纹，供下次构建比对。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(fingerprint(rules)) + "\n", encoding="utf-8")


def diff_fingerprint(
    previous: set[str], rules: Iterable[Rule]
) -> tuple[list[str], list[str]]:
    """返回 ``(新增, 移除)`` 两条排序后的归一化规则清单。"""
    current = set(fingerprint(rules))
    return sorted(current - previous), sorted(previous - current)


def write_build_diff(
    output_dir: Path, added: list[str], removed: list[str]
) -> dict:
    """把新增/移除规则写入 ``output_dir/build_diff.txt``，返回汇总计数。"""
    lines = [
        "# 相邻两次构建规则差异（本地/连续构建；CI 全新 checkout 时无上一批指纹）",
        f"# 新增 {len(added)} 条, 移除 {len(removed)} 条",
        "",
    ]
    lines.append(f"## 新增 ({len(added)})")
    lines.extend(f"+ {norm}" for norm in added[:MAX_LINES_PER_SIDE])
    if len(added) > MAX_LINES_PER_SIDE:
        lines.append(f"# ... 其余 {len(added) - MAX_LINES_PER_SIDE} 条省略")
    lines.append("")
    lines.append(f"## 移除 ({len(removed)})")
    lines.extend(f"- {norm}" for norm in removed[:MAX_LINES_PER_SIDE])
    if len(removed) > MAX_LINES_PER_SIDE:
        lines.append(f"# ... 其余 {len(removed) - MAX_LINES_PER_SIDE} 条省略")
    lines.append("")
    (output_dir / DIFF_NAME).write_text("\n".join(lines), encoding="utf-8")
    return {"added": len(added), "removed": len(removed)}


_RISK_ORDER = {"critical": 3, "high": 2, "low": 1}


def registrable_domain(domain: str) -> str:
    """近似估算可注册域（eTLD+1）：不依赖 Public Suffix List 的启发式。

    处理常见的两级 ccTLD（``co.uk`` / ``com.cn`` 等），其余按「末两段」处理。
    """
    labels = domain.split(".")
    if len(labels) <= 2:
        return domain
    if ".".join(labels[-2:]).lower() in _TWO_LEVEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _allow_suffixes(allow_domains: Iterable[str]) -> set[str]:
    """把 allow 清单展开为其全部祖先后缀，用于判断新阻断是否覆盖放行域名。"""
    suffixes: set[str] = set()
    for domain in allow_domains:
        parts = domain.split(".")
        for i in range(len(parts)):
            suffixes.add(".".join(parts[i:]))
    return suffixes


def _whole_domain_block(norm: str) -> str | None:
    """若归一化规则是单域名整域阻断，返回该域名，否则返回 None。"""
    from .arbitrate import _is_whole_domain_block

    rule = parse_line(norm, source="build_diff")
    if rule is None or not _is_whole_domain_block(rule):
        return None
    return rule.domains[0]


def review_new_domains(
    output_dir: Path,
    added: Iterable[str],
    allow_domains: Iterable[str] = (),
) -> dict:
    """对本次新增规则做「新出现整域阻断」复核，返回待人工确认清单。

    仅关注会把整个域名（含子域）加入拦截集合的新规则。风险分级：

    - ``critical``：新阻断覆盖了 ``config/false_positives.yaml`` allow 清单中的域名
      （可能直接误杀大站，必须人工确认）；
    - ``high``：阻断落在可注册域本身（站点级整域封锁，误杀面最大）；
    - ``low``：阻断落在子域（影响面较窄）。

    ``short_label`` 提示二级标签较短（品牌型域名，通常热度较高）。
    """
    allow_suffixes = _allow_suffixes(allow_domains)
    entries: dict[str, dict] = {}
    for norm in added:
        domain = _whole_domain_block(norm)
        if not domain:
            continue
        reg = registrable_domain(domain)
        risk = "high" if domain == reg else "low"
        if domain in allow_suffixes:
            risk = "critical"
        rec = entries.get(domain)
        if rec is None:
            rec = {
                "domain": domain,
                "registrable": reg,
                "risk": risk,
                "short_label": len(reg.split(".")[0]) <= 4,
                "rules": [],
            }
            entries[domain] = rec
        elif _RISK_ORDER[risk] > _RISK_ORDER[rec["risk"]]:
            rec["risk"] = risk
        rec["rules"].append(norm)

    items = sorted(
        entries.values(),
        key=lambda e: (-_RISK_ORDER[e["risk"]], e["domain"]),
    )
    by_risk = {"critical": 0, "high": 0, "low": 0}
    for item in items:
        by_risk[item["risk"]] += 1
    summary = {
        "total_new_domains": len(items),
        "by_risk": by_risk,
        "critical": [e["domain"] for e in items if e["risk"] == "critical"],
        "truncated": len(items) > MAX_REVIEW_ENTRIES,
        "entries": items[:MAX_REVIEW_ENTRIES],
    }
    (output_dir / REVIEW_NAME).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if by_risk["critical"]:
        LOG.warning(
            "新出现整域阻断覆盖 allow 清单域名 %d 个，需人工确认: %s",
            by_risk["critical"],
            summary["critical"][:5],
        )
    LOG.info(
        "新出现整域阻断复核: 共 %d 个（critical %d / high %d / low %d）-> %s",
        len(items),
        by_risk["critical"],
        by_risk["high"],
        by_risk["low"],
        REVIEW_NAME,
    )
    return summary
