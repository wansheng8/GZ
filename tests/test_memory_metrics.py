from adblock_collection import memory_metrics as mm


def test_update_creates_marked_block(tmp_path):
    path = tmp_path / "MEMORY.md"
    path.write_text("# User Instruction Memory\n\n## Entries\n\n- keep me\n", encoding="utf-8")

    mm.update_memory(path, "| r0 |", keep=3)

    text = path.read_text(encoding="utf-8")
    assert mm.START in text and mm.END in text
    assert "- keep me" in text
    assert mm._data_rows(text) == ["| r0 |"]


def test_prepend_newest_and_trim(tmp_path):
    path = tmp_path / "MEMORY.md"
    path.write_text("# Memory\n", encoding="utf-8")

    for i in range(5):
        mm.update_memory(path, f"| r{i} |", keep=3)

    assert mm._data_rows(path.read_text(encoding="utf-8")) == [
        "| r4 |",
        "| r3 |",
        "| r2 |",
    ]


def test_duplicate_top_row_is_not_repeated(tmp_path):
    path = tmp_path / "MEMORY.md"
    path.write_text("# Memory\n", encoding="utf-8")

    mm.update_memory(path, "| same |", keep=5)
    mm.update_memory(path, "| same |", keep=5)

    assert mm._data_rows(path.read_text(encoding="utf-8")) == ["| same |"]


def test_inline_marker_in_prose_does_not_confuse_boundaries(tmp_path):
    path = tmp_path / "MEMORY.md"
    prose = f"- 说明：`{mm.START}` 与 `{mm.END}` 之间由 CI 维护。\n"
    path.write_text("# Memory\n\n" + prose, encoding="utf-8")

    mm.update_memory(path, "| r0 |", keep=3)
    mm.update_memory(path, "| r1 |", keep=3)

    text = path.read_text(encoding="utf-8")
    assert prose.strip() in text
    assert mm._data_rows(text) == ["| r1 |", "| r0 |"]


def test_build_row_reads_report_and_manifest(tmp_path):
    import json
    from datetime import datetime, timezone

    out = tmp_path / "dist"
    out.mkdir()
    (out / "build_report.json").write_text(
        json.dumps({"passed": True, "metrics": {"total_rules": 1234, "dns_domains": 999}}),
        encoding="utf-8",
    )
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "generated_files": [
                    {"file": mm.NETWORK, "rules": 800},
                    {"file": mm.COSMETIC, "rules": 434},
                    {"file": mm.UBO_ENHANCE, "rules": 5},
                ]
            }
        ),
        encoding="utf-8",
    )

    row = mm.build_row(out, now=datetime(2026, 9, 23, 4, 0, tzinfo=timezone.utc), sha="abc1234")

    assert row == "| 2026-09-23 04:00 | `abc1234` | 通过 | 1,234 | 999 | 800 | 434 | 5 |"
