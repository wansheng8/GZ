import json

from adblock_collection.rules import Rule, parse_lines
from adblock_collection.rules_jsonl import (
    dump_rules_jsonl,
    load_rules_jsonl,
    rule_from_dict,
    rule_to_dict,
    safe_load_rules_jsonl,
)

SAMPLE = [
    "||ads.example^",
    "||ads.example^$important",
    "||track.example^$third-party,image",
    "||gone.example^,badfilter",
    "@@||allowed.example^",
    "example.com##.ad-banner",
    "example.com##+js(noop)",
]


def _sample_rules():
    rules = parse_lines(SAMPLE, category_hint="ads", source="Src")
    rules[0].sources = ["Src", "Other"]
    return rules


def test_round_trip_preserves_all_fields(tmp_path):
    rules = _sample_rules()
    path = tmp_path / "rules.jsonl"
    count = dump_rules_jsonl(rules, path)
    assert count == len(rules)

    restored = load_rules_jsonl(path)
    assert len(restored) == len(rules)
    for original, back in zip(rules, restored, strict=True):
        assert rule_to_dict(original) == rule_to_dict(back)


def test_rule_dict_round_trip_full_rule():
    rule = Rule(
        raw="||a.example^$important",
        norm="||a.example^$important",
        kind="network",
        category="ads",
        is_exception=False,
        is_css=False,
        is_scriptlet=False,
        is_badfilter=False,
        is_important=True,
        domains=["a.example"],
        source="Src",
        sources=["Src", "Other"],
        options={"important": ""},
    )
    restored = rule_from_dict(rule_to_dict(rule))
    assert rule_to_dict(restored) == rule_to_dict(rule)


def test_safe_load_returns_none_on_corrupt(tmp_path):
    path = tmp_path / "rules.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")
    assert safe_load_rules_jsonl(path) is None
    assert safe_load_rules_jsonl(tmp_path / "missing.jsonl") is None


def test_dump_is_jsonl(tmp_path):
    path = tmp_path / "rules.jsonl"
    dump_rules_jsonl(_sample_rules(), path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(SAMPLE)
    for line in lines:
        assert json.loads(line)["norm"]
