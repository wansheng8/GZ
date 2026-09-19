"""M3：增强开关默认开启、退出开关与旧 --redundant 兼容路径。"""

from __future__ import annotations

import json
from types import SimpleNamespace

from adblock_collection import cli, merge
from adblock_collection.cli import _build_parser


def _args(tmp_path, **overrides):
    base = {
        "config": str(tmp_path / "sources.yaml"),
        "out": str(tmp_path / "dist"),
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
    }
    base.update(overrides)
    return SimpleNamespace(**base)


_LINES = [
    "! t",
    "||a.com^$xmlhttprequest",
    "||b.com^",
    "@@||b.com^",
    "||badmalware.example^",
    "||c.com^",
    "||sub.c.com^",
]


def _write_cfg(tmp_path):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n    category: ads\n",
        encoding="utf-8",
    )
    return cfg


def test_cli_defaults_enable_all_enhancements():
    ns = _build_parser().parse_args(["build"])
    assert ns.alias_normalize is True
    assert ns.resolve_conflicts is True
    assert ns.per_rule_classify is True
    assert ns.domain_fold is True
    assert ns.redundant is False


def test_cli_opt_out_flags_disable_only_targeted():
    ns = _build_parser().parse_args(["build", "--no-domain-fold", "--no-alias-normalize"])
    assert ns.domain_fold is False
    assert ns.alias_normalize is False
    assert ns.resolve_conflicts is True
    assert ns.per_rule_classify is True


def test_default_flags_enable_all_enhancements(tmp_path, monkeypatch):
    _write_cfg(tmp_path)
    monkeypatch.setattr(merge, "fetch_source", lambda *a, **k: list(_LINES))

    out = tmp_path / "dist"
    assert cli.build(_args(tmp_path)) == 0

    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    for key in (
        "alias_normalize",
        "resolve_conflicts",
        "per_rule_classify",
        "domain_fold",
    ):
        assert key in report["enhancements"], f"missing enhancement report: {key}"
    assert (out / "arbitration.json").exists()
    assert (out / "domain_fold.json").exists()
    full = (out / "adblock_collection_full.txt").read_text(encoding="utf-8").splitlines()
    assert "||sub.c.com^" not in full


def test_opt_out_disables_all_enhancements(tmp_path, monkeypatch):
    _write_cfg(tmp_path)
    monkeypatch.setattr(merge, "fetch_source", lambda *a, **k: list(_LINES))

    out = tmp_path / "dist-off"
    args = _args(
        tmp_path,
        out=str(out),
        alias_normalize=False,
        resolve_conflicts=False,
        per_rule_classify=False,
        domain_fold=False,
    )
    assert cli.build(args) == 0

    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    assert report["enhancements"] == {}
    assert not (out / "arbitration.json").exists()
    assert not (out / "domain_fold.json").exists()


def test_redundant_compat_keeps_legacy_domain_fold(tmp_path, monkeypatch):
    _write_cfg(tmp_path)
    monkeypatch.setattr(merge, "fetch_source", lambda *a, **k: list(_LINES))

    out = tmp_path / "dist-legacy"
    args = _args(
        tmp_path,
        out=str(out),
        redundant=True,
        alias_normalize=False,
        resolve_conflicts=False,
        per_rule_classify=False,
        domain_fold=False,
    )
    assert cli.build(args) == 0

    full = (out / "adblock_collection_full.txt").read_text(encoding="utf-8").splitlines()
    assert "||sub.c.com^" not in full
