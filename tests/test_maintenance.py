"""规则过期/维护跟踪（build --history）。"""

from __future__ import annotations

import json
from datetime import date

from adblock_collection.maintenance import (
    load_history,
    update_history,
    write_maintenance_report,
)
from adblock_collection.rules import parse_line


def _rules(*raws):
    return [parse_line(raw) for raw in raws]


def test_update_history_marks_current_and_detects_stale(tmp_path):
    path = tmp_path / "history.tsv"
    update_history(_rules("||a.com^", "||b.com^"), today=date(2026, 1, 1), path=path)

    result = update_history(
        _rules("||a.com^"), today=date(2026, 2, 15), stale_days=30, path=path
    )
    stale_norm = parse_line("||b.com^").norm
    assert result["stale"] == [stale_norm]
    assert result["tracked"] == 2
    assert load_history(path)[parse_line("||a.com^").norm] == "2026-02-15"


def test_update_history_prunes_beyond_retention(tmp_path):
    path = tmp_path / "history.tsv"
    update_history(_rules("||old.com^"), today=date(2026, 1, 1), path=path)
    result = update_history(
        _rules("||new.com^"),
        today=date(2026, 6, 1),
        stale_days=30,
        retention_days=120,
        path=path,
    )
    assert result["tracked"] == 1
    assert set(load_history(path)) == {parse_line("||new.com^").norm}


def test_write_maintenance_report(tmp_path):
    report = write_maintenance_report(
        tmp_path,
        {
            "tracked": 5,
            "current": 3,
            "stale": ["x", "y"],
            "stale_days": 30,
            "retention_days": 120,
        },
    )
    assert report["stale_count"] == 2
    data = json.loads((tmp_path / "maintenance_report.json").read_text(encoding="utf-8"))
    assert data["stale_sample"] == ["x", "y"]
    assert "generated_at" in data and "today" in data
