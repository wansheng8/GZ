"""上游列表加载、缓存、合并、去重、badfilter 处理与分类统计。"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

import requests

from .pipeline import parse_source_cached
from .rules import Rule, parse_line

LOG = logging.getLogger("adblock_collection")

DOWNLOAD_TIMEOUT = (10, 30)
MAX_RETRIES = 2
CACHE_DIR = Path(".cache/sources")


def load_sources(config_path: Path) -> list[dict]:
    import yaml

    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("sources", [])


def _cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return CACHE_DIR / digest


def fetch_source(url: str, use_cache: bool = True, offline: bool = False, mirror: Optional[str] = None) -> list[str]:
    """下载上游列表，支持本地缓存、离线模式与备用镜像。

    主源下载失败时，若提供 mirror 则自动尝试镜像；两者皆失败且存在有效缓存时，
    回退使用过期缓存并打 WARN，避免数据完全缺失。
    """
    cache = _cache_path(url)
    if use_cache and cache.exists() and offline:
        LOG.info("使用缓存: %s", url)
        return cache.read_text(encoding="utf-8", errors="replace").splitlines()
    if offline:
        LOG.warning("离线模式且缓存缺失: %s", url)
        return []

    candidates = [url]
    if mirror:
        candidates.append(mirror)

    last_err: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        for cand in candidates:
            try:
                resp = requests.get(
                    cand,
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
                if cand != url:
                    LOG.info("镜像源成功: %s", cand)
                return text.splitlines()
            except (requests.RequestException, ValueError) as exc:
                last_err = exc
                LOG.warning("下载失败 (%s/%s) %s: %s", attempt, MAX_RETRIES, cand, exc)
        time.sleep(2 * attempt)
    # 主源与镜像均失败，回退到过期缓存
    if cache.exists():
        LOG.warning("主源与镜像均失败，回退使用过期缓存: %s", url)
        return cache.read_text(encoding="utf-8", errors="replace").splitlines()
    LOG.error("放弃下载 %s: %s", url, last_err)
    return []


def parse_source(lines: Iterable[str], category_hint: str, source: str) -> list[Rule]:
    return [r for r in (parse_line(line, category_hint=category_hint, source=source) for line in lines) if r is not None]


def collect(config_path: Path, use_cache: bool = True, offline: bool = False,
            use_stage_cache: bool = True) -> dict[str, list[Rule]]:
    """下载并解析所有上游列表，返回 {"all": [(name, rules), ...], "_failed": [name, ...]}。

    use_stage_cache=True 时，未变化的上游会复用 .cache/parsed 下的解析结果，跳过重复解析。
    """
    sources = load_sources(config_path)
    result: dict[str, list[Rule]] = defaultdict(list)
    failed: list[str] = []
    for src in sources:
        name = src.get("name", "unknown")
        url = src.get("url")
        if not url:
            continue
        LOG.info("处理上游列表: %s", name)
        lines = fetch_source(url, use_cache=use_cache, offline=offline, mirror=src.get("mirror"))
        if not lines:
            failed.append(name)
            continue
        rules = parse_source_cached(
            lines, src.get("category", "other"), name,
            url=url, use_stage_cache=use_stage_cache,
        )
        result["all"].append((name, rules))
    result["_failed"] = failed
    return result


def dedupe(rules: Iterable[Rule]) -> list[Rule]:
    """基于规范化键去重，保留首次出现的原始写法，并合并所有同源规则的上游来源。

    合并来源可让后续血缘/置信度统计正确反映「该规则出现在哪些上游列表」，
    避免去重后仅保留单一 source 导致跨源信息丢失。
    """
    seen: dict[str, Rule] = {}
    order: list[str] = []
    for rule in rules:
        if rule.norm not in seen:
            seen[rule.norm] = rule
            order.append(rule.norm)
        else:
            prev = seen[rule.norm]
            if rule.source and rule.source not in prev.sources:
                prev.sources.append(rule.source)
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


_CSS_SELECTOR_RE = re.compile(r"[#@#?]+(.+)$")


def remove_redundant_css(rules: Iterable[Rule]) -> list[Rule]:
    """消除 css 规则中的同域同基础选择器冗余。

    仅对「单限定域名 + 纯类名选择器（以 . 开头、无空格/逗号/属性选择器）」做去重，
    保留首次出现的规则；复杂选择器（含逗号、属性、伪类组合）不参与，避免误删。
    """
    seen: dict[tuple[str, str], Rule] = {}
    kept: list[Rule] = []
    removed = 0
    for r in rules:
        if r.kind != "css" or r.is_exception or not r.domains or len(r.domains) != 1:
            kept.append(r)
            continue
        m = _CSS_SELECTOR_RE.search(r.raw)
        if not m:
            kept.append(r)
            continue
        sel = m.group(1).strip()
        # 仅当选择器是单一纯类名（无空格、逗号、方括号、冒号）时才视为可去重
        if " " in sel or "," in sel or "[" in sel or ":" in sel or not sel.startswith("."):
            kept.append(r)
            continue
        key = (r.domains[0], sel)
        if key in seen:
            removed += 1
            continue
        seen[key] = r
        kept.append(r)
    if removed:
        LOG.info("冗余 css 规则移除: %d", removed)
    return kept


def apply_allowlist(rules: Iterable[Rule], allow: Iterable[str]) -> list[Rule]:
    """按误杀回归白名单强制放行：剔除整域阻断规则中命中 allow 清单（含祖先域）的网络规则。

    仅作用于网络阻断规则；例外（@@）与元素隐藏类规则不受影响。符合「宁愿少拦截」原则——
    allow 清单中的知名站点（google/microsoft/office 等）绝不会被整域封锁。
    """
    allow_set = {str(d).strip().lower() for d in allow if d}
    if not allow_set:
        return list(rules)
    kept: list[Rule] = []
    for r in rules:
        if r.kind == "network" and not r.is_exception and r.domains and len(r.domains) == 1:
            dom = r.domains[0].lower()
            parts = dom.split(".")
            if any(".".join(parts[i:]) in allow_set for i in range(len(parts))):
                continue
        kept.append(r)
    return kept


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
