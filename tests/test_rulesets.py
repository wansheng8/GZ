"""连接层规则集产物（mihomo / sing-box / Surge / Quantumult X）测试。"""

import json

from adblock_collection import writer
from adblock_collection.rules import parse_line


def _rules():
    return [
        parse_line("||ads.example.com^"),
        parse_line("||track.example.com^"),
        parse_line("@@||allowed.example^", source="LocalAllowlist"),
        parse_line("||allowed.example^"),
        parse_line("example.com##.ad"),
        parse_line("||ads.example.com/path^"),
    ]


def test_write_rulesets_emits_all_formats(tmp_path):
    counts = writer.write_rulesets(_rules(), tmp_path, {"level": "all"}, "T")
    assert counts == {
        "clash": 2,
        "singbox": 2,
        "surge": 2,
        "surge_domain_set": 2,
        "quanx": 2,
    }

    rdir = tmp_path / "rulesets"
    clash = (rdir / "adblock_clash.yaml").read_text(encoding="utf-8")
    assert "payload:" in clash
    assert "  - '+.ads.example.com'" in clash
    assert "  - '+.track.example.com'" in clash
    # 自定义白名单整域放行在连接层同样生效；路径规则与元素隐藏规则不得进入
    assert "allowed.example" not in clash
    assert "path" not in clash

    singbox = json.loads((rdir / "adblock_singbox.json").read_text(encoding="utf-8"))
    assert singbox["version"] == 3
    assert singbox["rules"] == [
        {"domain_suffix": ["ads.example.com", "track.example.com"]}
    ]

    surge = (rdir / "adblock_surge.list").read_text(encoding="utf-8")
    assert "DOMAIN-SUFFIX,ads.example.com,REJECT" in surge
    assert "DOMAIN-SUFFIX,allowed.example,REJECT" not in surge

    domain_set = (rdir / "adblock_surge_domain_set.txt").read_text(encoding="utf-8")
    ds_lines = domain_set.splitlines()
    assert ".ads.example.com" in ds_lines
    assert ".track.example.com" in ds_lines
    assert "allowed.example" not in ds_lines

    quanx = (rdir / "adblock_quanx.list").read_text(encoding="utf-8")
    assert "host-suffix, ads.example.com, reject" in quanx
    assert "host-suffix, allowed.example, reject" not in quanx


def test_write_rulesets_empty_is_valid(tmp_path):
    counts = writer.write_rulesets([], tmp_path, {"level": "all"}, "T")
    assert counts == {
        "clash": 0,
        "singbox": 0,
        "surge": 0,
        "surge_domain_set": 0,
        "quanx": 0,
    }
    rdir = tmp_path / "rulesets"
    assert (rdir / "adblock_clash.yaml").read_text(encoding="utf-8").startswith("# T")
    assert json.loads((rdir / "adblock_singbox.json").read_text(encoding="utf-8")) == {
        "version": 3,
        "rules": [{"domain_suffix": []}],
    }


def test_hosts_and_bare_domain_sources_use_exact_operators(tmp_path):
    """hosts 行 / domains-only 行仅匹配域名本体，连接层用精确算子。"""
    rules = [
        parse_line("||ads.example.com^"),
        parse_line("0.0.0.0 hosts.example.com"),
        parse_line("bare.example.com"),
    ]
    writer.write_rulesets(rules, tmp_path, {"level": "all"}, "T")
    rdir = tmp_path / "rulesets"
    clash = (rdir / "adblock_clash.yaml").read_text(encoding="utf-8")
    assert "  - '+.ads.example.com'" in clash
    assert "  - 'hosts.example.com'" in clash
    assert "  - 'bare.example.com'" in clash
    assert "  - '+.hosts.example.com'" not in clash

    singbox = json.loads((rdir / "adblock_singbox.json").read_text(encoding="utf-8"))
    assert singbox["rules"] == [
        {"domain_suffix": ["ads.example.com"]},
        {"domain": ["bare.example.com", "hosts.example.com"]},
    ]

    surge = (rdir / "adblock_surge.list").read_text(encoding="utf-8")
    assert "DOMAIN-SUFFIX,ads.example.com,REJECT" in surge
    assert "DOMAIN,hosts.example.com,REJECT" in surge
    assert "DOMAIN,bare.example.com,REJECT" in surge

    domain_set = (rdir / "adblock_surge_domain_set.txt").read_text(encoding="utf-8")
    ds_lines = domain_set.splitlines()
    # 前导点=本体+子域；裸域名=精确（hosts / domains-only 来源）
    assert ".ads.example.com" in ds_lines
    assert "hosts.example.com" in ds_lines
    assert "bare.example.com" in ds_lines
    assert ".hosts.example.com" not in ds_lines

    quanx = (rdir / "adblock_quanx.list").read_text(encoding="utf-8")
    assert "host-suffix, ads.example.com, reject" in quanx
    assert "host, hosts.example.com, reject" in quanx
    assert "host, bare.example.com, reject" in quanx


def test_suffix_semantics_dominate_when_both_present():
    """同一域名同时有精确与含子域来源时，按更宽的含子域处理。"""
    rules = [parse_line("0.0.0.0 dup.example"), parse_line("||dup.example^")]
    suffix, exact = writer._scan_dns_domains(rules, {"level": "all"})
    assert suffix == {"dup.example"}
    assert exact == set()


def test_emit_rulesets_appends_manifest(tmp_path):
    from adblock_collection import cli

    manifest = []
    cli._emit_rulesets(_rules(), tmp_path, manifest, {"level": "all"})
    files = {m["file"] for m in manifest}
    assert "rulesets/adblock_clash.yaml" in files
    assert "rulesets/adblock_singbox.json" in files
    assert "rulesets/adblock_surge.list" in files
    assert "rulesets/adblock_surge_domain_set.txt" in files
    assert "rulesets/adblock_quanx.list" in files
    formats = {m["format"] for m in manifest}
    assert formats == {
        "clash_ruleset",
        "singbox_ruleset",
        "surge_ruleset",
        "surge_domain_set",
        "quanx_ruleset",
    }
    assert all(m["rules"] == 2 for m in manifest)


def test_split_text_list_roundtrips_and_respects_limit(tmp_path):
    path = tmp_path / "adblock_surge.list"
    lines = ["# T", "# Total Rules: 100"]
    lines += [f"DOMAIN-SUFFIX,d{i}.example,REJECT" for i in range(100)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    names = writer.split_text_list(path, max_bytes=300)
    assert len(names) > 1
    parts = [tmp_path / n for n in names]
    body = [
        line
        for p in parts
        for line in p.read_text(encoding="utf-8").splitlines()
        if not line.startswith("#")
    ]
    assert body == [line for line in lines if not line.startswith("#")]
    assert all(p.stat().st_size <= 300 for p in parts)
    assert all("Total Rules" in p.read_text(encoding="utf-8") for p in parts)
    # 每片标注分片序号 i/N
    for index, p in enumerate(parts, 1):
        assert f"# Part {index}/{len(parts)}" in p.read_text(encoding="utf-8")


def test_split_text_list_skips_small_files(tmp_path):
    path = tmp_path / "adblock_surge.list"
    path.write_text("# T\nDOMAIN-SUFFIX,a.example,REJECT\n", encoding="utf-8")
    assert writer.split_text_list(path, max_bytes=1024) == []


def test_write_rulesets_splits_oversized_text_lists(tmp_path, monkeypatch):
    monkeypatch.setattr(writer, "JSDELIVR_MAX_BYTES", 300)
    rules = [parse_line(f"||d{i}.example^") for i in range(100)]
    writer.write_rulesets(rules, tmp_path, {"level": "all"}, "T")
    rdir = tmp_path / "rulesets"
    assert list(rdir.glob("adblock_surge_part*.list"))
    assert list(rdir.glob("adblock_quanx_part*.list"))
    assert not list(rdir.glob("adblock_clash_part*"))
    assert not list(rdir.glob("adblock_singbox_part*"))


def test_write_surge_domain_set_warns_over_limit(tmp_path, monkeypatch, caplog):
    import logging

    monkeypatch.setattr(writer, "SURGE_DOMAIN_SET_MAX", 2)
    with caplog.at_level(logging.WARNING, logger="adblock_collection"):
        writer.write_surge_domain_set(
            {"a.example", "b.example", "c.example"},
            tmp_path / "domain_set.txt",
            "T",
        )
    assert any("超过单集上限" in rec.message for rec in caplog.records)
    assert "total 3" in (tmp_path / "domain_set.txt").read_text(encoding="utf-8")
