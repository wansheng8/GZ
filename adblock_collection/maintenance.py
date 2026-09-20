"""需求扩展：规则过期/维护跟踪。

广告域名会随时间失效，长期未出现的规则应被清理。本模块在本地/连续构建场景下，
把每条规则的归一化指纹与「最近一次出现日期」记录在
``.cache/build/rule_history.tsv``（不入库），并在规则连续缺席超过 ``stale_days``
时输出 ``maintenance_report.json``。

该跟踪默认关闭（``build --history`` 开启）：CI 每次全新 checkout，没有历史可比，
也不希望为维护统计增加构建开销。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from .rules import Rule

LOG = logging.getLogger(__name__)

DEFAULT_HISTORY_PATH = Path(".cache/build/rule_history.tsv")
REPORT_NAME = "maintenance_report.json"
DEFAULT_STALE_DAYS = 30
DEFAULT_RETENTION_DAYS = 120
MAX_REPORT_SAMPLES = 5000


def load_history(path: Path = DEFAULT_HISTORY_PATH) -> dict[str, str]:
    """读取 ``norm -> 最近出现日期(YYYY-MM-DD)``；文件缺失时返回空表。"""
    if not path.exists():
        return {}
    history: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    for line in text.splitlines():
        last_seen, _, norm = line.partition("\t")
        if last_seen and norm:
            history[norm] = last_seen
    return history


def save_history(history: dict[str, str], path: Path = DEFAULT_HISTORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{last_seen}\t{norm}" for norm, last_seen in sorted(history.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _age_days(last_seen: str, today: date) -> int:
    try:
        seen = date.fromisoformat(last_seen)
    except ValueError:
        return 0
    return (today - seen).days


def update_history(
    rules: Iterable[Rule],
    *,
    today: date | None = None,
    stale_days: int = DEFAULT_STALE_DAYS,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    path: Path = DEFAULT_HISTORY_PATH,
) -> dict:
    """更新规则历史，返回 ``{"stale": [...], "tracked": n, ...}``。

    - 本批出现的规则：``last_seen`` 记为今天；
    - 本批缺席且缺席天数 >= ``stale_days``：进入 stale 清单；
    - 缺席天数 >= ``retention_days`` 的条目被清除，避免历史无限膨胀。
    """
    today = today or date.today()
    iso = today.isoformat()
    history = load_history(path)
    current = {r.norm for r in rules if r.norm}

    for norm in current:
        history[norm] = iso

    stale = sorted(
        norm
        for norm, last_seen in history.items()
        if norm not in current and _age_days(last_seen, today) >= stale_days
    )
    retained = {
        norm: last_seen
        for norm, last_seen in history.items()
        if _age_days(last_seen, today) < retention_days
    }
    save_history(retained, path)
    return {
        "today": iso,
        "tracked": len(retained),
        "current": len(current),
        "stale": stale,
        "stale_days": stale_days,
        "retention_days": retention_days,
    }


def write_maintenance_report(output_dir: Path, result: dict) -> dict:
    """把维护结果写入 ``output_dir/maintenance_report.json``。"""
    stale = result.get("stale", [])
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "today": result.get("today", date.today().isoformat()),
        "tracked_rules": result.get("tracked", 0),
        "current_rules": result.get("current", 0),
        "stale_count": len(stale),
        "stale_days": result.get("stale_days", DEFAULT_STALE_DAYS),
        "retention_days": result.get("retention_days", DEFAULT_RETENTION_DAYS),
        "stale_sample": stale[:MAX_REPORT_SAMPLES],
    }
    (output_dir / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
