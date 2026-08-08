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
        assert "! ========== 例外规则（白名单） ==========" in content
        assert "! ========== 网络请求拦截 ==========" in content

        # 验证 exception 规则在前
        exception_section = content.find("! ========== 例外规则（白名单） ==========")
        block_section = content.find("! ========== 网络请求拦截 ==========")
        assert exception_section < block_section

        # 验证 hosts 格式保留原样
        assert "127.0.0.1 adware.malware.com" in content
        assert "||adware.malware.com^" not in content

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


def test_end_to_end_multi_site_dedup():
    """端到端测试: 模拟 main.py 流程（normalize_rule 覆盖），多站点顺序无关去重生效"""
    src = SourceConfig(name="Test", url="http://mock/x.txt", priority=1, enabled=True)

    # 两条语义相同、域名顺序不同的多站点 hide 规则
    rules = parse_rules(
        "example.com,foo.org##.sponsor\nfoo.org,example.com##.sponsor\n",
        src,
    )
    assert len(rules) == 2

    # 与 main.py 一致: 解析后立即用 normalize_rule 覆盖 normalized
    for rule in rules:
        rule.normalized = normalize_rule(rule.raw)

    merger = RuleMerger()
    merger.add_source(rules)
    merged = merger.merge()

    # 两条规则应被合并为一条
    assert len(merged) == 1
    assert merged[0].raw == "example.com,foo.org##.sponsor"


if __name__ == "__main__":
    test_end_to_end_pipeline()
