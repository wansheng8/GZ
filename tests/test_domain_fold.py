from adblock_collection.domain_fold import fold_domains
from adblock_collection.rules import parse_line


def _rules(*lines):
    out = []
    for line in lines:
        rule = parse_line(line)
        assert rule is not None
        out.append(rule)
    return out


def test_parent_covers_child():
    kept, report = fold_domains(_rules("||a.com^", "||sub.a.com^"))
    assert [r.raw for r in kept] == ["||a.com^"]
    assert report.folded == 1
    assert report.domains == ["sub.a.com"]


def test_child_exception_protects_child_block():
    rules = _rules("||a.com^", "||sub.a.com^", "@@||sub.a.com^")
    kept, report = fold_domains(rules)
    raws = [r.raw for r in kept]
    assert "||sub.a.com^" in raws
    assert "@@||sub.a.com^" in raws
    assert report.folded == 0


def test_legacy_mode_folds_exception_child():
    rules = _rules("||a.com^", "||sub.a.com^", "@@||sub.a.com^")
    kept, _ = fold_domains(rules, protect_exception_children=False)
    raws = [r.raw for r in kept]
    assert "||sub.a.com^" not in raws
    assert "@@||sub.a.com^" in raws


def test_grandchild_not_protected_by_child_exception():
    rules = _rules("||a.com^", "||x.sub.a.com^", "@@||sub.a.com^")
    kept, report = fold_domains(rules)
    assert "||x.sub.a.com^" not in [r.raw for r in kept]
    assert report.folded == 1


def test_important_representative_wins():
    kept, report = fold_domains(_rules("||a.com^", "||a.com^$important"))
    assert [r.raw for r in kept] == ["||a.com^$important"]
    assert report.folded == 1


def test_no_parent_keeps_child():
    kept, report = fold_domains(_rules("||sub.a.com^"))
    assert [r.raw for r in kept] == ["||sub.a.com^"]
    assert report.folded == 0


def test_path_rule_covered_by_full_block():
    kept, report = fold_domains(_rules("||a.com^", "||a.com/path^"))
    assert [r.raw for r in kept] == ["||a.com^"]
    assert report.folded == 1


def test_exception_rule_never_removed():
    kept, report = fold_domains(_rules("@@||a.com^"))
    assert [r.raw for r in kept] == ["@@||a.com^"]
    assert report.folded == 0


def test_fold_is_idempotent():
    rules = _rules("||a.com^", "||sub.a.com^", "||x.sub.a.com^")
    once, _ = fold_domains(rules)
    twice, report = fold_domains(once)
    assert [r.raw for r in once] == [r.raw for r in twice]
    assert report.folded == 0


def test_cli_build_domain_fold_writes_report(tmp_path, monkeypatch):
    import json

    from adblock_collection import cli, merge

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        merge, "fetch_source", lambda *a, **k: ["! t", "||a.com^", "||sub.a.com^"]
    )

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
            "resolve_conflicts": False,
            "per_rule_classify": False,
            "domain_fold": True,
        },
    )()
    assert cli.build(args) == 0

    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    assert report["enhancements"]["domain_fold"]["folded"] == 1

    fold = json.loads((out / "domain_fold.json").read_text(encoding="utf-8"))
    assert fold["domains"] == ["sub.a.com"]

    full = (out / "adblock_collection_full.txt").read_text(encoding="utf-8")
    assert "||sub.a.com^" not in full.splitlines()
