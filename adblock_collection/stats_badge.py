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


def load_counts(out_dir: Path) -> tuple[int, int, int]:
    """返回 (完整版规则数, DNS 域名数, 上游源数)。"""
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    counts = {x["file"]: x["rules"] for x in manifest["generated_files"]}
    status = json.loads((out_dir / "sources_status.json").read_text(encoding="utf-8"))
    return counts[FULL], counts[DNS], int(status.get("total_sources", 0))


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


def sync(root: Path) -> None:
    total, dns, sources = load_counts(root / "dist")
    sync_readme(root / "README.md", total, dns, sources)
    sync_svg(root / "assets" / "stats.svg", total, dns, sources)


def main() -> None:
    sync(Path.cwd())


if __name__ == "__main__":
    main()
