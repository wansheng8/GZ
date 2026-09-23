"""上游列表加载、缓存、合并、去重、badfilter 处理与分类统计。"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import requests

from .pipeline import parse_source_cached
from .preprocess import preprocess
from .rules import (
    _ELEMENT_SEP_RE,
    _PURE_DOMAIN_RE,
    Rule,
    _option_start,
    _split_options,
)

LOG = logging.getLogger("adblock_collection")

DOWNLOAD_TIMEOUT = (10, 30)
MAX_RETRIES = 2
CACHE_DIR = Path(".cache/sources")

# 自定义名单：固定目录 config/lists/ 下的两个文件，按来源名并入规则集。
# 白名单以 @@ 例外规则表达，黑名单以普通阻断规则表达；两者均支持裸域名简写。
CUSTOM_LIST_FILES = (
    ("LocalBlocklist", "lists/blocklist.txt"),
    ("LocalAllowlist", "lists/allowlist.txt"),
)
_DOMAIN_ONLY_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", re.IGNORECASE
)


def _normalize_custom_line(line: str, is_allow: bool) -> str | None:
    """把自定义名单的一行规范成 adblock 规则；裸域名按方向补全。

    黑名单裸域名 ``example.com`` -> ``||example.com^``；
    白名单裸域名 ``example.com`` -> ``@@||example.com^``。注释与空行返回 None。
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("!"):
        return None
    # 以 # 开头且不是元素隐藏分隔符（##/#?#/#$#/#%#/#@#）的行视为注释
    if stripped.startswith("#") and _ELEMENT_SEP_RE.match(stripped) is None:
        return None
    if _DOMAIN_ONLY_RE.match(stripped):
        return f"@@||{stripped}^" if is_allow else f"||{stripped}^"
    return stripped


def load_custom_lists(
    config_path: Path, use_stage_cache: bool = True
) -> list[tuple[str, list[Rule]]]:
    """加载 config/lists/ 下的自定义黑/白名单，返回 [(来源名, 规则), ...]。

    文件缺失或读取失败时记日志并跳过，保证构建继续。
    """
    loaded: list[tuple[str, list[Rule]]] = []
    for name, rel in CUSTOM_LIST_FILES:
        path = config_path.parent / rel
        if not path.exists():
            LOG.info("自定义名单不存在，跳过: %s", path)
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            LOG.warning("读取自定义名单失败: %s: %s", path, exc)
            continue
        is_allow = name == "LocalAllowlist"
        lines = []
        for raw in text.splitlines():
            norm = _normalize_custom_line(raw, is_allow)
            if norm is not None:
                lines.append(norm)
        rules = parse_source_cached(
            lines, "other", name, url=str(path), use_stage_cache=use_stage_cache
        )
        loaded.append((name, rules))
        LOG.info("纳入自定义名单: %s (%d 条)", path, len(rules))
    return loaded


def load_sources(config_path: Path) -> list[dict]:
    import yaml

    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("sources", [])


def _cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return CACHE_DIR / digest


def fetch_source(
    url: str,
    use_cache: bool = True,
    offline: bool = False,
    mirror: str | None = None,
) -> list[str]:
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

    last_err: Exception | None = None
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
                if stripped.startswith(("<!DOCTYPE", "<html")):
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


def collect(
    config_path: Path,
    use_cache: bool = True,
    offline: bool = False,
    use_stage_cache: bool = True,
) -> dict[str, list[Rule]]:
    """下载并解析所有上游列表，返回 {"all": [(name, rules), ...], "_failed": [name, ...]}。

    use_stage_cache=True 时，未变化的上游会复用 .cache/parsed 下的解析结果，跳过重复解析。
    """
    sources = load_sources(config_path)
    result: dict[str, list[Rule]] = defaultdict(list)
    failed: list[str] = []

    # 本地增强规则：固定纳入 config/local_rules.txt（若存在），用于补充上游未覆盖的
    # 元素隐藏/网页版直播广告等规则，不会被上游覆盖，也不影响白名单放行。
    local_path = config_path.parent / "local_rules.txt"
    if local_path.exists():
        try:
            ltext = local_path.read_text(encoding="utf-8", errors="replace")
            llines = [
                ln
                for ln in ltext.splitlines()
                if ln.strip()
                and not ln.lstrip().startswith("#")
                and not ln.lstrip().startswith("!")
            ]
            lrules = parse_source_cached(
                llines,
                "other",
                "LocalRules",
                url=str(local_path),
                use_stage_cache=use_stage_cache,
            )
            result["all"].append(("LocalRules", lrules))
            LOG.info("纳入本地增强规则: %s (%d 条)", local_path, len(lrules))
        except OSError as exc:
            LOG.warning("读取本地增强规则失败: %s", exc)

    # 自定义黑/白名单：config/lists/ 下固定两文件，在去重前并入，参与全流水线。
    for name, rules in load_custom_lists(config_path, use_stage_cache=use_stage_cache):
        result["all"].append((name, rules))

    # 并行下载所有上游（下载是最大的耗时瓶颈，顺序下载会让失败源的重试超时拖垮整体）
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _resolve_include(target: str) -> tuple[list[str], str] | None:
        """``!#include`` 回调：按 URL 抓取子列表（复用缓存/离线/镜像回退）。"""
        sub = fetch_source(target, use_cache=use_cache, offline=offline)
        if not sub:
            return None
        return sub, target

    def _fetch(src):
        name = src.get("name", "unknown")
        url = src.get("url")
        if not url:
            return name, None
        try:
            lines = fetch_source(
                url, use_cache=use_cache, offline=offline, mirror=src.get("mirror")
            )
            # 解析 !#if/!#else/!#endif 条件编译并内联 !#include 子列表
            lines = preprocess(lines, base_url=url, resolve_include=_resolve_include)
        except Exception as exc:  # noqa: BLE001 - 单源异常不应中断整体构建
            LOG.warning("源处理异常 %s: %s", name, exc)
            return name, None
        return name, lines

    fetch_results: dict[str, list[str] | None] = {}
    with ThreadPoolExecutor(max_workers=min(16, max(4, len(sources)))) as ex:
        futures = {ex.submit(_fetch, src): src for src in sources}
        for fut in as_completed(futures):
            name, lines = fut.result()
            fetch_results[name] = lines

    for src in sources:
        name = src.get("name", "unknown")
        lines = fetch_results.get(name)
        if not lines:
            failed.append(name)
            continue
        LOG.info("处理上游列表: %s", name)
        rules = parse_source_cached(
            lines,
            src.get("category", "other"),
            name,
            url=src.get("url"),
            use_stage_cache=use_stage_cache,
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


def _badfilter_target(norm: str) -> str | None:
    """从 badfilter 规则的规范化键还原其要抵消的目标键。

    规范化键形如 ``prefix$opt1,opt2``（选项已排序）。需按 ``_split_options`` 切分，
    避免取值内逗号被误拆；去掉 badfilter 后若已无其它选项，需连同 ``$`` 一起丢弃，
    才能匹配无选项规则 ``prefix``（如 ``||ads.com^$badfilter`` 抵消 ``||ads.com^``）。
    同时兼容遗留写法 ``||domain^,badfilter``（无 ``$`` 选项段）。
    """
    if norm.endswith(",badfilter"):
        return norm[: -len(",badfilter")]
    idx = _option_start(norm)
    if idx is None:
        return None
    parts = [
        p
        for p in _split_options(norm[idx + 1 :])
        if p.lstrip("~").split("=", 1)[0].strip().lower() != "badfilter"
    ]
    if not parts:
        return norm[:idx]
    return norm[:idx] + "$" + ",".join(parts)


def apply_badfilter(rules: Iterable[Rule]) -> list[Rule]:
    """移除被 badfilter 标记抵消的规则。

    badfilter 规则格式为与目标规则完全相同但追加了 ,badfilter 选项，
    用于让订阅者停用上游某条规则。
    """
    rule_list = list(rules)
    badfilters: set[str] = {
        target
        for r in rule_list
        if r.is_badfilter and (target := _badfilter_target(r.norm))
    }

    if not badfilters:
        return rule_list
    kept: list[Rule] = []
    removed = 0
    for r in rule_list:
        if r.is_badfilter:
            removed += 1
            continue
        if r.norm in badfilters:
            removed += 1
            continue
        kept.append(r)
    LOG.info("badfilter 移除规则: %d", removed)
    return kept


# 视为「整域全量拦截」的选项集合：仅 $important 不改变拦截范围，只是提升优先级。
_FULL_BLOCK_OPTIONS = frozenset({"important"})


def _pattern_part(raw: str) -> str:
    """返回规则去掉 ``$options`` 后的匹配模式部分。"""
    idx = _option_start(raw)
    return raw if idx is None else raw[:idx]


def _is_full_domain_block(r: Rule) -> bool:
    """该规则是否拦截目标域名的**全部**请求（可安全覆盖其子域）。

    必须是「纯域名」模式（``||domain^`` / ``||domain``）。带路径的规则
    （``||domain/path``）只拦截部分请求，既不能覆盖子域、也不能顶替同域纯域名规则，
    否则会把 ``||doubleclick.net^`` 之类的整域封锁误删，导致该域名彻底失守。
    """
    if r.kind != "network" or r.is_exception:
        return False
    if set(r.options) - _FULL_BLOCK_OPTIONS:
        return False
    return bool(_PURE_DOMAIN_RE.search(_pattern_part(r.raw)))


def remove_redundant_domains(rules: Iterable[Rule]) -> list[Rule]:
    """消除被「整域全量拦截」覆盖的冗余单域名网络规则。

    仅当同一域名（或某祖先域）存在纯域名全量拦截（``||a.com^`` /
    ``||a.com^$important``）时，才删除被其覆盖的窄规则（``||a.com^$image``、
    ``||a.com/path``、``||sub.a.com^`` 等）。同一域名同时存在普通与 ``$important``
    全量拦截时只保留 ``$important`` 版本。带路径的规则（``||a.com/path^``）不是全量
    拦截，既不覆盖子域也不顶替纯域名规则。例外（@@）规则始终保留。
    """
    from .domain_fold import fold_domains

    kept, report = fold_domains(rules, protect_exception_children=False)
    if report.folded:
        LOG.info("冗余域名规则移除: %d", report.folded)
    return kept


_CSS_SELECTOR_RE = re.compile(r"[#$@%#?]+(.+)$")


def remove_redundant_css(rules: Iterable[Rule]) -> list[Rule]:
    """消除 css 规则中的同域同基础选择器冗余。

    仅对「单限定域名 + 纯类名选择器（以 . 开头、无空格/逗号/属性/伪类/声明）」做去重，
    保留首次出现的规则；复杂选择器（含逗号、属性、伪类组合或 #$# 带 CSS 声明）不参与，
    避免误删。
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
        # 仅当选择器是单一纯类名（无空格、逗号、方括号、冒号、CSS 声明）时才视为可去重
        if (
            " " in sel
            or "," in sel
            or "[" in sel
            or ":" in sel
            or "{" in sel
            or not sel.startswith(".")
        ):
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
    """按误杀回归白名单强制放行：仅放行「域名精确等于」allow 清单项的整域阻断规则。

    使用精确匹配而非祖先匹配——allow 中的 tencent.com 只放行 ||tencent.com^ 本身，
    其广告/追踪子域（ad.tencent.com、analytics.tencent.com 等）仍会被正常拦截，避免
    「大站广告也不拦」的半截拦截问题。仅作用于网络阻断规则；例外与元素隐藏不受影响。
    符合「宁愿少拦截、但不放过子域追踪」的原则。
    """
    allow_set = {str(d).strip().lower() for d in allow if d}
    if not allow_set:
        return list(rules)
    kept: list[Rule] = []
    for r in rules:
        if (
            r.kind == "network"
            and not r.is_exception
            and r.domains
            and len(r.domains) == 1
        ):
            dom = r.domains[0].lower()
            if dom in allow_set:
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


_WILDCARD_BLOCKLIST_RE = re.compile(
    r"^(?:\*|#[@$%?]{0,2}#\*)"  # 全局/整页元素隐藏（行首无域名限定，覆盖 ##/#@#/#$#/#%#/#?# 等）
    r"|#[@$%?]{0,2}#(?:body|html|head)\b"  # 隐藏整页主体元素（任意域名前缀）
    r"|^#[@$%?]{0,2}#\["  # 无域名限定的属性选择器（如 ##[class*="ad"]），易整站误伤
)
# 域名级通配（如 *.example.com##、*##、*#$# 等）同样禁止
_DOMAIN_WILDCARD_RE = re.compile(r"^(?:\*|[*\w.-]*\*[*\w.-]*)\s*#[@$%?]{0,2}#")
# 选择器内出现裸 * 通配（除 [class*="x"] 这类属性包含匹配外）禁止
_SELECTOR_WILDCARD_RE = re.compile(r"(^|\s)\*(,|\s|$|>)")


def _validate_lines(lines: Iterable[str], label: str) -> list[str]:
    """校验一组规则的误伤通配，返回违规行列表（含标签与行号）。"""
    violations: list[str] = []
    for idx, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith(("#", "!")):
            continue
        if _WILDCARD_BLOCKLIST_RE.search(line) or _DOMAIN_WILDCARD_RE.search(line):
            violations.append(f"{label}:{idx}: {line}")
            continue
        # 仅对元素隐藏/扩展 CSS/HTML 过滤规则检查选择器内裸通配
        m = _ELEMENT_SEP_RE.search(line)
        if not m or m.group(1).startswith("#@"):
            continue
        if m.group(1) in ("#%#", "#@%#"):
            continue  # JS 注入，后接脚本代码
        selector = line[m.end() :]
        if not selector:
            continue
        # CSS 注入的 { ... } 是声明部分，仅校验其前的选择器
        selector = selector.split("{", 1)[0]
        # 移除合法的属性包含匹配 [class*="x"] 后再判断裸 *
        scrubbed = re.sub(r'\[[^\]]*\*="[^"]*"\]', "", selector)
        if _SELECTOR_WILDCARD_RE.search(scrubbed):
            violations.append(f"{label}:{idx}: {line}")
    return violations


def validate_local_rules(config_path: Path) -> list[str]:
    """校验 config/local_rules.txt，禁止可能误伤整页/整站的通配规则。

    返回违规行列表（非空即应阻断构建）。覆盖 ##、#?#、#$#、#%#、$$ 等全部装饰分隔符；
    JS 注入（#%#）后是脚本而非选择器，不参与通配校验；例外规则（#@#）会减少拦截，放行。
    允许的属性包含匹配（如 [class*="ad"]）在被限定的选择器中视为安全。
    """
    local_path = config_path.parent / "local_rules.txt"
    if not local_path.exists():
        return []
    return _validate_lines(
        local_path.read_text(encoding="utf-8", errors="replace").splitlines(),
        local_path.name,
    )


def validate_custom_lists(config_path: Path) -> list[str]:
    """校验 config/lists/ 下的自定义黑/白名单，禁止可能误伤整页/整站的通配规则。

    裸域名简写先按方向补全为规则再校验；文件缺失时跳过。
    """
    violations: list[str] = []
    for name, rel in CUSTOM_LIST_FILES:
        path = config_path.parent / rel
        if not path.exists():
            continue
        is_allow = name == "LocalAllowlist"
        normalized = [
            norm
            for raw in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if (norm := _normalize_custom_line(raw, is_allow)) is not None
        ]
        violations.extend(_validate_lines(normalized, path.name))
    return violations
