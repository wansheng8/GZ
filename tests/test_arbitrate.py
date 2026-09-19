import json

from adblock_collection.arbitrate import arbitrate
from adblock_collection.rules import parse_line


def _parse(lines):
    return [parse_line(x, source="Test") for x in lines]


def test_global_exception_cancels_normal_block():
    rules, records = arbitrate(_parse(["||a.com^", "@@||a.com^"]))
    norms = {r.norm for r in rules}
    assert "||a.com^" not in norms
    assert "@@||a.com^" in norms
    assert len(records) == 1
    rec = records[0]
    assert rec.target == "a.com"
    assert rec.winner == "@@||a.com^"
    assert rec.losers == ["||a.com^"]


def test_global_exception_cancels_important_block():
    rules, records = arbitrate(_parse(["||a.com^$important", "@@||a.com^"]))
    norms = {r.norm for r in rules}
    assert "||a.com^$important" not in norms
    assert "@@||a.com^" in norms
    assert len(records) == 1


def test_important_block_overrides_normal_block():
    rules, records = arbitrate(_parse(["||a.com^", "||a.com^$important"]))
    norms = {r.norm for r in rules}
    assert "||a.com^$important" in norms
    assert "||a.com^" not in norms
    assert records[0].winner == "||a.com^$important"


def test_scoped_exception_does_not_cancel_block():
    rules, records = arbitrate(_parse(["||a.com^", "@@||a.com^$domain=x.com"]))
    norms = {r.norm for r in rules}
    assert "||a.com^" in norms
    assert "@@||a.com^$domain=x.com" in norms
    assert records == []


def test_path_exception_does_not_cancel_block():
    rules, records = arbitrate(_parse(["||a.com^", "@@||a.com/path^"]))
    assert len(rules) == 2
    assert records == []


def test_scoped_block_not_arbitrated():
    rules, records = arbitrate(_parse(["||a.com^$third-party", "||a.com^$important"]))
    assert len(rules) == 2
    assert records == []


def test_unrelated_domains_untouched():
    rules, records = arbitrate(_parse(["||a.com^", "||b.com^"]))
    assert len(rules) == 2
    assert records == []


def test_non_network_rules_untouched():
    rules, records = arbitrate(_parse(["||a.com^", "a.com##.ad", "@@||a.com^"]))
    assert any(r.kind == "css" for r in rules)
    assert records[0].losers == ["||a.com^"]


def test_arbitrate_is_deterministic():
    data = ["||a.com^", "||a.com^$important", "@@||b.com^", "||b.com^"]
    first, rec1 = arbitrate(_parse(data))
    second, rec2 = arbitrate(_parse(data))
    assert [r.norm for r in first] == [r.norm for r in second]
    assert [r.to_dict() for r in rec1] == [r.to_dict() for r in rec2]


def test_cli_build_resolve_conflicts_writes_report(tmp_path, monkeypatch):
    from adblock_collection import cli, merge

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n", encoding="utf-8"
    )
    lines = ["! t", "||a.com^", "@@||a.com^"]
    monkeypatch.setattr(merge, "fetch_source", lambda *a, **k: list(lines))

    out = tmp_path / "dist"
    args = type(
        "A",
        (),
        {
            "config": str(cfg),
            "out": str(out),
            "dns_policy": None,
            "no_cache": True,
            "no_stage_cache": True,
            "offline": True,
            "no_dns": False,
            "redundant": False,
            "split_by_category": False,
            "alias_normalize": False,
            "resolve_conflicts": True,
            "per_rule_classify": False,
            "domain_fold": False,
        },
    )()
    assert cli.build(args) == 0

    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    assert report["enhancements"]["resolve_conflicts"]["removed"] == 1

    records = json.loads((out / "arbitration.json").read_text(encoding="utf-8"))
    assert records[0]["target"] == "a.com"
    assert records[0]["winner"] == "@@||a.com^"

    full = (out / "adblock_collection_full.txt").read_text(encoding="utf-8")
    assert "||a.com^" not in [ln for ln in full.splitlines() if not ln.startswith("!")]
