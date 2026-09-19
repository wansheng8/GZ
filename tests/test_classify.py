from adblock_collection.rules import (
    Rule,
    _signal_category,
    classify_per_rule,
    parse_line,
)


def _parse(line, hint="other"):
    return parse_line(line, category_hint=hint, source="Test")


def test_security_signal_overrides_specific_hint():
    rules = classify_per_rule([_parse("||badmalware.example^", hint="ads")])
    assert rules[0].category == "malware"


def test_phishing_signal_overrides_specific_hint():
    rules = classify_per_rule([_parse("||secure-phish-login.example^", hint="ads")])
    assert rules[0].category == "phishing"


def test_generic_hint_allows_privacy_signal():
    rules = classify_per_rule([_parse("||tracker.example^", hint="network")])
    assert rules[0].category == "privacy"


def test_specific_hint_preserved_when_signal_is_weaker():
    rules = classify_per_rule([_parse("||doubleclick.example^", hint="ads")])
    assert rules[0].category == "ads"


def test_specific_hint_preserved_without_signal():
    rules = classify_per_rule([_parse("||plain.example^", hint="ads")])
    assert rules[0].category == "ads"


def test_exception_always_whitelist():
    rules = classify_per_rule([_parse("@@||a.com^", hint="ads")])
    assert rules[0].category == "whitelist"


def test_cosmetic_keeps_kind():
    rules = classify_per_rule([_parse("a.com##.ad-banner", hint="ads")])
    assert rules[0].category == "css"


def test_domain_signal_used_when_raw_has_none():
    rule = Rule(
        raw="||cdn.example^",
        norm="||cdn.example^",
        domains=["telemetry.example"],
    )
    assert _signal_category(rule) == "privacy"


def test_classify_is_idempotent():
    rules = classify_per_rule([_parse("||google-analytics.com^", hint="network")])
    again = classify_per_rule(rules)
    assert [r.category for r in again] == [r.category for r in rules]


def test_classify_preserves_other_fields():
    rule = _parse("||badmalware.example^$important", hint="ads")
    out = classify_per_rule([rule])
    assert out[0].raw == rule.raw
    assert out[0].norm == rule.norm
    assert out[0].domains == rule.domains
    assert out[0].is_important is True


def test_cli_build_per_rule_classify_promotes_security(tmp_path, monkeypatch):
    import json

    from adblock_collection import cli, merge

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n    category: ads\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        merge, "fetch_source", lambda *a, **k: ["! t", "||badmalware.example^"]
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
            "per_rule_classify": True,
        },
    )()
    assert cli.build(args) == 0

    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    assert report["enhancements"]["per_rule_classify"]["reclassified"] == 1

    security = (out / "security" / "adblock_collection_security.txt").read_text(
        encoding="utf-8"
    )
    assert "||badmalware.example^" in security.splitlines()
