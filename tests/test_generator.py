"""测试生成器模块"""

import os
import tempfile

from src.parser import Rule
from src.generator import generate_output, generate_changelog, load_previous_result, GenerationResult


def make_rule(raw, rule_type, source="Test", priority=1, domain=""):
    return Rule(
        raw=raw,
        normalized=raw.lower(),
        rule_type=rule_type,
        domain=domain,
        source=source,
        priority=priority,
    )


def test_generate_output():
    """测试输出文件生成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        rules = [
            make_rule("@@||safe.com^", "exception"),
            make_rule("||ads.com^", "block"),
            make_rule("||tracker.com^", "block"),
        ]

        sources_summary = {
            "Test": {"rule_count": 3, "priority": 1, "status": "updated"},
        }

        result = generate_output(rules, sources_summary, tmpdir, "filter.txt")

        assert result.total_rules == 3
        assert result.exception_rules == 1
        assert result.block_rules == 2

        # 验证文件存在且有内容
        output_path = os.path.join(tmpdir, "filter.txt")
        assert os.path.exists(output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "[AdBlock Plus 2.0]" in content
        assert "! Title: Adblock Filter Aggregator" in content
        assert "! Total rules: 3" in content
        assert "@@||safe.com^" in content
        assert "||ads.com^" in content
        assert "||tracker.com^" in content
        assert "! ===== Exception Rules =====" in content
        assert "! ===== Block Rules =====" in content


def test_generate_changelog():
    """测试变更日志生成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        current = GenerationResult(
            total_rules=100,
            exception_rules=10,
            block_rules=85,
            hide_rules=5,
            by_source={"Test": 100},
            timestamp="2026-08-02T12:00:00Z",
        )

        sources_info = {
            "Test": {"rule_count": 100, "priority": 1, "status": "updated"},
        }

        generate_changelog(
            current=current,
            sources_info=sources_info,
            previous=None,
            output_dir=tmpdir,
            changelog_file="changelog.md",
            retention_days=90,
        )

        changelog_path = os.path.join(tmpdir, "changelog.md")
        assert os.path.exists(changelog_path)

        with open(changelog_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "2026-08-02T12:00:00Z" in content
        assert "100" in content
        assert "Test" in content


def test_load_previous_result():
    """测试加载上次结果"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 先生成一个输出文件
        rules = [
            make_rule("||ads.com^", "block"),
            make_rule("@@||safe.com^", "exception"),
        ]

        sources_summary = {
            "Test": {"rule_count": 2, "priority": 1, "status": "updated"},
        }

        generate_output(rules, sources_summary, tmpdir, "filter.txt")

        # 加载上次结果
        previous = load_previous_result(tmpdir, "filter.txt")

        assert previous is not None
        assert previous.total_rules == 2
        assert previous.exception_rules == 1
        assert previous.block_rules == 1


def test_load_previous_result_nonexistent():
    """测试加载不存在的上次结果"""
    result = load_previous_result("/nonexistent/path", "filter.txt")
    assert result is None
