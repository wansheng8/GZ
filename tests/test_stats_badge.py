import json
from pathlib import Path

from adblock_collection import stats_badge

README = """\
[![Rules](https://img.shields.io/badge/Total_Rules-1%2C000-ff00e5)](dist/a.txt)
[![DNS](https://img.shields.io/badge/DNS_Domains-500-00f0ff)](dist/b.txt)
[![Sources](https://img.shields.io/badge/Upstream-10_sources-9d00ff)](config/sources.yaml)
<img src="assets/stats.svg" alt="1,000 rules · 500 domains · 10 sources · 1万+ deduplicated"/>

<!-- kind-stats:start -->
| 类型 | 数量 | 归属层 |
| :--- | ---: | :--- |
| network | 0 | 网络拦截（DNS 从中提取纯域名） |
<!-- kind-stats:end -->

<!-- category-stats:start -->
| 类别 | 数量 | 订阅 |
| :--- | ---: | :--- |
| network | 0 | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_network.txt) |
<!-- category-stats:end -->
"""

SVG = """\
<svg>
  <text font-size="40" fill="#ff00e5">1,000</text>
  <text>FULL RULES</text>
  <text font-size="40" fill="#00f0ff">500</text>
  <text>DNS DOMAINS</text>
  <text font-size="40" fill="#9d00ff">10</text>
  <text>UPSTREAM</text>
  <text font-size="40" fill="#39ff14">1万+</text>
  <text>DEDUPLICATED</text>
</svg>
"""


def _write(
    root: Path,
    total: int,
    dns: int,
    sources: int,
    kinds: dict | None = None,
    categories: dict | None = None,
) -> None:
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "manifest.json").write_text(
        json.dumps(
            {
                "generated_files": [
                    {"file": stats_badge.FULL, "rules": total},
                    {"file": stats_badge.DNS, "rules": dns},
                ]
            }
        ),
        encoding="utf-8",
    )
    (dist / "sources_status.json").write_text(
        json.dumps({"total_sources": sources, "failed_sources": []}), encoding="utf-8"
    )
    (dist / stats_badge.KIND_STATS).write_text(
        json.dumps(
            {
                "by_kind": kinds if kinds is not None else {"network": 900, "css": 100},
                "by_category": categories
                if categories is not None
                else {"network": 900, "css": 100},
            }
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(README, encoding="utf-8")
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "stats.svg").write_text(SVG, encoding="utf-8")


def test_sync_updates_readme_and_svg(tmp_path):
    _write(
        tmp_path,
        total=779485,
        dns=541600,
        sources=60,
        kinds={"network": 779000, "css": 420, "scriptlet": 60, "html": 4, "js": 1},
    )

    stats_badge.sync(tmp_path)

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "Total_Rules-779%2C485-" in readme
    assert "DNS_Domains-541%2C600-" in readme
    assert "Upstream-60_sources" in readme
    assert 'alt="779,485 rules · 541,600 domains · 60 sources' in readme

    # 类型构成表按 by_kind 重写，合计等于各项之和
    assert "| network | 779,000 | 网络拦截（DNS 从中提取纯域名） |" in readme
    assert "| css | 420 | 元素隐藏 |" in readme
    assert "| scriptlet | 60 | 元素隐藏 |" in readme
    assert "| html | 4 | 元素隐藏 |" in readme
    assert "| js | 1 | 元素隐藏 |" in readme
    assert "| **合计** | 779,485 | — |" in readme

    svg = (tmp_path / "assets" / "stats.svg").read_text(encoding="utf-8")
    assert ">779,485</text>" in svg
    assert ">541,600</text>" in svg
    assert ">60</text>" in svg
    assert ">1万+</text>" in svg


def test_sync_kind_table_skips_without_markers(tmp_path):
    _write(tmp_path, total=10, dns=5, sources=1, kinds={"network": 10})
    readme = tmp_path / "README.md"
    readme.write_text("# no markers\n", encoding="utf-8")

    stats_badge.sync(tmp_path)

    assert readme.read_text(encoding="utf-8") == "# no markers\n"


def test_sync_is_idempotent(tmp_path):
    _write(tmp_path, total=1234, dns=567, sources=3)

    stats_badge.sync(tmp_path)
    first = (tmp_path / "README.md").read_text(encoding="utf-8")
    svg_first = (tmp_path / "assets" / "stats.svg").read_text(encoding="utf-8")
    stats_badge.sync(tmp_path)

    assert (tmp_path / "README.md").read_text(encoding="utf-8") == first
    assert (tmp_path / "assets" / "stats.svg").read_text(encoding="utf-8") == svg_first


def test_sync_category_table(tmp_path):
    _write(
        tmp_path,
        total=1007,
        dns=500,
        sources=1,
        categories={"network": 900, "css": 100, "whitelist": 7, "empty": 0},
    )

    stats_badge.sync(tmp_path)

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    # 按数量降序；whitelist 无订阅链接；零值类别不出现
    assert (
        "| network | 900 | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/"
        "dist/adblock_collection_full_network.txt) |" in readme
    )
    assert "| whitelist | 7 | 例外规则（仅供审计） |" in readme
    assert "| **合计** | 1,007 | — |" in readme
    assert "empty" not in readme


def test_sync_category_table_skips_without_markers(tmp_path):
    _write(tmp_path, total=10, dns=5, sources=1)
    readme = tmp_path / "README.md"
    readme.write_text("# no markers\n", encoding="utf-8")

    stats_badge.sync(tmp_path)

    assert readme.read_text(encoding="utf-8") == "# no markers\n"
