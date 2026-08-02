#!/usr/bin/env python3
"""Adblock Filter Aggregator - 主入口

从多个上游源收集广告过滤规则，进行解析、标准化、合并去重，
输出兼容主流广告过滤器的统一规则列表。
"""

import asyncio
import logging
import sys
from pathlib import Path

from src.config import load_config, get_enabled_sources
from src.downloader import load_etags, save_etags, download_all
from src.generator import generate_output, generate_changelog, load_previous_result
from src.merger import RuleMerger
from src.normalizer import normalize_rule
from src.parser import parse_rules

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """主流程"""
    logger.info("=== Adblock Filter Aggregator ===")

    # 1. 加载配置
    config = load_config()
    sources = get_enabled_sources(config)
    logger.info("Loaded %d enabled sources", len(sources))
    for src in sources:
        logger.info("  [p%d] %s: %s", src.priority, src.name, src.url)

    # 2. 加载 ETag 缓存
    etags = load_etags(config.cache_dir, config.etag_file)
    logger.info("Loaded %d cached ETags", len(etags))

    # 3. 并发下载
    logger.info("Downloading rules from %d sources...", len(sources))
    results = await download_all(
        sources=sources,
        etags=etags,
        timeout=config.request_timeout,
        retry_delay=config.retry_delay,
    )

    # 4. 检查是否有变更
    changed_count = sum(1 for r in results.values() if r.changed and r.error is None)
    if changed_count == 0:
        logger.info("No sources have changed. Skipping regeneration.")
        return

    logger.info("%d source(s) have changes", changed_count)

    # 5. 解析和合并规则
    merger = RuleMerger()
    sources_summary: dict[str, dict] = {}

    for name, result in results.items():
        if result.error:
            logger.warning("[%s] Skipped due to error: %s", name, result.error)
            sources_summary[name] = {
                "rule_count": 0,
                "priority": result.source.priority,
                "status": "error",
            }
            continue

        if not result.content:
            sources_summary[name] = {
                "rule_count": 0,
                "priority": result.source.priority,
                "status": "unchanged" if not result.changed else "empty",
            }
            continue

        rules = parse_rules(result.content, result.source)
        logger.info("[%s] Parsed %d rules", name, len(rules))

        # 标准化规则
        for rule in rules:
            rule.normalized = normalize_rule(rule.raw)

        merger.add_source(rules)
        sources_summary[name] = {
            "rule_count": len(rules),
            "priority": result.source.priority,
            "status": "updated" if result.changed else "unchanged",
        }

    # 6. 执行合并去重
    merged_rules = merger.merge()

    # 7. 校验规则长度
    too_long = [r for r in merged_rules if len(r.raw) > config.max_rule_length]
    if too_long:
        logger.warning(
            "%d rules exceed max length of %d characters (removing them)",
            len(too_long),
            config.max_rule_length,
        )
        merged_rules = [r for r in merged_rules if len(r.raw) <= config.max_rule_length]

    # 8. 生成输出
    previous = load_previous_result(config.output_dir, config.output_file)
    result = generate_output(merged_rules, sources_summary, config.output_dir, config.output_file)
    generate_changelog(
        current=result,
        sources_info=sources_summary,
        previous=previous,
        output_dir=config.output_dir,
        changelog_file=config.changelog_file,
        retention_days=config.changelog_retention_days,
    )

    # 9. 更新 ETag 缓存 - 此处不直接保存，因为 ETag 来自响应头
    # 在实际使用中，可以在 downloader 中传递 ETag 更新
    logger.info("")
    logger.info("=== Generation Complete ===")
    logger.info("Output: %s/%s", config.output_dir, config.output_file)
    logger.info("Total rules: %d", result.total_rules)
    logger.info("  Exception: %d", result.exception_rules)
    logger.info("  Block: %d", result.block_rules)
    logger.info("  Hide: %d", result.hide_rules)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)
