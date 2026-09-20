import json

from adblock_collection.aliases import normalize_aliases
from adblock_collection.rules import parse_line


def _rule(line, source="Test"):
    return parse_line(line, source=source)


def test_xmlhttprequest_normalized_to_xhr():
    rules, report = normalize_aliases([_rule("||a.com^$xmlhttprequest")])
    assert rules[0].raw == "||a.com^$xhr"
    assert rules[0].norm == "||a.com^$xhr"
    assert list(rules[0].options) == ["xhr"]
    assert report.normalized == 1
    assert report.by_alias == {"xmlhttprequest": 1}


def test_doc_normalized_to_document():
    rules, _ = normalize_aliases([_rule("||a.com^$doc")])
    assert rules[0].raw == "||a.com^$document"
    assert "document" in rules[0].options


def test_frame_normalized_to_subdocument():
    rules, report = normalize_aliases([_rule("||a.com^$frame")])
    assert rules[0].raw == "||a.com^$subdocument"
    assert "subdocument" in rules[0].options
    assert report.by_alias == {"frame": 1}


def test_frame_and_subdocument_collapse():
    rules, report = normalize_aliases(
        [_rule("||a.com^$frame"), _rule("||a.com^$subdocument")]
    )
    assert len(rules) == 1
    assert report.collapsed == 1


def test_generichide_aliases_collapse():
    for alias in ("ghide", "ehide", "elemhide"):
        rules, _ = normalize_aliases([_rule(f"||a.com^${alias}")])
        assert rules[0].raw == "||a.com^$generichide", alias


def test_negation_prefix_preserved():
    rules, _ = normalize_aliases([_rule("||a.com^$~xmlhttprequest")])
    assert rules[0].raw == "||a.com^$~xhr"
    assert "~xhr" in rules[0].options


def test_option_value_preserved():
    rules, _ = normalize_aliases([_rule("||a.com^$xmlhttprequest,domain=x.com")])
    assert "$xhr,domain=x.com" in rules[0].raw
    assert rules[0].options["domain"] == "x.com"


def test_non_alias_options_untouched():
    line = "||a.com^$popup,other,websocket,important"
    rules, report = normalize_aliases([_rule(line)])
    assert rules[0].raw == line
    assert report.normalized == 0


def test_rule_without_options_untouched():
    line = "||a.com^"
    rules, report = normalize_aliases([_rule(line)])
    assert rules[0].raw == line
    assert report.normalized == 0
    assert report.collapsed == 0


def test_alias_equivalent_rules_collapse_and_merge_sources():
    rules, report = normalize_aliases(
        [
            _rule("||a.com^$xmlhttprequest", source="SrcA"),
            _rule("||a.com^$xhr", source="SrcB"),
        ]
    )
    assert len(rules) == 1
    assert rules[0].sources == ["SrcA", "SrcB"]
    assert report.collapsed == 1


def test_normalize_is_idempotent():
    first, _ = normalize_aliases([_rule("||a.com^$xmlhttprequest")])
    second, report = normalize_aliases(first)
    assert second[0].raw == first[0].raw
    assert second[0].norm == first[0].norm
    assert report.normalized == 0
    assert report.collapsed == 0


def test_unrelated_duplicates_still_collapse_once():
    rules, report = normalize_aliases(
        [_rule("||a.com^", source="A"), _rule("||a.com^", source="B")]
    )
    assert len(rules) == 1
    assert rules[0].sources == ["A", "B"]
    assert report.collapsed == 1


def _build_args(cfg, out, alias):
    return type(
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
            "alias_normalize": alias,
            "resolve_conflicts": False,
            "per_rule_classify": False,
            "domain_fold": False,
        },
    )()


def test_cli_build_alias_normalize_toggle(tmp_path, monkeypatch):
    from adblock_collection import cli, merge

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n", encoding="utf-8"
    )
    lines = [
        "! t",
        "||ads.example.com^$xmlhttprequest",
        "||ads.example.com^$xhr",
        "||track.example.com^$doc",
    ]
    monkeypatch.setattr(merge, "fetch_source", lambda *a, **k: list(lines))

    off = tmp_path / "off"
    on = tmp_path / "on"
    assert cli.build(_build_args(cfg, off, False)) == 0
    assert cli.build(_build_args(cfg, on, True)) == 0

    off_txt = (off / "adblock_collection_full.txt").read_text(encoding="utf-8")
    on_txt = (on / "adblock_collection_full.txt").read_text(encoding="utf-8")

    assert "||ads.example.com^$xmlhttprequest" in off_txt
    assert "||ads.example.com^$xhr" in off_txt
    assert "||track.example.com^$doc" in off_txt

    assert "$xmlhttprequest" not in on_txt
    assert "||track.example.com^$document" in on_txt

    on_report = json.loads((on / "build_report.json").read_text(encoding="utf-8"))
    stats = on_report["enhancements"]["alias_normalize"]
    assert stats["normalized"] >= 2
    assert stats["collapsed"] >= 1

    off_report = json.loads((off / "build_report.json").read_text(encoding="utf-8"))
    assert off_report["enhancements"] == {}
