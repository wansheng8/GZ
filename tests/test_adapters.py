"""客户端适配产物（dist/adapters/）生成测试。"""

from __future__ import annotations

import json

import pytest
import yaml

from adblock_collection import writer
from adblock_collection.adapters import (
    PublishConfig,
    load_publish_config,
    write_adapters,
)
from adblock_collection.build_pipeline import BuildError

PUBLISH = PublishConfig(
    repository="wansheng8/GZ",
    branch="main",
    raw_base="https://raw.githubusercontent.com/wansheng8/GZ/main/dist/",
    mirror_base="https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/",
)

ALL_FILES = {
    "mihomo.yaml",
    "singbox.json",
    "surge.conf",
    "quanx.conf",
    "adguardhome.yaml",
    "pihole.txt",
    "dnsmasq.conf",
    "hosts.md",
    "browsers.md",
}

CONNECTION_BASES = (
    "adblock_clash.yaml",
    "adblock_singbox.json",
    "adblock_surge_domain_set.txt",
    "adblock_quanx.list",
)


def _seed_rulesets(tmp_path, *, parts=False):
    rdir = tmp_path / "rulesets"
    rdir.mkdir(parents=True, exist_ok=True)
    for name in CONNECTION_BASES:
        (rdir / name).write_text("seed\n", encoding="utf-8")
    if parts:
        (rdir / "adblock_quanx_part01.list").write_text("seed\n", encoding="utf-8")
        (rdir / "adblock_quanx_part02.list").write_text("seed\n", encoding="utf-8")
    return rdir


def test_write_adapters_emits_all_nine(tmp_path):
    rdir = _seed_rulesets(tmp_path)
    manifest: list = []
    written = write_adapters(tmp_path, PUBLISH, manifest, rulesets_dir=rdir)

    assert set(written) == ALL_FILES
    assert {m["file"] for m in manifest} == {f"adapters/{n}" for n in ALL_FILES}
    assert all(m["format"] == "adapter" for m in manifest)
    assert {m["target"] for m in manifest} == {
        "mihomo",
        "singbox",
        "surge",
        "quanx",
        "adguardhome",
        "pihole",
        "dnsmasq",
        "hosts",
        "browsers",
    }
    assert not any("rules" in m for m in manifest)


def test_adapters_reference_only_and_use_configured_bases(tmp_path):
    rdir = _seed_rulesets(tmp_path)
    manifest: list = []
    write_adapters(tmp_path, PUBLISH, manifest, rulesets_dir=rdir)

    for name in ALL_FILES:
        text = (tmp_path / "adapters" / name).read_text(encoding="utf-8")
        prefixes = ("||", "@@", "##") if not name.endswith(".md") else ("||", "@@")
        for line in text.splitlines():
            assert not line.startswith(prefixes), (name, line)
        for url in _urls(text):
            if url == writer.HOMEPAGE:
                continue
            assert url.startswith(
                (PUBLISH.raw_base, PUBLISH.mirror_base)
            ), (name, url)


def _urls(text: str) -> list[str]:
    import re

    return re.findall(r"https?://[^\s\"',)<>`]+", text)


def test_singbox_is_valid_jsonc_with_source_format(tmp_path):
    rdir = _seed_rulesets(tmp_path)
    write_adapters(tmp_path, PUBLISH, [], rulesets_dir=rdir)
    text = (tmp_path / "adapters" / "singbox.json").read_text(encoding="utf-8")
    body = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )
    payload = json.loads(body)
    rs = payload["route"]["rule_set"][0]
    assert rs["type"] == "remote"
    assert rs["format"] == "source"
    assert rs["url"] == PUBLISH.raw_base + "rulesets/adblock_singbox.json"
    assert payload["route"]["rules"] == [
        {"rule_set": "adblock", "action": "reject"}
    ]
    # 远端规则集缓存需显式开启 experimental.cache_file.enabled，首部注释给出提示
    assert "experimental.cache_file.enabled" in text


def test_mihomo_and_adguardhome_are_valid_yaml(tmp_path):
    rdir = _seed_rulesets(tmp_path)
    write_adapters(tmp_path, PUBLISH, [], rulesets_dir=rdir)
    mihomo = yaml.safe_load(
        (tmp_path / "adapters" / "mihomo.yaml").read_text(encoding="utf-8")
    )
    assert mihomo["rule-providers"]["adblock"]["behavior"] == "domain"
    rules = mihomo["rules"]
    assert "RULE-SET,adblock,REJECT" in rules

    agh = yaml.safe_load(
        (tmp_path / "adapters" / "adguardhome.yaml").read_text(encoding="utf-8")
    )
    assert agh["filters"][0]["url"].endswith("adblock_collection_full_domains.txt")
    # 需求 2.5：AdGuard Home 适配片段不含放行规则
    assert "! " not in (tmp_path / "adapters" / "adguardhome.yaml").read_text(
        encoding="utf-8"
    )


def test_quanx_lists_parts(tmp_path):
    rdir = _seed_rulesets(tmp_path, parts=True)
    write_adapters(tmp_path, PUBLISH, [], rulesets_dir=rdir)
    text = (tmp_path / "adapters" / "quanx.conf").read_text(encoding="utf-8")
    # 完整文件超 jsDelivr 上限时，镜像只列分片，不再引用会 403 的完整文件
    assert "adblock_quanx_part01.list, tag=Adblock-1, force-policy=reject" in text
    assert "adblock_quanx_part02.list, tag=Adblock-2, force-policy=reject" in text
    assert "adblock_quanx.list," not in text
    assert "force-remote-filter" not in text


def test_quanx_single_file_without_parts(tmp_path):
    rdir = _seed_rulesets(tmp_path)
    write_adapters(tmp_path, PUBLISH, [], rulesets_dir=rdir)
    text = (tmp_path / "adapters" / "quanx.conf").read_text(encoding="utf-8")
    assert (
        "filter_remote = https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/"
        "rulesets/adblock_quanx.list, tag=Adblock, force-policy=reject, enabled=true"
        in text
    )
    assert "force-remote-filter" not in text


def test_surge_domain_set_has_update_interval(tmp_path):
    rdir = _seed_rulesets(tmp_path)
    write_adapters(tmp_path, PUBLISH, [], rulesets_dir=rdir)
    text = (tmp_path / "adapters" / "surge.conf").read_text(encoding="utf-8")
    assert (
        "DOMAIN-SET,https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/"
        "rulesets/adblock_surge_domain_set.txt,REJECT,update-interval=86400" in text
    )


def test_skips_connection_layer_without_rulesets(tmp_path):
    manifest: list = []
    written = write_adapters(tmp_path, PUBLISH, manifest, rulesets_dir=None)
    assert set(written) == {
        "adguardhome.yaml",
        "pihole.txt",
        "dnsmasq.conf",
        "hosts.md",
        "browsers.md",
    }


def test_adapters_are_deterministic(tmp_path):
    rdir = _seed_rulesets(tmp_path, parts=True)
    write_adapters(tmp_path, PUBLISH, [], rulesets_dir=rdir)
    first = {
        p.name: p.read_bytes() for p in sorted((tmp_path / "adapters").iterdir())
    }
    write_adapters(tmp_path, PUBLISH, [], rulesets_dir=rdir)
    second = {
        p.name: p.read_bytes() for p in sorted((tmp_path / "adapters").iterdir())
    }
    assert first == second


def test_manifest_records_bytes_and_sha256(tmp_path):
    rdir = _seed_rulesets(tmp_path)
    manifest: list = []
    write_adapters(tmp_path, PUBLISH, manifest, rulesets_dir=rdir)
    writer.write_manifest(manifest, tmp_path)
    payload = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    adapters = [e for e in payload["generated_files"] if e["format"] == "adapter"]
    assert len(adapters) == 9
    for entry in adapters:
        assert entry["bytes"] > 0
        assert len(entry["sha256"]) == 64


def test_load_publish_config_defaults(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("name: X\nsources: []\n", encoding="utf-8")
    p = load_publish_config(cfg)
    assert p.repository == "wansheng8/GZ"
    assert p.branch == "main"
    assert p.raw_base.endswith("wansheng8/GZ/main/dist/")
    assert p.mirror_base.endswith("wansheng8/GZ@main/dist/")


def test_load_publish_config_override(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "publish:\n"
        "  repository: me/repo\n"
        "  branch: dev\n"
        "  raw_base: https://example.com/dist\n",
        encoding="utf-8",
    )
    p = load_publish_config(cfg)
    assert p.repository == "me/repo"
    assert p.branch == "dev"
    assert p.raw_base == "https://example.com/dist/"
    assert p.mirror_base == "https://cdn.jsdelivr.net/gh/me/repo@dev/dist/"


def test_load_publish_config_rejects_non_mapping(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("publish: [1, 2]\n", encoding="utf-8")
    with pytest.raises(BuildError):
        load_publish_config(cfg)


def test_stats_cmd_preserves_adapter_entries(tmp_path):
    """stats 只刷新 .txt 规则计数，不得给适配条目补 rules/empty。"""
    from types import SimpleNamespace

    from adblock_collection import cli

    (tmp_path / "adapters").mkdir()
    (tmp_path / "adapters" / "pihole.txt").write_text(
        "https://example.com/adlist\n", encoding="utf-8"
    )
    manifest = [
        {
            "name": "adapter_pihole",
            "file": "adapters/pihole.txt",
            "format": "adapter",
            "target": "pihole",
        }
    ]
    import json as _json

    (tmp_path / "manifest.json").write_text(
        _json.dumps({"generated_files": manifest}), encoding="utf-8"
    )
    assert cli.stats_cmd(SimpleNamespace(out=str(tmp_path))) == 0
    payload = _json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    entry = next(
        e for e in payload["generated_files"] if e["file"] == "adapters/pihole.txt"
    )
    assert entry["format"] == "adapter"
    assert entry["target"] == "pihole"
    assert "rules" not in entry
