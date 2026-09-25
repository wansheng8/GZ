"""把每次构建生成的规则条数同步到 ``.monkeycode/MEMORY.md`` 的指标快照区块。

上游列表每日更新，规则条数会持续变化。为了让每次构建产出多少条规则都能直接在
MEMORY.md 看到，本模块在构建末尾把 ``dist`` 的关键计数写入一个由 HTML 注释标记
包围的区块：最新的记录置顶，仅保留最近 ``KEEP`` 条，避免文件无限增长。

区块由标记界定，脚本幂等：重复运行只更新区块内容，不影响 MEMORY.md 的其他记忆条目。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MEMORY_PATH = Path(".monkeycode/MEMORY.md")
START = "<!-- build-metrics:start -->"
END = "<!-- build-metrics:end -->"
KEEP = 10

NETWORK = "adblock_collection_full_browser_network.txt"
COSMETIC = "adblock_collection_full_cosmetic.txt"
UBO_ENHANCE = "adblock_collection_ubo_enhance.txt"

_COLUMNS = [
    "生成时间(UTC)",
    "提交",
    "结果",
    "总规则数",
    "DNS 域名",
    "网络拦截",
    "元素隐藏",
    "uBO 增强",
]
_TABLE_HEADER = "| " + " | ".join(_COLUMNS) + " |"
_TABLE_SEP = "| " + " | ".join(["---"] * len(_COLUMNS)) + " |"
_HEADER = "## 构建指标快照（CI 自动生成）"
_NOTE = (
    f"> 由 `python -m adblock_collection.memory_metrics` 在每次构建后更新，"
    f"最新记录置顶、仅保留最近 {KEEP} 次；数值取自 `dist/build_report.json` "
    "与 `dist/manifest.json`。"
)
# 标记必须是「独占一行」的 HTML 注释；行内的同名文本（例如记忆条目里的说明）
# 不会被误判为区块边界。
_START_RE = re.compile(rf"^{re.escape(START)}\s*$", re.MULTILINE)
_END_RE = re.compile(rf"^{re.escape(END)}\s*$", re.MULTILINE)


def _short_sha() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha[:7]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or "-"
    except (subprocess.SubprocessError, OSError):
        return "-"


def build_row(out_dir: Path, now: datetime | None = None, sha: str = "-") -> str:
    """按 ``out_dir`` 的产物计数渲染一行 Markdown 表格记录。"""
    report = json.loads((out_dir / "build_report.json").read_text(encoding="utf-8"))
    metrics = report.get("metrics", {})
    counts = {}
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        counts = {
            x["file"]: x.get("rules", 0) for x in manifest.get("generated_files", [])
        }
    now = now or datetime.now(timezone.utc)
    cells = [
        now.strftime("%Y-%m-%d %H:%M"),
        f"`{sha}`",
        "通过" if report.get("passed") else "失败",
        f"{metrics.get('total_rules', 0):,}",
        f"{metrics.get('dns_domains', 0):,}",
        f"{counts.get(NETWORK, 0):,}",
        f"{counts.get(COSMETIC, 0):,}",
        f"{counts.get(UBO_ENHANCE, 0):,}",
    ]
    return "| " + " | ".join(cells) + " |"


def _data_rows(text: str) -> list[str]:
    """从区块文本中取出数据行（去掉表头、分隔线与标记行）。"""
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        if line == _TABLE_HEADER or line.startswith("| ---"):
            continue
        if "生成时间" in line:
            continue
        rows.append(line)
    return rows


def _render_block(rows: list[str]) -> str:
    lines = [START, _HEADER, "", _NOTE, "", _TABLE_HEADER, _TABLE_SEP, *rows, END]
    return "\n".join(lines)


def update_memory(path: Path, row: str, keep: int = KEEP) -> None:
    """把 ``row`` 置顶写入 ``path`` 的指标快照区块，并裁剪到 ``keep`` 条。"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    start = _START_RE.search(text)
    end = _END_RE.search(text)
    if start and end and start.end() < end.start():
        pre = text[: start.start()]
        block = text[start.end() : end.start()]
        post = text[end.end() :]
        rows = _data_rows(block)
        if not rows or rows[0] != row:
            rows.insert(0, row)
        rows = rows[:keep]
        text = f"{pre}{_render_block(rows)}{post}"
    else:
        block = _render_block([row][:keep])
        text = f"{text.rstrip()}\n\n{block}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    out_dir = Path.cwd() / "dist"
    row = build_row(out_dir, sha=_short_sha())
    update_memory(Path.cwd() / MEMORY_PATH, row)
    print(f"MEMORY.md 构建指标已更新: {row}")


if __name__ == "__main__":
    main()
