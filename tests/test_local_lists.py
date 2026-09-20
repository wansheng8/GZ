"""自定义黑白名单目录（config/lists/）的加载、来源标记与校验测试。"""

from __future__ import annotations

from pathlib import Path

from adblock_collection.merge import (
    _normalize_custom_line,
    load_custom_lists,
    validate_custom_lists,
)


def _write_config(tmp_path: Path, blocklist: str | None, allowlist: str | None) -> Path:
    cfg = tmp_path / "sources.yaml"
    cfg.write_text("name: t\nsources: []\n", encoding="utf-8")
    lists = tmp_path / "lists"
    lists.mkdir(exist_ok=True)
    if blocklist is not None:
        (lists / "blocklist.txt").write_text(blocklist, encoding="utf-8")
    if allowlist is not None:
        (lists / "allowlist.txt").write_text(allowlist, encoding="utf-8")
    return cfg


def test_normalize_missing_and_comments():
    assert _normalize_custom_line("", False) is None
    assert _normalize_custom_line("   ", False) is None
    assert _normalize_custom_line("# comment", False) is None
    assert _normalize_custom_line("! comment", False) is None


def test_normalize_bare_domain_direction():
    assert _normalize_custom_line("example.com", False) == "||example.com^"
    assert _normalize_custom_line("example.com", True) == "@@||example.com^"
    assert _normalize_custom_line("Sub.Example.COM", False) == "||Sub.Example.COM^"


def test_normalize_keeps_full_rules():
    assert _normalize_custom_line("||ads.example.com^", False) == "||ads.example.com^"
    assert (
        _normalize_custom_line("@@||cdn.example.com^", True)
        == "@@||cdn.example.com^"
    )
    assert (
        _normalize_custom_line("example.com##.ad-slot", False)
        == "example.com##.ad-slot"
    )


def test_normalize_treats_element_hiding_as_rule_not_comment():
    # 无域名限定的元素隐藏规则不是注释，须保留
    assert _normalize_custom_line("##.ad-slot", False) == "##.ad-slot"
    assert _normalize_custom_line("#?#.promo", False) == "#?#.promo"
    assert _normalize_custom_line("# comment", False) is None


def test_load_custom_lists_missing_files(tmp_path):
    cfg = _write_config(tmp_path, None, None)
    assert load_custom_lists(cfg, use_stage_cache=False) == []


def test_load_custom_lists_empty_and_comments(tmp_path):
    cfg = _write_config(tmp_path, "", "# only comment\n")
    loaded = dict(load_custom_lists(cfg, use_stage_cache=False))
    assert loaded["LocalBlocklist"] == []
    assert loaded["LocalAllowlist"] == []


def test_load_custom_lists_sources_and_normalization(tmp_path):
    cfg = _write_config(
        tmp_path,
        "# block\nexample.com\n||ads.example.com^\n",
        "example.com\n",
    )
    loaded = dict(load_custom_lists(cfg, use_stage_cache=False))
    block_norms = {r.norm for r in loaded["LocalBlocklist"]}
    assert "||example.com^" in block_norms
    assert "||ads.example.com^" in block_norms
    assert all(r.source == "LocalBlocklist" for r in loaded["LocalBlocklist"])
    allow_norms = {r.norm for r in loaded["LocalAllowlist"]}
    assert "@@||example.com^" in allow_norms
    assert all(r.source == "LocalAllowlist" for r in loaded["LocalAllowlist"])


def test_validate_custom_lists_missing_ok(tmp_path):
    cfg = _write_config(tmp_path, None, None)
    assert validate_custom_lists(cfg) == []


def test_validate_custom_lists_blocks_wildcards(tmp_path):
    cfg = _write_config(tmp_path, "*##.banner\n", "@@||ok.com^\n")
    violations = validate_custom_lists(cfg)
    assert any("blocklist.txt" in v for v in violations)
    assert not any("ok.com" in v for v in violations)


def test_validate_custom_lists_checks_normalized_bare_domain(tmp_path):
    # 裸域名本身合法，不应被通配校验误报
    cfg = _write_config(tmp_path, "example.com\n", "example.com\n")
    assert validate_custom_lists(cfg) == []


def _build_args(config: Path, out: Path):
    return type(
        "A",
        (),
        {
            "config": str(config),
            "out": str(out),
            "dns_policy": None,
            "no_cache": True,
            "no_stage_cache": True,
            "offline": True,
            "no_dns": False,
            "redundant": False,
            "split_by_category": False,
            "alias_normalize": True,
            "resolve_conflicts": True,
            "per_rule_classify": True,
            "domain_fold": True,
            "dry_run": False,
        },
    )()


def test_build_with_custom_lists(tmp_path, monkeypatch):
    import json

    from adblock_collection import cli, merge

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n", encoding="utf-8"
    )
    lists = tmp_path / "lists"
    lists.mkdir()
    (lists / "blocklist.txt").write_text("localblock.example\n", encoding="utf-8")
    (lists / "allowlist.txt").write_text("up.example\n", encoding="utf-8")

    upstream = [
        "||shared.example^",
        "||up.example^",
        "@@||allowme.example^",
    ]
    monkeypatch.setattr(merge, "fetch_source", lambda *a, **k: list(upstream))

    out = tmp_path / "dist"
    assert cli.build(_build_args(cfg, out)) == 0

    dns_allow = (out / "dns_allow.txt").read_text(encoding="utf-8")
    assert "up.example" in dns_allow
    # 上游例外不再派生 DNS 白名单
    assert "allowme.example" not in dns_allow
    assert "shared.example" not in dns_allow

    domains = (out / "adblock_collection_full_domains.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    # 自定义黑名单进入 DNS 阻断集合
    assert "localblock.example" in domains
    # 自定义白名单覆盖上游阻断
    assert "up.example" not in domains

    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    assert report["metrics"]["local_blocklist_rules"] == 1
    assert report["metrics"]["local_allowlist_rules"] == 1

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    entries = {e["name"]: e for e in manifest["generated_files"]}
    assert entries["dns_allow"]["source"] == "custom_allowlist"


def test_lint_parser_defaults_to_repo_lists():
    from adblock_collection.cli import _build_parser

    args = _build_parser().parse_args(["lint"])
    assert args.rules == [
        "config/local_rules.txt",
        "config/lists/blocklist.txt",
        "config/lists/allowlist.txt",
    ]


def test_repo_custom_lists_are_clean():
    from pathlib import Path as _Path

    from adblock_collection.lint import lint_text

    for rel in ("config/lists/blocklist.txt", "config/lists/allowlist.txt"):
        path = _Path(rel)
        report = lint_text(path.read_text(encoding="utf-8"), source=str(path))
        assert report.errors == [], [i.to_dict() for i in report.errors]
        assert report.warnings == [], [i.to_dict() for i in report.warnings]

