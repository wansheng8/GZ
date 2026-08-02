#!/usr/bin/env python3
"""Adblock Filter Aggregator - 主入口

从多个上游源收集广告过滤规则，进行解析、标准化、合并去重，
输出精简版和完整版两个版本。
"""

import asyncio
import logging
import sys
from pathlib import Path

from src.config import load_config, get_enabled_sources, get_lite_sources, SourceConfig
from src.downloader import load_etags, save_etags, download_all, DownloadResult
from src.generator import generate_output, generate_changelog, load_previous_result
from src.merger import RuleMerger
from src.normalizer import normalize_rule
from src.parser import parse_rules

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def process_sources(
    results: dict[str, DownloadResult],
    lite_only: bool,
    max_rule_length: int,
) -> tuple[list, dict[str, dict]]:
    """解析和合并指定源的规则

    Args:
        results: 所有下载结果
        lite_only: True 仅处理 lite 源
        max_rule_length: 最大规则长度

    Returns:
        (merged_rules, sources_summary)
    """
    merger = RuleMerger()
    sources_summary: dict[str, dict] = {}

    for name, result in results.items():
        if lite_only and not result.source.lite:
            continue

        if result.error:
            logger.warning("[%s] Skipped: %s", name, result.error)
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

        for rule in rules:
            rule.normalized = normalize_rule(rule.raw)

        merger.add_source(rules)
        sources_summary[name] = {
            "rule_count": len(rules),
            "priority": result.source.priority,
            "status": "updated" if result.changed else "unchanged",
        }

    merged = merger.merge()

    # 校验长度
    too_long = [r for r in merged if len(r.raw) > max_rule_length]
    if too_long:
        logger.warning("%d rules exceed max length, removing", len(too_long))
        merged = [r for r in merged if len(r.raw) <= max_rule_length]

    return merged, sources_summary


async def main() -> None:
    logger.info("=== Adblock Filter Aggregator ===")

    # 1. 加载配置
    config = load_config()
    all_sources = get_enabled_sources(config)
    logger.info("Loaded %d enabled sources (%d lite)", len(all_sources), len(get_lite_sources(config)))

    # 2. 加载 ETag 缓存
    etags = load_etags(config.cache_dir, config.etag_file)
    logger.info("Loaded %d cached ETags", len(etags))

    # 3. 并发下载所有源（一次下载，两次使用）
    logger.info("Downloading from %d sources...", len(all_sources))
    results = await download_all(
        sources=all_sources,
        etags=etags,
        timeout=config.request_timeout,
        retry_delay=config.retry_delay,
    )

    changed_count = sum(1 for r in results.values() if r.changed and r.error is None)
    if changed_count == 0:
        logger.info("No sources have changed. Skipping regeneration.")
        return

    logger.info("%d source(s) have changes", changed_count)

    # 4. 生成精简版 (lite sources only)
    lite_merged, lite_summary = await process_sources(
        results, lite_only=True, max_rule_length=config.max_rule_length,
    )
    lite_result = generate_output(
        lite_merged, lite_summary, config.output_dir, config.lite_output_file,
    )
    logger.info("")
    logger.info("=== Lite Version ===")
    logger.info("Output: %s/%s", config.output_dir, config.lite_output_file)
    logger.info("Total rules: %d (%d exception, %d block, %d hide)",
                lite_result.total_rules, lite_result.exception_rules,
                lite_result.block_rules, lite_result.hide_rules)

    # 5. 生成完整版 (all sources)
    full_merged, full_summary = await process_sources(
        results, lite_only=False, max_rule_length=config.max_rule_length,
    )
    full_result = generate_output(
        full_merged, full_summary, config.output_dir, config.output_file,
    )
    logger.info("")
    logger.info("=== Full Version ===")
    logger.info("Output: %s/%s", config.output_dir, config.output_file)
    logger.info("Total rules: %d (%d exception, %d block, %d hide)",
                full_result.total_rules, full_result.exception_rules,
                full_result.block_rules, full_result.hide_rules)

    # 6. 变更日志（基于完整版）
    previous = load_previous_result(config.output_dir, config.output_file)
    generate_changelog(
        current=full_result,
        sources_info=full_summary,
        previous=previous,
        output_dir=config.output_dir,
        changelog_file=config.changelog_file,
        retention_days=config.changelog_retention_days,
    )

    logger.info("")
    logger.info("=== Generation Complete ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)
