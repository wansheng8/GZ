"""输出生成模块 - 生成最终的过滤列表文件和变更日志"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from src.parser import Rule

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """生成结果统计"""
    total_rules: int
    exception_rules: int
    block_rules: int
    hide_rules: int
    by_source: dict[str, int]
    timestamp: str


def generate_output(
    rules: list[Rule],
    sources_summary: dict[str, dict],
    output_dir: str,
    output_file: str,
) -> GenerationResult:
    """生成最终输出文件

    输出格式兼容 Adblock Plus、uBlock Origin 和 AdGuard

    Args:
        rules: 合并去重后的规则列表
        sources_summary: 各源的摘要信息
        output_dir: 输出目录
        output_file: 输出文件名

    Returns:
        GenerationResult: 生成结果统计
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc)
    timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 统计
    by_source: dict[str, int] = {}
    exception_count = 0
    block_count = 0
    hide_count = 0

    for rule in rules:
        by_source[rule.source] = by_source.get(rule.source, 0) + 1
        if rule.rule_type == "exception":
            exception_count += 1
        elif rule.rule_type == "hide":
            hide_count += 1
        else:
            block_count += 1

    # 构建文件头
    source_lines = []
    for name, info in sources_summary.items():
        source_lines.append(f"!   {name}: {info.get('rule_count', 0)} rules (priority {info.get('priority', '?')})")

    header = f"""[AdBlock Plus 2.0]
! Title: Adblock Filter Aggregator
! Description: Aggregated ad blocking filter list from multiple upstream sources
! Homepage: https://github.com/adblock-filter-aggregator
! Expires: 20 minutes
! Version: {timestamp_str}
! Last modified: {timestamp_str}
! Total rules: {len(rules)}
!   Exception rules: {exception_count}
!   Block rules: {block_count}
!   Hide rules: {hide_count}
! Sources:
{chr(10).join(source_lines)}
!
"""

    # 写入文件
    file_path = output_path / output_file
    with open(file_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(header)

        # 写入规则，exception 规则已在前
        section = ""
        for rule in rules:
            if rule.rule_type == "exception" and section != "exception":
                f.write("! ===== Exception Rules =====\n")
                section = "exception"
            elif rule.rule_type == "block" and section != "block":
                f.write("! ===== Block Rules =====\n")
                section = "block"
            elif rule.rule_type == "hide" and section != "hide":
                f.write("! ===== Hide Rules =====\n")
                section = "hide"

            f.write(rule.raw + "\n")

    result = GenerationResult(
        total_rules=len(rules),
        exception_rules=exception_count,
        block_rules=block_count,
        hide_rules=hide_count,
        by_source=by_source,
        timestamp=timestamp_str,
    )

    logger.info(
        "Generated %s: %d rules (%d exception, %d block, %d hide)",
        file_path,
        result.total_rules,
        result.exception_rules,
        result.block_rules,
        result.hide_rules,
    )

    return result


def generate_changelog(
    current: GenerationResult,
    sources_info: dict[str, dict],
    previous: Optional[GenerationResult],
    output_dir: str,
    changelog_file: str,
    retention_days: int,
) -> None:
    """生成和更新变更日志

    Args:
        current: 当前生成结果
        sources_info: 各源的详细信息
        previous: 上一次生成结果
        output_dir: 输出目录
        changelog_file: 变更日志文件名
        retention_days: 日志保留天数
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    changelog_path = output_path / changelog_file

    # 读取现有日志
    existing_entries: list[str] = []
    if changelog_path.exists():
        with open(changelog_path, "r", encoding="utf-8") as f:
            content = f.read()
        if content:
            existing_entries = content.split("\n---\n")

    # 计算增量
    delta_added = 0
    delta_removed = 0
    if previous:
        delta_added = max(0, current.total_rules - previous.total_rules)
        delta_removed = max(0, previous.total_rules - current.total_rules)

    # 构建新条目
    delta_str = ""
    if previous:
        delta_str = f" (+{delta_added} / -{delta_removed})"

    entry_lines = [f"## {current.timestamp}"]
    entry_lines.append(f"- Total rules: {current.total_rules:,}{delta_str}")
    entry_lines.append("- Sources:")

    for name, info in sorted(sources_info.items()):
        source_count = current.by_source.get(name, 0)
        status = info.get("status", "unchanged")
        status_icon = "+" if status == "updated" else "="
        entry_lines.append(f"  - {name}: {source_count:,} rules ({status_icon})")

    entry = "\n".join(entry_lines)

    # 清理过期条目（按日期过滤）
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    valid_entries = [entry]
    for old_entry in existing_entries:
        # 提取日期行
        first_line = old_entry.strip().split("\n")[0]
        if first_line.startswith("## "):
            date_str = first_line[3:].strip()
            try:
                entry_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if entry_date > cutoff:
                    valid_entries.append(old_entry)
            except ValueError:
                # 无法解析日期则保留
                valid_entries.append(old_entry)

    # 写入文件
    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write("\n---\n".join(valid_entries))

    logger.info("Updated changelog: %s", changelog_path)


def load_previous_result(output_dir: str, output_file: str) -> Optional[GenerationResult]:
    """从现有输出文件中加载上次生成的结果统计

    Args:
        output_dir: 输出目录
        output_file: 输出文件名

    Returns:
        上次的生成结果，若文件不存在则返回 None
    """
    file_path = Path(output_dir) / output_file
    if not file_path.exists():
        return None

    try:
        exception_count = 0
        block_count = 0
        hide_count = 0
        total = 0
        by_source: dict[str, int] = {}
        timestamp = ""

        with open(file_path, "r", encoding="utf-8") as f:
            section = None
            for line in f:
                stripped = line.strip()
                if stripped.startswith("! Last modified:"):
                    timestamp = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("!   ") and ":" in stripped and "rules" in stripped:
                    pass  # Source info is generated fresh each time
                elif stripped.startswith("! ===== Exception"):
                    section = "exception"
                elif stripped.startswith("! ===== Block"):
                    section = "block"
                elif stripped.startswith("! ===== Hide"):
                    section = "hide"
                elif stripped.startswith("!") or stripped.startswith("["):
                    continue  # Skip header lines and comments
                elif stripped:
                    total += 1
                    if section == "exception":
                        exception_count += 1
                    elif section == "hide":
                        hide_count += 1
                    else:
                        block_count += 1

        return GenerationResult(
            total_rules=total,
            exception_rules=exception_count,
            block_rules=block_count,
            hide_rules=hide_count,
            by_source=by_source,
            timestamp=timestamp,
        )
    except Exception as e:
        logger.warning("Failed to load previous result: %s", e)
        return None
