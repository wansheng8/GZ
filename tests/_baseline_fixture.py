"""M2 字节基线夹具：以固定小样本构建，供 golden 基线与重构后比对使用。

样本覆盖：整域阻断、路径规则、$important、$third-party、选项别名、badfilter、
例外、hosts 行、裸域名行、元素隐藏、脚本注入、安全类（malware/phishing）、父子域、
跨源重复。构建参数与 CI 一致（--split-by-category --redundant）。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

CONFIG_NAME = "sources.yaml"
CONFIG_TEXT = """name: fixture
sources:
  - name: FixtureAds
    url: https://fixture.invalid/ads.txt
    category: ads
  - name: FixturePrivacy
    url: https://fixture.invalid/privacy.txt
    category: privacy
"""

LINES: dict[str, list[str]] = {
    "https://fixture.invalid/ads.txt": [
        "! Fixture Ads",
        "||ads.example^",
        "||ads.example^$third-party",
        "||track.example/path^",
        "||sub.ads.example^",
        "||ads.example^$important",
        "||bare.example",
        "0.0.0.0 hosts.example",
        "||xmpl.example^$xmlhttprequest",
        "||gone.example^",
        "||gone.example^,badfilter",
        "@@||allowed.example^",
        "||badmalware.example^",
        "||evil-phish.example^",
        "example.com##.ad-banner",
        "example.com#?#.promo",
        "example.com##+js(noop)",
        "||shared.example^",
    ],
    "https://fixture.invalid/privacy.txt": [
        "! Fixture Privacy",
        "||analytics.example^",
        "||tracker.example^",
        "@@||sub.allowed.example^",
        "||shared.example^",
    ],
}


def _fake_fetch(url: str, **_kwargs) -> list[str]:
    return list(LINES[url])


def build_fixture(base: Path, *, redundant: bool = True) -> Path:
    """用固定样本构建到 ``base/dist``，返回产物目录。"""
    from adblock_collection import cli, merge

    base.mkdir(parents=True, exist_ok=True)
    config_path = base / CONFIG_NAME
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")

    original = merge.fetch_source
    merge.fetch_source = _fake_fetch
    try:
        output_dir = base / "dist"
        args = SimpleNamespace(
            config=str(config_path),
            out=str(output_dir),
            dns_policy=None,
            no_cache=True,
            no_stage_cache=True,
            offline=True,
            no_dns=False,
            redundant=redundant,
            split_by_category=True,
            alias_normalize=False,
            resolve_conflicts=False,
            per_rule_classify=False,
            domain_fold=False,
            dry_run=False,
        )
        rc = cli.build(args)
        if rc != 0:
            raise RuntimeError(f"fixture build failed with rc={rc}")
    finally:
        merge.fetch_source = original
    return output_dir
