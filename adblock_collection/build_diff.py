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

import logging
from collections.abc import Iterable
from pathlib import Path

from .rules import Rule

LOG = logging.getLogger(__name__)

DEFAULT_FINGERPRINT_PATH = Path(".cache/build/previous_rules.txt")
DIFF_NAME = "build_diff.txt"

# 单个方向最多写出的明细行数；超出时在文件末尾注明实际条数，避免异常变更产生超大文件
MAX_LINES_PER_SIDE = 20000


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
