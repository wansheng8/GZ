"""测试主入口模块的辅助函数 - 覆盖空结果保护"""

import os
import tempfile

from main import generate_version
from src.parser import Rule


def make_rule(raw="||example.com^", rule_type="block"):
    return Rule(
        raw=raw,
        normalized=raw.lower(),
        rule_type=rule_type,
        domain="example.com",
        source="Test",
        priority=1,
    )


def test_generate_version_skips_empty():
    """测试空结果跳过生成，不写文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_version([], {}, tmpdir, "filter.txt", "Test Version")
        assert result is None
        assert not os.path.exists(os.path.join(tmpdir, "filter.txt"))


def test_generate_version_writes_output():
    """测试非空结果正常生成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        rules = [make_rule()]
        summary = {"Test": {"rule_count": 1, "priority": 1, "status": "updated"}}
        result = generate_version(rules, summary, tmpdir, "filter.txt", "Test Version")
        assert result is not None
        assert result.total_rules == 1
        assert os.path.exists(os.path.join(tmpdir, "filter.txt"))
