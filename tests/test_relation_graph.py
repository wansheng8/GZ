"""语义关系图与来源血缘补充测试。"""

from __future__ import annotations

from adblock_collection.provenance import (
    build_relation_graph,
    build_provenance,
    cross_source_duplicate_count,
)
from adblock_collection.rules import parse_line


def test_relation_graph_parent_child():
    rules = [
        parse_line("||example.com^"),
        parse_line("||sub.example.com^"),
        parse_line("||other.com^"),
    ]
    rels = build_relation_graph(rules)
    pc = [r for r in rels if r.kind == "PARENT_CHILD"]
    assert len(pc) == 1
    assert pc[0].a == "example.com"
    assert pc[0].b == "sub.example.com"


def test_relation_graph_cross_source():
    rules = [
        parse_line("||a.com^", source="EasyList"),
        parse_line("||a.com^", source="AdGuard Base"),
        parse_line("||b.com^", source="EasyList"),
    ]
    rels = build_relation_graph(rules)
    xs = [r for r in rels if r.kind == "CROSS_SOURCE_DUPLICATE"]
    assert len(xs) == 1
    assert "EasyList" in xs[0].b and "AdGuard" in xs[0].b


def test_relation_graph_exception_conflict():
    rules = [
        parse_line("||example.com^"),
        parse_line("@@||example.com^$document"),
    ]
    rels = build_relation_graph(rules)
    ec = [r for r in rels if r.kind == "EXCEPTION_CONFLICT"]
    # 冲突涉及阻断规则与例外规则两条，各记录一条关系
    assert len(ec) >= 1
    assert ec[0].a == "example.com"


def test_relation_graph_reports_in_provenance_flow(tmp_path, monkeypatch):
    from adblock_collection.cli import _write_provenance_report

    monkeypatch.chdir(tmp_path)
    rules = [
        parse_line("||example.com^"),
        parse_line("||sub.example.com^"),
    ]
    summary = _write_provenance_report(rules, tmp_path)
    assert summary["parent_child_relations"] == 1
    rg = tmp_path / "relation_graph.json"
    assert rg.exists()
    import json
    data = json.loads(rg.read_text(encoding="utf-8"))
    assert any(d["kind"] == "PARENT_CHILD" for d in data)
