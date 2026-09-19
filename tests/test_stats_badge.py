import json
from pathlib import Path

from adblock_collection import stats_badge

README = """\
[![Rules](https://img.shields.io/badge/Total_Rules-1%2C000-ff00e5)](dist/a.txt)
[![DNS](https://img.shields.io/badge/DNS_Domains-500-00f0ff)](dist/b.txt)
[![Sources](https://img.shields.io/badge/Upstream-10_sources-9d00ff)](config/sources.yaml)
<img src="assets/stats.svg" alt="1,000 rules · 500 domains · 10 sources · 1万+ deduplicated"/>
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


def _write(root: Path, total: int, dns: int, sources: int) -> None:
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
    (root / "README.md").write_text(README, encoding="utf-8")
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "stats.svg").write_text(SVG, encoding="utf-8")


def test_sync_updates_readme_and_svg(tmp_path):
    _write(tmp_path, total=779485, dns=541600, sources=60)

    stats_badge.sync(tmp_path)

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "Total_Rules-779%2C485-" in readme
    assert "DNS_Domains-541%2C600-" in readme
    assert "Upstream-60_sources" in readme
    assert 'alt="779,485 rules · 541,600 domains · 60 sources' in readme

    svg = (tmp_path / "assets" / "stats.svg").read_text(encoding="utf-8")
    assert ">779,485</text>" in svg
    assert ">541,600</text>" in svg
    assert ">60</text>" in svg
    assert ">1万+</text>" in svg


def test_sync_is_idempotent(tmp_path):
    _write(tmp_path, total=1234, dns=567, sources=3)

    stats_badge.sync(tmp_path)
    first = (tmp_path / "README.md").read_text(encoding="utf-8")
    svg_first = (tmp_path / "assets" / "stats.svg").read_text(encoding="utf-8")
    stats_badge.sync(tmp_path)

    assert (tmp_path / "README.md").read_text(encoding="utf-8") == first
    assert (tmp_path / "assets" / "stats.svg").read_text(encoding="utf-8") == svg_first
