"""阶段缓存与算法版本。

把「下载 → 解析 → 规范化 → 分类 → 提取域名」拆成可缓存阶段。只要「源内容哈希 +
各阶段算法版本」不变，就直接复用已解析的 Rule 列表，避免对未变化的上游重复解析。

算法版本约定：任何影响 Rule 字段产出的逻辑变更（normalize / classify / extract_domains /
_parser 正则调整）都应 bump 对应版本号，旧缓存自动失效，避免「代码已升级、CI 仍用旧缓存」
的隐患。

阶段：
- sources : 原始文本（已有 .cache/sources/，由 fetch_source 管理）
- parsed  : 文本 -> Rule 列表（本模块管理，key = src_sha256 + PARSER_VERSION）
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Iterable, Optional

from .rules import Rule, parse_line

LOG = logging.getLogger("adblock_collection")

# 各阶段算法版本。逻辑变更时递增，旧缓存自动失效。
PARSER_VERSION = "1.1.0"
NORMALIZER_VERSION = "1.0.0"
CLASSIFIER_VERSION = "1.1.0"

STAGE_DIR = Path(".cache/parsed")


def _source_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stage_key(url: str, src_sha: str) -> str:
    payload = "||".join([url, src_sha, PARSER_VERSION, NORMALIZER_VERSION, CLASSIFIER_VERSION])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def cache_path(url: str, src_sha: str) -> Path:
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    return STAGE_DIR / _stage_key(url, src_sha)


def load_parsed(url: str, src_sha: str) -> Optional[list[Rule]]:
    """命中阶段缓存则返回已解析的 Rule 列表，否则返回 None。"""
    path = cache_path(url, src_sha)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rules: list[Rule] = []
    for item in data:
        r = Rule(
            raw=item["raw"],
            norm=item["norm"],
            kind=item.get("kind", "network"),
            category=item.get("category", "other"),
            is_exception=item.get("is_exception", False),
            is_css=item.get("is_css", False),
            is_scriptlet=item.get("is_scriptlet", False),
            is_badfilter=item.get("is_badfilter", False),
            is_important=item.get("is_important", False),
            domains=item.get("domains", []),
            source=item.get("source"),
            options=item.get("options", {}),
        )
        rules.append(r)
    LOG.info("阶段缓存命中: %s (%d 条)", url, len(rules))
    return rules


def save_parsed(url: str, src_sha: str, rules: Iterable[Rule]) -> None:
    """将解析结果写入阶段缓存。"""
    payload = [
        {
            "raw": r.raw,
            "norm": r.norm,
            "kind": r.kind,
            "category": r.category,
            "is_exception": r.is_exception,
            "is_css": r.is_css,
            "is_scriptlet": r.is_scriptlet,
            "is_badfilter": r.is_badfilter,
            "is_important": r.is_important,
            "domains": r.domains,
            "source": r.source,
            "options": r.options,
        }
        for r in rules
    ]
    path = cache_path(url, src_sha)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def parse_source_cached(lines: Iterable[str], category_hint: str, source: str,
                        url: str = "", use_stage_cache: bool = True) -> list[Rule]:
    """带阶段缓存的解析入口。

    use_stage_cache=False 时退化为原 parse_source 行为（离线/调试场景）。
    """
    if use_stage_cache and url:
        text = "\n".join(lines)
        src_sha = _source_sha256(text)
        cached = load_parsed(url, src_sha)
        if cached is not None:
            return cached

    rules = [
        r for r in (parse_line(line, category_hint=category_hint, source=source) for line in lines)
        if r is not None
    ]
    if use_stage_cache and url:
        save_parsed(url, _source_sha256("\n".join(lines)), rules)
    return rules
