"""配置加载模块 - 读取和验证 sources.yaml 配置"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SourceConfig:
    """单个上游规则源的配置"""
    name: str
    url: str
    priority: int
    lite: bool = False
    enabled: bool = True


@dataclass
class AppConfig:
    """应用全局配置"""
    sources: list[SourceConfig] = field(default_factory=list)
    output_dir: str = "dist"
    output_file: str = "filter.txt"
    lite_output_file: str = "filter-lite.txt"
    changelog_file: str = "changelog.md"
    cache_dir: str = "cache"
    etag_file: str = "etags.json"
    request_timeout: int = 30
    retry_delay: int = 5
    max_rule_length: int = 4000
    changelog_retention_days: int = 90


def load_config(path: str = "sources.yaml") -> AppConfig:
    """从 YAML 文件加载配置"""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Configuration file is empty: {path}")

    sources = []
    if "sources" not in raw:
        raise ValueError("Missing 'sources' section in configuration")

    for src in raw["sources"]:
        sources.append(SourceConfig(
            name=src["name"],
            url=src["url"],
            priority=src["priority"],
            lite=src.get("lite", False),
            enabled=src.get("enabled", True),
        ))

    settings = raw.get("settings", {})

    return AppConfig(
        sources=sources,
        output_dir=settings.get("output_dir", "dist"),
        output_file=settings.get("output_file", "filter.txt"),
        lite_output_file=settings.get("lite_output_file", "filter-lite.txt"),
        changelog_file=settings.get("changelog_file", "changelog.md"),
        cache_dir=settings.get("cache_dir", "cache"),
        etag_file=settings.get("etag_file", "etags.json"),
        request_timeout=settings.get("request_timeout", 30),
        retry_delay=settings.get("retry_delay", 5),
        max_rule_length=settings.get("max_rule_length", 4000),
        changelog_retention_days=settings.get("changelog_retention_days", 90),
    )


def get_enabled_sources(config: AppConfig) -> list[SourceConfig]:
    """获取所有启用的源，按 priority 升序排列"""
    return sorted(
        [s for s in config.sources if s.enabled],
        key=lambda s: s.priority,
    )


def get_lite_sources(config: AppConfig) -> list[SourceConfig]:
    """获取精简版启用的源（lite: true 且 enabled）"""
    return sorted(
        [s for s in config.sources if s.enabled and s.lite],
        key=lambda s: s.priority,
    )
