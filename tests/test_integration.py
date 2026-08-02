"""端到端集成测试 - 模拟完整管道流程"""

import os
import tempfile

from src.config import SourceConfig
from src.parser import parse_rules
from src.normalizer import normalize_rule
from src.merger import RuleMerger
from src.generator import generate_output, generate_changelog


# 模拟两个上游源的规则内容
EASYLIST_CONTENT = """[Adblock Plus 2.0]
! Title: EasyList
! Last modified: 01 Aug 2026 12:00 UTC
||doubleclick.net^
||googleadservices.com^
@@||example.com/acceptable-ads^
||ads.example.com^
! This is a comment
||tracker.example.com/analytics.js
"""

ADGUARD_CONTENT = """[Adguard]
! Title: AdGuard Base filter
! Expires: 4 days
||doubleclick.net^
||facebook.com/ads/*
||new-rule-from-adguard.com^
@@||adguard-whitelist.com^
127.0.0.1 adware.malware.com
"""


def test_end_to_end_pipeline():
    """端到端测试：模拟两个源的完整处理管道"""
    # 创建源配置
    easylist_src = SourceConfig(
        name="EasyList", url="http://mock/easylist.txt", priority=1, enabled=True
    )
    adguard_src = SourceConfig(
        name="AdGuard Base", url="http://mock/adguard.txt", priority=3, enabled=True
    )

    # 解析规则
    easylist_rules = parse_rules(EASYLIST_CONTENT, easylist_src)
    adguard_rules = parse_rules(ADGUARD_CONTENT, adguard_src)

    # 标准化
    for rule in easylist_rules + adguard_rules:
        rule.normalized = normalize_rule(rule.raw)

    # 合并去重
    merger = RuleMerger()
    merger.add_source(easylist_rules)
    merger.add_source(adguard_rules)
    merged = merger.merge()

    # 验证去重效果
    normalized_set = {r.normalized for r in merged}
    # doubleclick.net^ 在两个源中都出现，应该被去重
    assert "||doubleclick.net^" in normalized_set
    # 确认去重后规则数少于两个源的总和
    total_raw = len(easylist_rules) + len(adguard_rules)
    assert len(merged) < total_raw, f"Expected dedup, but got {len(merged)} >= {total_raw}"

    # 验证来源优先级
    doubleclick_rules = [r for r in merged if "doubleclick" in r.normalized]
    assert doubleclick_rules[0].priority == 1  # EasyList 优先级最高

    # 生成输出
    with tempfile.TemporaryDirectory() as tmpdir:
        sources_summary = {
            "EasyList": {"rule_count": len(easylist_rules), "priority": 1, "status": "updated"},
            "AdGuard Base": {"rule_count": len(adguard_rules), "priority": 3, "status": "updated"},
        }

        result = generate_output(merged, sources_summary, tmpdir, "filter.txt")

        # 验证生成结果
        assert result.total_rules > 0
        assert result.exception_rules > 0
        assert result.block_rules > 0

        # 验证输出文件
        output_path = os.path.join(tmpdir, "filter.txt")
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 验证格式
        assert "[AdBlock Plus 2.0]" in content
        assert "! Title: Adblock Filter Aggregator" in content
        assert "! Expires: 20 minutes" in content
        assert "! ===== Exception Rules =====" in content
        assert "! ===== Block Rules =====" in content

        # 验证 exception 规则在前
        exception_section = content.find("! ===== Exception Rules =====")
        block_section = content.find("! ===== Block Rules =====")
        assert exception_section < block_section

        # 验证 hosts 格式转换
        assert "||adware.malware.com^" in content

        # 验证变更日志
        generate_changelog(
            current=result,
            sources_info=sources_summary,
            previous=None,
            output_dir=tmpdir,
            changelog_file="changelog.md",
            retention_days=90,
        )

        changelog_path = os.path.join(tmpdir, "changelog.md")
        assert os.path.exists(changelog_path)

        print(f"Total rules: {result.total_rules}")
        print(f"  Exception: {result.exception_rules}")
        print(f"  Block: {result.block_rules}")
        print(f"  Hide: {result.hide_rules}")
        print(f"E2E pipeline test PASSED")


if __name__ == "__main__":
    test_end_to_end_pipeline()
