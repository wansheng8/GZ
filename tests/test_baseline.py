import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _baseline_fixture import build_default_fixture, build_fixture  # noqa: E402

from adblock_collection.baseline import compare_baseline  # noqa: E402

GOLDEN = Path(__file__).parent / "baseline" / "m2"
GOLDEN_DEFAULT = Path(__file__).parent / "baseline" / "m3"


def test_fixture_build_matches_golden(tmp_path):
    out = build_fixture(tmp_path)
    diff = compare_baseline(GOLDEN, out, extra_ignores=["build_diff.txt", "new_domain_review.json"])
    assert diff.passed, [f.to_dict() for f in diff.mismatches]


def test_default_build_matches_golden(tmp_path):
    """M3：四项增强默认开启时的产物字节基线。"""
    out = build_default_fixture(tmp_path)
    diff = compare_baseline(GOLDEN_DEFAULT, out, extra_ignores=["build_diff.txt", "new_domain_review.json"])
    assert diff.passed, [f.to_dict() for f in diff.mismatches]


def test_identical_dirs_pass(tmp_path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "a.txt").write_text("x\n", encoding="utf-8")
    (new / "a.txt").write_text("x\n", encoding="utf-8")
    assert compare_baseline(old, new).passed


def test_generated_at_is_ignored(tmp_path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "sources_status.json").write_text(
        '{"total_sources": 2, "generated_at": "2026-01-01T00:00:00Z"}',
        encoding="utf-8",
    )
    (new / "sources_status.json").write_text(
        '{"total_sources": 2, "generated_at": "2026-02-02T00:00:00Z"}',
        encoding="utf-8",
    )
    assert compare_baseline(old, new).passed


def test_manifest_derived_fields_ignored(tmp_path):
    """manifest 内嵌 sources_status 时间戳与逐文件 sha256 不应造成基线抖动。"""

    def _manifest(ts: str, sha: str) -> str:
        return json.dumps(
            {
                "generated_at": ts,
                "sources_status": {"complete": True, "generated_at": ts},
                "generated_files": [{"file": "a.txt", "bytes": 3, "sha256": sha}],
            }
        )

    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "manifest.json").write_text(_manifest("2026-01-01T00:00:00Z", "aa"), encoding="utf-8")
    (new / "manifest.json").write_text(_manifest("2026-02-02T00:00:00Z", "bb"), encoding="utf-8")
    assert compare_baseline(old, new).passed


def test_manifest_content_change_detected(tmp_path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    old_payload = {"generated_files": [{"file": "a.txt", "bytes": 4, "sha256": "aa"}]}
    new_payload = {"generated_files": [{"file": "a.txt", "bytes": 3, "sha256": "bb"}]}
    (old / "manifest.json").write_text(json.dumps(old_payload), encoding="utf-8")
    (new / "manifest.json").write_text(json.dumps(new_payload), encoding="utf-8")
    assert not compare_baseline(old, new).passed


def test_missing_file_detected(tmp_path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "a.txt").write_text("x\n", encoding="utf-8")
    diff = compare_baseline(old, new)
    assert not diff.passed
    assert diff.mismatches[0].missing is True


def test_changed_line_detected(tmp_path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "a.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    (new / "a.txt").write_text("one\nTWO\nthree\n", encoding="utf-8")
    diff = compare_baseline(old, new)
    assert not diff.passed
    assert diff.files[0].first_diff_line == 2
    assert diff.files[0].diff_lines == 1


def test_offline_rebuild_from_jsonl(tmp_path):
    """需求 2.4：由 rules.jsonl 重建核心产物，不发起网络请求。"""
    from adblock_collection.build_pipeline import BuildContext, BuildFlags
    from adblock_collection.dns_policy import load_dns_policy
    from adblock_collection.rules_jsonl import DEFAULT_JSONL_PATH, emit_from_jsonl

    base = tmp_path / "fixture"
    build_fixture(base)
    jsonl = DEFAULT_JSONL_PATH
    assert jsonl.exists()

    rebuilt = tmp_path / "rebuilt"
    ctx = BuildContext(
        config_path=base / "sources.yaml",
        output_dir=rebuilt,
        dns_policy=load_dns_policy(base / "sources.yaml"),
        security_policy={"categories": ["malware", "phishing", "mining"]},
        flags=BuildFlags(gen_dns=True, split_by_category=True),
    )
    emit_from_jsonl(jsonl, rebuilt, ctx)

    for name in (
        "adblock_collection_full.txt",
        "adblock_collection_full_browser_network.txt",
        "adblock_collection_full_cosmetic.txt",
        "adblock_collection_full_dns_abp.txt",
    ):
        assert (rebuilt / name).read_bytes() == (GOLDEN / name).read_bytes()
