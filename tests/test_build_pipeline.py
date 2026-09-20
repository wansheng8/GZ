from types import SimpleNamespace

import pytest

from adblock_collection.build_pipeline import (
    BuildContext,
    BuildError,
    BuildFlags,
    FunctionStage,
    Pipeline,
    StageError,
)
from adblock_collection.rules import parse_line


def _ctx(tmp_path):
    return BuildContext(
        config_path=tmp_path / "sources.yaml",
        output_dir=tmp_path / "dist",
        dns_policy={},
        security_policy={},
        flags=BuildFlags(),
    )


def test_pipeline_runs_stages_in_order(tmp_path):
    order = []

    def stage_a(rules, ctx):
        order.append("a")
        return rules + [parse_line("||a.example^")]

    def stage_b(rules, ctx):
        order.append("b")
        return rules + [parse_line("||b.example^")]

    pipeline = Pipeline([FunctionStage("a", stage_a), FunctionStage("b", stage_b)])
    result, report = pipeline.run([], _ctx(tmp_path))

    assert order == ["a", "b"]
    assert len(result) == 2
    assert [s.name for s in report.stages] == ["a", "b"]
    assert [s.in_rules for s in report.stages] == [0, 1]
    assert [s.out_rules for s in report.stages] == [1, 2]
    assert report.total_elapsed_ms >= 0


def test_pipeline_wraps_exception_as_stage_error(tmp_path):
    def boom(rules, ctx):
        raise ValueError("kaboom")

    with pytest.raises(StageError) as exc:
        Pipeline([FunctionStage("boom", boom)]).run([], _ctx(tmp_path))
    assert "boom" in str(exc.value)
    assert isinstance(exc.value, BuildError)


def test_pipeline_propagates_build_error(tmp_path):
    def boom(rules, ctx):
        raise BuildError("already typed")

    with pytest.raises(BuildError):
        Pipeline([FunctionStage("boom", boom)]).run([], _ctx(tmp_path))


def test_function_stage_exposes_name(tmp_path):
    stage = FunctionStage("x", lambda rules, ctx: rules)
    assert stage.name == "x"
    assert stage([], _ctx(tmp_path)) == []


def test_cli_dry_run_writes_nothing(tmp_path, monkeypatch):
    from adblock_collection import cli, merge

    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "name: x\nsources:\n  - name: a\n    url: https://a\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        merge, "fetch_source", lambda *a, **k: ["! t", "||a.example^", "@@||a.example^"]
    )
    out = tmp_path / "dist"
    jsonl = tmp_path / "cache" / "rules.jsonl"
    monkeypatch.setattr(cli, "DEFAULT_JSONL_PATH", jsonl)
    saved: list = []
    monkeypatch.setattr(cli, "save_fingerprint", lambda *a, **k: saved.append(1))
    args = SimpleNamespace(
        config=str(cfg),
        out=str(out),
        dns_policy=None,
        no_cache=True,
        no_stage_cache=True,
        offline=True,
        no_dns=False,
        redundant=False,
        split_by_category=True,
        alias_normalize=False,
        resolve_conflicts=False,
        per_rule_classify=False,
        domain_fold=True,
        dry_run=True,
        baseline=None,
        history=False,
        stale_days=30,
    )
    assert cli.build(args) == 0
    assert not out.exists()
    assert not jsonl.exists()
    assert saved == []
