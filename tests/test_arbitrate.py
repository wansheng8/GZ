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


def test_normal_exception_does_not_cancel_important_block():
    # C7：uBO 语义——普通整域例外不足以抵消 $important 整域阻断
    rules, records = arbitrate(_parse(["||a.com^$important", "@@||a.com^"]))
    norms = {r.norm for r in rules}
    assert "||a.com^$important" in norms
    assert "@@||a.com^" in norms
    # 两者并存，无需撤销任何规则
    assert records == []


def test_important_exception_cancels_important_block():
    # C7：带 $important 的整域例外才能抵消 $important 整域阻断
    rules, records = arbitrate(_parse(["||a.com^$important", "@@||a.com^$important"]))
    norms = {r.norm for r in rules}
    assert "||a.com^$important" not in norms
    assert "@@||a.com^$important" in norms
    assert len(records) == 1
    assert records[0].winner == "@@||a.com^$important"
    assert records[0].reason == "$important 整域例外优先于整域阻断"


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


def test_generichide_exception_does_not_cancel_block():
    rules, records = arbitrate(_parse(["||a.com^", "@@||a.com^$generichide"]))
    norms = {r.norm for r in rules}
    assert "||a.com^" in norms
    assert "@@||a.com^$generichide" in norms
    assert records == []


def test_non_blocking_exception_does_not_cancel_block():
    for option in ("$elemhide", "$removeparam=fbclid", "$csp=script-src 'self'"):
        line = f"@@||a.com^{option}"
        rules, records = arbitrate(_parse(["||a.com^", line]))
        assert {r.norm for r in rules} == {"||a.com^", line}
        assert records == []


def test_inline_comment_exception_does_not_cancel_block():
    # 行内注释（`$generichide! url: …`）须在解析阶段剥离，规则仍按 $generichide 语义
    # 处理：不能因注释污染而被当成整域放行、连带撤销同域阻断
    rules, records = arbitrate(
        _parse(
            [
                "||a.com^",
                "@@||a.com^$generichide! url: https://example.invalid/x.txt",
            ]
        )
    )
    assert records == []
    assert "||a.com^" in {r.norm for r in rules}


def test_popup_exception_does_not_cancel_block():
    rules, records = arbitrate(_parse(["||a.com^", "@@||a.com^$popup"]))
    assert {r.norm for r in rules} == {"||a.com^", "@@||a.com^$popup"}
    assert records == []


def test_document_exception_cancels_block():
    rules, records = arbitrate(_parse(["||a.com^", "@@||a.com^$document"]))
    norms = {r.norm for r in rules}
    assert "||a.com^" not in norms
    assert "@@||a.com^$document" in norms
    assert records[0].winner == "@@||a.com^$document"


def test_reason_annotation_exception_cancels_block():
    rules, _ = arbitrate(_parse(["||a.com^", "@@||a.com^$reason=manual"]))
    assert "||a.com^" not in {r.norm for r in rules}


def test_is_global_domain_exception_predicate():
    from adblock_collection.writer import _is_global_domain_exception

    def pred(line):
        return _is_global_domain_exception(parse_line(line, source="Test"))

    assert pred("@@||a.com^")
    assert pred("@@||a.com^$document")
    assert pred("@@||a.com^$all")
    assert pred("@@||a.com^$important")
    assert pred("@@||a.com^$reason=manual")
    assert not pred("@@||a.com^$generichide")
    assert not pred("@@||a.com^$generichide! url: https://example.invalid/x.txt")
    assert not pred("@@||a.com^$elemhide")
    assert not pred("@@||a.com^$removeparam=fbclid")
    assert not pred("@@||a.com^$csp=script-src 'self'")
    assert not pred("@@||a.com^$popup")
    assert not pred("@@||a.com^$third-party")
    assert not pred("@@||a.com^$script")
    assert not pred("@@||a.com^$domain=x.com")
    assert not pred("@@||a.com/path^")


def test_generichide_allowlist_does_not_allow_dns():
    from adblock_collection.writer import _blocked_domains, _custom_allow_domains

    rules = [
        parse_line("||gh.example^", source="Upstream"),
        parse_line("@@||gh.example^$generichide", source="LocalAllowlist"),
        parse_line("@@||ok.example^", source="LocalAllowlist"),
    ]
    assert _custom_allow_domains(rules) == {"ok.example"}
    assert "gh.example" in _blocked_domains(rules)


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


def test_custom_allowlist_exception_beats_upstream_block():
    rules = [
        parse_line("||a.com^", source="Upstream"),
        parse_line("@@||a.com^", source="LocalAllowlist"),
    ]
    kept, records = arbitrate(rules)
    norms = {r.norm for r in kept}
    assert "@@||a.com^" in norms
    assert "||a.com^" not in norms
    assert records[0].winner == "@@||a.com^"
    assert records[0].reason == "自定义白名单优先于阻断"


def test_custom_allowlist_exception_beats_custom_block():
    rules = [
        parse_line("||a.com^", source="LocalBlocklist"),
        parse_line("@@||a.com^", source="LocalAllowlist"),
    ]
    kept, records = arbitrate(rules)
    norms = {r.norm for r in kept}
    assert "@@||a.com^" in norms
    assert "||a.com^" not in norms
    assert len(records) == 1


def test_custom_block_beats_upstream_exception():
    rules = [
        parse_line("@@||a.com^", source="Upstream"),
        parse_line("||a.com^", source="LocalBlocklist"),
    ]
    kept, records = arbitrate(rules)
    norms = {r.norm for r in kept}
    assert "||a.com^" in norms
    assert "@@||a.com^" not in norms
    assert records[0].winner == "||a.com^"
    assert records[0].reason == "自定义黑名单优先于上游规则"


def test_custom_block_beats_upstream_important_block():
    rules = [
        parse_line("||a.com^$important", source="Upstream"),
        parse_line("||a.com^", source="LocalBlocklist"),
    ]
    kept, records = arbitrate(rules)
    norms = {r.norm for r in kept}
    assert "||a.com^" in norms
    assert "||a.com^$important" not in norms


def test_custom_block_beats_upstream_normal_block():
    rules = [
        parse_line("||a.com^", source="Upstream"),
        parse_line("||a.com^$third-party", source="LocalBlocklist"),
    ]
    kept, _ = arbitrate(rules)
    norms = {r.norm for r in kept}
    assert "||a.com^$third-party" in norms
    assert "||a.com^" not in norms


def test_upstream_priority_unchanged_without_custom():
    rules = [
        parse_line("@@||a.com^", source="Upstream"),
        parse_line("||a.com^$important", source="Upstream"),
        parse_line("||a.com^", source="Upstream"),
    ]
    kept, records = arbitrate(rules)
    norms = {r.norm for r in kept}
    assert "@@||a.com^" in norms
    assert "||a.com^$important" in norms
    assert "||a.com^" not in norms
    assert records[0].reason == "$important 阻断优先于普通整域例外"


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
