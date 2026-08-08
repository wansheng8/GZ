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
        assert "! ========== 例外规则（白名单） ==========" in content
        assert "! ========== 网络请求拦截 ==========" in content


def test_generate_output_headers_excluded_from_stats():
    """测试 header 元数据行写入输出但不计入规则统计"""
    with tempfile.TemporaryDirectory() as tmpdir:
        rules = [
            make_rule("! Title: EasyList", "header"),
            make_rule("! Expires: 4 days", "header"),
            make_rule("||ads.com^", "block"),
        ]

        sources_summary = {
            "Test": {"rule_count": 3, "priority": 1, "status": "updated"},
        }

        result = generate_output(rules, sources_summary, tmpdir, "filter.txt")

        # header 不计入统计
        assert result.total_rules == 1
        assert result.block_rules == 1

        output_path = os.path.join(tmpdir, "filter.txt")
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # header 行透传到输出文件，且在 Exception/Block 分区之前
        assert "! Title: EasyList" in content
        assert "! Expires: 4 days" in content
        assert "! Total rules: 1" in content
        block_section = content.find("! ========== 网络请求拦截 ==========")
        assert content.find("! Title: EasyList") < block_section
        assert content.find("! Expires: 4 days") < block_section


def test_generate_output_hide_group_section():
    """测试元素类规则（隐藏例外/脚本/HTML）统一归入 Hide 分区"""
    with tempfile.TemporaryDirectory() as tmpdir:
        rules = [
            make_rule("@@||safe.com^", "exception"),
            make_rule("||ads.com^", "block"),
            make_rule("example.com#@#.important", "hide-exception"),
            make_rule("example.com##.ad", "hide"),
            make_rule("example.com##+js(abort.js, x)", "scriptlet"),
            make_rule("example.com$$div.ad", "html"),
        ]

        sources_summary = {
            "Test": {"rule_count": 6, "priority": 1, "status": "updated"},
        }

        result = generate_output(rules, sources_summary, tmpdir, "filter.txt")

        # 元素类规则统一计入 hide 统计
        assert result.exception_rules == 1
        assert result.block_rules == 1
        assert result.hide_rules == 4

        with open(os.path.join(tmpdir, "filter.txt"), "r", encoding="utf-8") as f:
            content = f.read()

        # 各元素类规则透传且位于 Hide 分区内
        assert "example.com#@#.important" in content
        assert "example.com##+js(abort.js, x)" in content
        assert "example.com$$div.ad" in content
        hide_section = content.find("! ========== 元素隐藏规则 ==========")
        assert hide_section != -1
        assert content.find("example.com#@#.important") > hide_section
        assert content.find("example.com##+js(abort.js, x)") > hide_section
        assert content.find("example.com$$div.ad") > hide_section

        # 隐藏例外子分区标记存在，且隐藏例外规则在子分区标记之后
        hide_exc_section = content.find("! ========== 隐藏例外 ==========")
        assert hide_exc_section != -1
        assert hide_exc_section > hide_section
        assert content.find("example.com#@#.important") > hide_exc_section


def test_generate_output_preserves_comments():
    """测试输入注释行透传到输出文件（分区标记之后、规则之前）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        block_with_comment = make_rule("||ad.coolapk.com^", "block")
        block_with_comment.comments = ["! -- 酷安自身广告域名/路径 --"]
        exc_with_comment = make_rule("@@||api.coolapk.com^", "exception")
        exc_with_comment.comments = ["! 允许正常统计接口（避免误杀）"]

        rules = [exc_with_comment, block_with_comment]

        sources_summary = {
            "Test": {"rule_count": 2, "priority": 1, "status": "updated"},
        }

        result = generate_output(rules, sources_summary, tmpdir, "filter.txt")
        assert result.total_rules == 2

        with open(os.path.join(tmpdir, "filter.txt"), "r", encoding="utf-8") as f:
            content = f.read()

        # 注释透传且在分区标记之后、规则之前
        assert "! -- 酷安自身广告域名/路径 --" in content
        assert "! 允许正常统计接口（避免误杀）" in content

        block_section = content.find("! ========== 网络请求拦截 ==========")
        comment_pos = content.find("! -- 酷安自身广告域名/路径 --")
        rule_pos = content.find("||ad.coolapk.com^")
        assert block_section < comment_pos < rule_pos

        exc_section = content.find("! ========== 例外规则（白名单） ==========")
        assert exc_section < content.find("! 允许正常统计接口（避免误杀）") < content.find("@@||api.coolapk.com^")


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
