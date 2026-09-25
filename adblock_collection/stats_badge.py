"""从 dist 产物同步 README 徽章与 assets/stats.svg 的统计数字。

上游列表每日更新，产物规则数会持续变化。若徽章数字写死在 README 与 SVG 中，
就会与 dist 真实值逐渐偏离。本模块在构建流程末尾按 manifest 重新渲染这些数字，
使展示值与产物始终一致。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

FULL = "adblock_collection_full.txt"
DNS = "adblock_collection_full_dns.txt"
KIND_STATS = "adblock_collection_full.stats.json"

# README 规则类型构成表的自动同步区间（HTML 注释不影响渲染）。
_KIND_START = "<!-- kind-stats:start -->"
_KIND_END = "<!-- kind-stats:end -->"

# README 按类别订阅表的自动同步区间。
_CATEGORY_START = "<!-- category-stats:start -->"
_CATEGORY_END = "<!-- category-stats:end -->"

# 类别订阅文件的 raw 地址模板（与 README 订阅中心保持一致）。
_CATEGORY_URL = (
    "https://raw.githubusercontent.com/wansheng8/GZ/main/dist/"
    "adblock_collection_full_{cat}.txt"
)

# 已知规则的固定展示顺序与归属层；未知类型追加在末尾，归属层留空。
_KIND_ORDER = ("network", "css", "scriptlet", "html", "js")
_KIND_LAYERS = {
    "network": "网络拦截（DNS 从中提取纯域名）",
    "css": "元素隐藏",
    "scriptlet": "元素隐藏",
    "html": "元素隐藏",
    "js": "元素隐藏",
}


def load_counts(out_dir: Path) -> tuple[int, int, int]:
    """返回 (完整版规则数, DNS 域名数, 上游源数)。"""
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    counts = {x["file"]: x.get("rules", 0) for x in manifest["generated_files"]}
    status = json.loads((out_dir / "sources_status.json").read_text(encoding="utf-8"))
    return counts[FULL], counts[DNS], int(status.get("total_sources", 0))


def load_kinds(out_dir: Path) -> dict[str, int]:
    """读取完整版规则的类型分布；stats 缺失时返回空字典（不触碰 README）。"""
    path = out_dir / KIND_STATS
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in data.get("by_kind", {}).items()}


def load_categories(out_dir: Path) -> dict[str, int]:
    """读取完整版的类别分布；stats 缺失时返回空字典（不触碰 README）。"""
    path = out_dir / KIND_STATS
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(k): int(v)
        for k, v in (data.get("by_category") or {}).items()
        if int(v) > 0
    }



def _url_encode(n: int) -> str:
    return f"{n:,}".replace(",", "%2C")


def sync_readme(path: Path, total: int, dns: int, sources: int) -> None:
    values = {"Total_Rules": total, "DNS_Domains": dns}
    text = path.read_text(encoding="utf-8")
    for label, value in values.items():
        text = re.sub(
            rf"({label}-)[^-\s]+",
            lambda m, v=value: m.group(1) + _url_encode(v),
            text,
        )
    text = re.sub(r"(Upstream-)\d+(?=_sources)", lambda m: m.group(1) + str(sources), text)
    text = re.sub(
        r'(alt=")[0-9,]+( rules · )[0-9,]+( domains · )\d+( sources)',
        lambda m: (
            f"{m.group(1)}{total:,}{m.group(2)}{dns:,}{m.group(3)}{sources}{m.group(4)}"
        ),
        text,
    )
    path.write_text(text, encoding="utf-8")


def sync_svg(path: Path, total: int, dns: int, sources: int) -> None:
    labels = {"FULL RULES": total, "DNS DOMAINS": dns, "UPSTREAM": sources}
    text = path.read_text(encoding="utf-8")

    def repl(match: re.Match) -> str:
        value, label = match.group(2), match.group(4)
        if label in labels:
            value = f"{labels[label]:,}"
        return f"{match.group(1)}{value}{match.group(3)}{label}{match.group(5)}"

    text = re.sub(
        r'(font-size="40"[^>]*>)([^<]*)(</text>\s*<text[^>]*>)([^<]*)(</text>)',
        repl,
        text,
    )
    path.write_text(text, encoding="utf-8")


def _render_kind_table(kinds: dict[str, int]) -> str:
    order = [k for k in _KIND_ORDER if k in kinds]
    order += sorted(k for k in kinds if k not in _KIND_ORDER)
    lines = ["| 类型 | 数量 | 归属层 |", "| :--- | ---: | :--- |"]
    for kind in order:
        layer = _KIND_LAYERS.get(kind, "—")
        lines.append(f"| {kind} | {kinds[kind]:,} | {layer} |")
    lines.append(f"| **合计** | {sum(kinds.values()):,} | — |")
    return "\n".join(lines)


def sync_kind_table(path: Path, kinds: dict[str, int]) -> None:
    """重写 README 中 ``kind-stats`` 标记区间的类型构成表；无标记或无数据时跳过。"""
    if not kinds:
        return
    text = path.read_text(encoding="utf-8")
    start = text.find(_KIND_START)
    end = text.find(_KIND_END)
    if start == -1 or end == -1 or end < start:
        return
    block = f"{_KIND_START}\n{_render_kind_table(kinds)}\n{_KIND_END}"
    text = text[:start] + block + text[end + len(_KIND_END) :]
    path.write_text(text, encoding="utf-8")


def _render_category_table(categories: dict[str, int]) -> str:
    order = sorted(categories, key=lambda c: (-categories[c], c))
    lines = ["| 类别 | 数量 | 订阅 |", "| :--- | ---: | :--- |"]
    for cat in order:
        count = categories[cat]
        if cat == "whitelist":
            lines.append(f"| whitelist | {count:,} | 例外规则（仅供审计） |")
        else:
            lines.append(
                f"| {cat} | {count:,} | [订阅]({_CATEGORY_URL.format(cat=cat)}) |"
            )
    lines.append(f"| **合计** | {sum(categories.values()):,} | — |")
    return "\n".join(lines)


def sync_category_table(path: Path, categories: dict[str, int]) -> None:
    """重写 README 中 ``category-stats`` 标记区间的按类别订阅表；无标记或无数据时跳过。"""
    if not categories:
        return
    text = path.read_text(encoding="utf-8")
    start = text.find(_CATEGORY_START)
    end = text.find(_CATEGORY_END)
    if start == -1 or end == -1 or end < start:
        return
    block = f"{_CATEGORY_START}\n{_render_category_table(categories)}\n{_CATEGORY_END}"
    text = text[:start] + block + text[end + len(_CATEGORY_END) :]
    path.write_text(text, encoding="utf-8")


def sync(root: Path) -> None:
    total, dns, sources = load_counts(root / "dist")
    kinds = load_kinds(root / "dist")
    categories = load_categories(root / "dist")
    sync_readme(root / "README.md", total, dns, sources)
    sync_kind_table(root / "README.md", kinds)
    sync_category_table(root / "README.md", categories)
    sync_svg(root / "assets" / "stats.svg", total, dns, sources)


def main() -> None:
    sync(Path.cwd())


if __name__ == "__main__":
    main()
