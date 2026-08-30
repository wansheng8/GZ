"""上游列表加载、缓存、合并、去重、badfilter 处理与分类统计。"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

import requests

from .rules import Rule, parse_line

LOG = logging.getLogger("adblock_collection")

DOWNLOAD_TIMEOUT = 60
MAX_RETRIES = 3
CACHE_DIR = Path(".cache/sources")


def load_sources(config_path: Path) -> list[dict]:
    import yaml

    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("sources", [])


def _cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return CACHE_DIR / digest


def fetch_source(url: str, use_cache: bool = True, offline: bool = False) -> list[str]:
    """下载上游列表，支持本地缓存与离线模式。"""
    cache = _cache_path(url)
    if use_cache and cache.exists():
        LOG.info("使用缓存: %s", url)
        return cache.read_text(encoding="utf-8", errors="replace").splitlines()
    if offline:
        LOG.warning("离线模式且缓存缺失: %s", url)
        return []

    last_err: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                timeout=DOWNLOAD_TIMEOUT,
                headers={"User-Agent": "adblock-rule-collection/1.0"},
            )
            resp.raise_for_status()
            text = resp.text
            # 跳过返回 HTML 而非过滤器列表的响应（如错误页、登录页）
            stripped = text.lstrip()
            if stripped.startswith("<!DOCTYPE") or stripped.startswith("<html"):
                raise ValueError("响应不是过滤器列表（疑似 HTML 页面）")
            if use_cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(text, encoding="utf-8")
            return text.splitlines()
        except (requests.RequestException, ValueError) as exc:
            last_err = exc
            LOG.warning("下载失败 (%s/%s) %s: %s", attempt, MAX_RETRIES, url, exc)
            time.sleep(2 * attempt)
    LOG.error("放弃下载 %s: %s", url, last_err)
    return []


def parse_source(lines: Iterable[str], category_hint: str, source: str) -> list[Rule]:
    return [r for r in (parse_line(line, category_hint=category_hint, source=source) for line in lines) if r is not None]


def collect(config_path: Path, use_cache: bool = True, offline: bool = False) -> dict[str, list[Rule]]:
    """下载并解析所有上游列表，by_category 以分类聚合，all 保存 (name, rules)。"""
    sources = load_sources(config_path)
    result: dict[str, list[Rule]] = defaultdict(list)
    for src in sources:
        name = src.get("name", "unknown")
        url = src.get("url")
        if not url:
            continue
        LOG.info("处理上游列表: %s", name)
        lines = fetch_source(url, use_cache=use_cache, offline=offline)
        if not lines:
            continue
        rules = parse_source(lines, src.get("category", "other"), name)
        result[src.get("category", "other")].extend(rules)
        result["all"].append((name, rules))
    return result


def dedupe(rules: Iterable[Rule]) -> list[Rule]:
    """基于规范化键去重，保留首次出现的原始写法。"""
    seen: dict[str, Rule] = {}
    order: list[str] = []
    for rule in rules:
        if rule.norm not in seen:
            seen[rule.norm] = rule
            order.append(rule.norm)
    return [seen[k] for k in order]


def apply_badfilter(rules: Iterable[Rule]) -> list[Rule]:
    """移除被 badfilter 标记抵消的规则。

    badfilter 规则格式为与目标规则完全相同但追加了 ,badfilter 选项，
    用于让订阅者停用上游某条规则。
    """
    badfilters: set[str] = set()
    for r in rules:
        if r.is_badfilter:
            # 选项已按字母排序，badfilter 可能位于开头或结尾，去掉该 token 即可还原目标键
            target = r.norm.replace(",badfilter", "").replace("badfilter,", "")
            if target.endswith("$badfilter"):
                target = target[: -len("badfilter")]
            badfilters.add(target)

    if not badfilters:
        return list(rules)
    kept: list[Rule] = []
    removed = 0
    for r in rules:
        if r.is_badfilter:
            removed += 1
            continue
        if r.norm in badfilters:
            removed += 1
            continue
        kept.append(r)
    LOG.info("badfilter 移除规则: %d", removed)
    return kept


def remove_redundant_domains(rules: Iterable[Rule]) -> list[Rule]:
    """消除冗余的纯域名网络规则。

    当 '||a.com^'（阻断）存在时，更具体的 '||sub.a.com^' 或 '||a.com/ads^'
    在阻断语义上冗余，但保留例外（@@）规则。仅对阻断型单域名网络规则做父域归并。
    """
    blocked: dict[str, Rule] = {}
    others: list[Rule] = []
    for r in rules:
        if r.kind == "network" and not r.is_exception and r.domains and len(r.domains) == 1:
            blocked[r.domains[0]] = r
        else:
            others.append(r)

    # 标记被父域覆盖的子域规则（无论是否带路径，主机名层面冗余即移除）
    covered: set[str] = set()
    for domain in blocked:
        parts = domain.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[i:])
            if parent in blocked:
                covered.add(domain)
                break
    kept_blocked = [r for d, r in blocked.items() if d not in covered]
    removed = len(covered)
    if removed:
        LOG.info("冗余域名规则移除: %d", removed)
    return kept_blocked + others


def source_stats(rules: Iterable[Rule]) -> dict[str, int]:
    """统计各上游来源贡献的规则数（按规范化去重后的来源计）。"""
    stats: dict[str, int] = defaultdict(int)
    for r in rules:
        if r.source:
            stats[r.source] += 1
    return dict(sorted(stats.items(), key=lambda kv: kv[1], reverse=True))


def split_lite(rules: Iterable[Rule], sources_meta: list[dict]) -> list[Rule]:
    """仅保留来自 lite 标记上游的规则。"""
    lite_sources = {s.get("name") for s in sources_meta if s.get("lite")}
    if not lite_sources:
        return list(rules)
    return [r for r in rules if r.source in lite_sources]


def category_stats(rules: Iterable[Rule]) -> dict[str, int]:
    stats: dict[str, int] = defaultdict(int)
    for r in rules:
        stats[r.category] += 1
    return dict(sorted(stats.items(), key=lambda kv: kv[1], reverse=True))


def kind_stats(rules: Iterable[Rule]) -> dict[str, int]:
    stats: dict[str, int] = defaultdict(int)
    for r in rules:
        stats[r.kind] += 1
    return dict(sorted(stats.items(), key=lambda kv: kv[1], reverse=True))
