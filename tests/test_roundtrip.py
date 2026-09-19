"""需求 9：解析与序列化往返一致性校验。"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

from _baseline_fixture import build_default_fixture  # noqa: E402

from adblock_collection import cli, merge  # noqa: E402
from adblock_collection.dns_policy import load_dns_policy  # noqa: E402
from adblock_collection.roundtrip import check_roundtrip  # noqa: E402
from adblock_collection.rules_jsonl import (  # noqa: E402
    DEFAULT_JSONL_PATH,
    load_rules_jsonl,
)

_FORMAT_FILES = {
    "adblock": "adblock_collection_full.txt",
    "hosts": "adblock_collection_full_dns.txt",
    "hosts_ipv6": "adblock_collection_full_dns_ipv6.txt",
    "domains": "adblock_collection_full_domains.txt",
    "adblock_domains": "adblock_collection_full_dns_abp.txt",
}


def _prepare(tmp_path):
    out = build_default_fixture(tmp_path)
    policy = load_dns_policy(tmp_path / "sources.yaml")
    rules = load_rules_jsonl(DEFAULT_JSONL_PATH)
    paths = {fmt: out / name for fmt, name in _FORMAT_FILES.items()}
    return out, policy, rules, paths


def test_roundtrip_passes_for_all_formats(tmp_path):
    _out, policy, rules, paths = _prepare(tmp_path)
    assert check_roundtrip(paths, rules, policy) == []


def test_roundtrip_detects_domain_loss(tmp_path):
    _out, policy, rules, paths = _prepare(tmp_path)
    target = paths["domains"]
    lines = target.read_text(encoding="utf-8").splitlines()
    domain = next(line for line in lines if line and not line.startswith("#"))
    target.write_text(
        target.read_text(encoding="utf-8").replace(domain + "\n", "", 1),
        encoding="utf-8",
    )
    issues = check_roundtrip(paths, rules, policy)
    assert any(issue.startswith("domains ") for issue in issues)


def test_roundtrip_detects_adblock_loss(tmp_path):
    _out, policy, rules, paths = _prepare(tmp_path)
    target = paths["adblock"]
    lines = target.read_text(encoding="utf-8").splitlines()
    idx = next(
        i
        for i, line in enumerate(lines)
        if line and not line.startswith("!") and not line.startswith("[")
    )
    lines.pop(idx)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    issues = check_roundtrip(paths, rules, policy)
    assert any(issue.startswith("adblock ") for issue in issues)


def _args(tmp_path):
    return SimpleNamespace(
        config=str(tmp_path / "sources.yaml"),
        out=str(tmp_path / "dist"),
        dns_policy=None,
        no_cache=True,
        no_stage_cache=True,
        offline=True,
        no_dns=False,
        redundant=False,
        split_by_category=False,
        alias_normalize=True,
        resolve_conflicts=True,
        per_rule_classify=True,
        domain_fold=True,
        dry_run=False,
    )


def test_build_fails_when_roundtrip_violated(tmp_path, monkeypatch):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n    category: ads\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(merge, "fetch_source", lambda *a, **k: ["||a.com^"])
    monkeypatch.setattr(
        cli, "check_roundtrip", lambda *a, **k: ["adblock 往返丢失 1 条规则: 'x'"]
    )
    assert cli.build(_args(tmp_path)) == 3
