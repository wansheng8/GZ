import json


def test_cli_build_all_enhancements_compose(tmp_path, monkeypatch):
    from adblock_collection import cli, merge

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n    category: ads\n",
        encoding="utf-8",
    )
    lines = [
        "! t",
        "||a.com^$xmlhttprequest",
        "||b.com^",
        "@@||b.com^",
        "||badmalware.example^",
        "||c.com^",
        "||sub.c.com^",
    ]
    monkeypatch.setattr(merge, "fetch_source", lambda *a, **k: list(lines))

    out = tmp_path / "dist-enhanced"
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
            "alias_normalize": True,
            "resolve_conflicts": True,
            "per_rule_classify": True,
            "domain_fold": True,
        },
    )()
    assert cli.build(args) == 0

    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    enhancements = report["enhancements"]
    for key in (
        "alias_normalize",
        "resolve_conflicts",
        "per_rule_classify",
        "domain_fold",
    ):
        assert key in enhancements, f"missing enhancement report: {key}"

    full = (out / "adblock_collection_full.txt").read_text(encoding="utf-8").splitlines()
    assert "||sub.c.com^" not in full
    assert "||a.com^$xhr" in full
