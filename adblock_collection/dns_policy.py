"""DNS 输出安全分级。

把每条规则按 DNS 可表达性分为 REJECT（绝不进 DNS）、SAFE 与 CONDITIONAL 三档
（CONDITIONAL 已不再产出，保留常量仅为向后兼容），并给出 confidence（0~1）。
再结合 config 中的 dns_policy.level 决定最终是否进入 hosts / domains 文件。目的是在
「宁愿少拦截、不要误拦截」原则下，避免把只应阻断某路径或带作用域限制（如
$third-party）的规则错误地升级成整域拦截。

分级依据（参考 Adblock 语义）：

- REJECT  : CSS 元素隐藏、脚本注入、正则、重定向、含路径的网络规则，
            以及带动作/修饰选项（$csp/$removeparam/$replace/$empty…）、作用域限定选项
            （$domain/$from/$to/$top/$denyallow/$ipaddress/$method/$app/$dnstype）、
            匹配方式限定（$cname）、资源类型选项（$script/$image/$websocket/$fetch…）、
            第一/第三方限定（$third-party）或任何未识别修饰符的规则，取反形式
            （$~script/$~third-party）同理。DNS 只能看到域名，整域拦截会严重误伤，
            直接拒绝。
- SAFE    : 纯域名网络规则（||ads.example.com^），整域拦截语义等价，confidence=1.0。
            仅带「整域语义」修饰（$all/$important/$match-case，不限定类型与作用域）
            的规则语义等价于纯域名，同样归为 SAFE。仅带导航/弹窗修饰
            （$popup/$doc/$document）的单域名规则在用户确认放宽后按整域拦截输出。

未知修饰符采用「失败即拒绝（fail-closed）」：可升级为整域拦截的修饰符是一份显式
白名单（整域语义 + 导航语义 + 注解），任何不在白名单中的选项都按不可翻译拒绝。
这样新增或遗漏的修饰符（如 uBO `$top`、AdGuard `$stealth`/`$strict-first-party`）
不会因为「未识别」而被误升级成整域拦截。早期版本会把未知修饰符回退为 CONDITIONAL
并在 safe 档接受，属于 fail-open，已废弃。

策略等级（config 的 dns_policy.level）：

- all        : 仅接受纯域名 SAFE（含整域语义修饰）。最保守的向后兼容默认。
- safe       : 接受 SAFE；导航/弹窗类置信度 0.8，strict-safe 档下被排除。
- strict-safe: 仅接受置信度 >= 0.9 的纯域名 SAFE，最不易误杀。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .rules import _NET_DOMAIN_RE, _PURE_DOMAIN_RE, Rule

# 置信度常量
CONF_PURE_DOMAIN = 1.0
CONF_DOMAIN_MODIFIER = 0.8
CONF_REJECT = 0.0

# 质量分级三档
DNS_SAFE = "SAFE"
DNS_CONDITIONAL = "CONDITIONAL"
DNS_REJECT = "REJECT"

# 策略等级 -> 参数
DNS_LEVELS = {
    "all": {"min_confidence": 0.0, "allow_modifier": False},
    "safe": {"min_confidence": 0.8, "allow_modifier": True},
    "strict-safe": {"min_confidence": 0.9, "allow_modifier": False},
}
DEFAULT_LEVEL = "all"

# 非阻断型「动作/修饰」选项：带这些选项的规则不拦截域名，只改写请求或响应内容
# （如 $removeparam 去参、$csp 注入响应头、$replace 改写响应体）。它们即使写成
# 单域名规则也绝不能升级为 DNS 整域拦截，否则会造成整站误杀。
NON_BLOCKING_MODIFIERS = frozenset(
    {
        "removeparam",
        "replace",
        "csp",
        "permissions",
        "cookie",
        "set-cookie",
        "header",
        "removeheader",
        "addheader",
        "urltransform",
        "uritransform",
        "urlskip",
        "empty",
        "generichide",
        "specifichide",
        "elemhide",
        "content",
        "inline-script",
        "inline-font",
        "genericblock",
        # AdGuard 追踪保护/请求改写类修饰符：只改写行为，不阻断请求
        "stealth",
        "jsinject",
        "jsonprune",
        "xmlprune",
        "referrerpolicy",
        "urlblock",
        # AdGuard DNS 改写：重写响应而非阻断请求，DNS 层无法表达，硬拒绝
        "dnsrewrite",
        # uBO 旧名：$queryprune 等价于 $removeparam
        "queryprune",
        # uBO/AdGuard 短别名，等价于上面的非阻断选项
        "ghide",
        "shide",
        "ehide",
    }
)

# 整域语义修饰：只调整优先级或大小写匹配，不限定资源类型，也不限定作用域。
# 形如 ||ads.example.com^$all 的规则阻断到该域名的全部请求，DNS 整域拦截语义等价，
# 因而可归入 SAFE 而不是被当成作用域受限的 CONDITIONAL 丢弃。
WHOLE_DOMAIN_MODIFIERS = frozenset({"all", "important", "match-case"})

# 导航/弹窗语义修饰：$popup 拦截弹窗，$doc/$document 拦截页面加载，$popunder 为
# AdGuard 同义的旧写法。它们都只针对「打开页面」这一动作，常见于广告与跳转域；
# DNS 无法区分请求类型，把这类单域名规则按整域拦截处理，属于用户确认后的放宽策略。
# 与其它类型/作用域选项混用时不算。
NAVIGATION_DOMAIN_MODIFIERS = frozenset(
    {"popup", "popunder", "doc", "document"}
)

# 可整域表达的修饰符白名单：整域语义 + 导航语义的并集。规则只带这些选项时按整域
# 拦截输出；其余任何选项（作用域/类型/动作/未知）都 fail-closed 拒绝。
DNS_TRANSLATABLE_MODIFIERS = WHOLE_DOMAIN_MODIFIERS | NAVIGATION_DOMAIN_MODIFIERS

_OPTION_RE = re.compile(r"\$([^$]*)$")

# 元数据/注解类选项：仅标注规则来源或拦截原因，不改变匹配与拦截语义，分类时忽略。
# 例如 `||x^$all,reason=malicious` 语义等同于 `||x^$all`。
METADATA_OPTIONS = frozenset({"reason"})

# 正则 / 重定向类选项：规则无法翻译为域名语义，硬拒绝。
_REGEX_REDIRECT_MODIFIERS = frozenset(
    {"regexp", "redirect", "redirect-rule", "rewrite"}
)

# 作用域限定选项：DNS 只能按整域拦截，无法表达「仅在某来源站点 / 某目标域名 /
# 某 IP / 某请求方法 / 某 App / 某 DNS 记录类型 / 某顶层文档下生效」。带这些选项的
# 规则一旦升级为 DNS 拦截，会波及作用域之外的全部正常流量，属于误拦截，必须硬拒绝。
SCOPED_MODIFIERS = frozenset(
    {
        "domain",
        "from",
        "to",
        "top",
        "denyallow",
        "ipaddress",
        "method",
        "app",
        "dnstype",
        # AdGuard 作用域限定：按网络/客户端/客户端标签限定生效范围，DNS 无法区分
        "network",
        "client",
        "ctag",
    }
)

# 匹配方式限定选项：$cname 依据 CNAME 链而非请求 URL 匹配目标，与整域拦截语义不
# 等价（同一 IP/域名的正常流量会被误伤），硬拒绝。
MATCH_METHOD_MODIFIERS = frozenset({"cname"})

# 资源类型选项：限定规则只对某类请求生效（$script / $image / $websocket / $fetch …）。
# DNS 只能整域拦截，无法区分请求类型，升级会波及同域下的其它正常请求，属于误拦截，
# 因此硬拒绝。$popup/$doc/$document 属导航语义，单独由 NAVIGATION_DOMAIN_MODIFIERS
# 处理，不在此列。
RESOURCE_TYPE_MODIFIERS = frozenset(
    {
        "script",
        "image",
        "stylesheet",
        "css",
        "font",
        "media",
        "audio",
        "video",
        "object",
        "object-subrequest",
        "xmlhttprequest",
        "xhr",
        "fetch",
        "websocket",
        "webrtc",
        "ping",
        "beacon",
        "other",
        "subdocument",
        "frame",
        "inline-script",
        "inline-font",
        # AdGuard 内容类型修饰符
        "extension",
        "hls",
        "mp4",
    }
)

# 第一/第三方限定选项：DNS 无法区分请求来源关系，升级会误伤同域的合法请求，硬拒绝。
PARTY_MODIFIERS = frozenset(
    {
        "third-party",
        "first-party",
        "strict1p",
        "strict3p",
        "strict-first-party",
        "strict-third-party",
        "1p",
        "3p",
    }
)


@dataclass
class DnsVerdict:
    eligibility: str
    confidence: float
    reason: str

    @property
    def eligible(self) -> bool:
        return self.eligibility != DNS_REJECT


def classify_dns(rule: Rule) -> DnsVerdict:
    """按规则形态判定其 DNS 可表达性与置信度（不考虑例外标记，例外由调用方处理）。"""
    if rule.kind in ("css", "scriptlet"):
        reason = "css_rule" if rule.kind == "css" else "script_rule"
        return DnsVerdict(DNS_REJECT, CONF_REJECT, reason)
    if rule.kind != "network":
        return DnsVerdict(DNS_REJECT, CONF_REJECT, "non_network_rule")

    # 选项名统一去掉取反前缀并忽略纯注解（$reason=）后再比对：$~third-party /
    # $~script 这类「排除某类型」同样限定了作用范围，不能当作未知修饰而放宽。
    sem = {
        k.lstrip("~").lower()
        for k in rule.options
        if k.lstrip("~").lower() not in METADATA_OPTIONS
    }
    if sem:
        # 正则 / 重定向类规则无法转 DNS（白名单例外也转不出域名语义）
        if sem & _REGEX_REDIRECT_MODIFIERS:
            return DnsVerdict(DNS_REJECT, CONF_REJECT, "regex_or_redirect_rule")
        # 动作/修饰型选项不阻断域名，禁止升级为整域拦截
        if sem & NON_BLOCKING_MODIFIERS:
            return DnsVerdict(DNS_REJECT, CONF_REJECT, "non_blocking_modifier")
        # 作用域限定选项无法在 DNS 层表达，禁止升级为整域拦截
        if sem & SCOPED_MODIFIERS:
            return DnsVerdict(DNS_REJECT, CONF_REJECT, "scoped_modifier")
        # 匹配方式限定选项（$cname）无法在 DNS 层表达，硬拒绝
        if sem & MATCH_METHOD_MODIFIERS:
            return DnsVerdict(DNS_REJECT, CONF_REJECT, "match_method_modifier")
        # 资源类型限定选项（$script/$websocket/$fetch…）无法在 DNS 层表达，硬拒绝
        if sem & RESOURCE_TYPE_MODIFIERS:
            return DnsVerdict(DNS_REJECT, CONF_REJECT, "resource_type_modifier")
        # 第一/第三方限定选项无法在 DNS 层表达，硬拒绝
        if sem & PARTY_MODIFIERS:
            return DnsVerdict(DNS_REJECT, CONF_REJECT, "party_modifier")

    # 含路径的网络规则：DNS 只能看到域名，整域拦截会误伤，拒绝
    m = _NET_DOMAIN_RE.search(rule.raw)
    if m:
        after = _OPTION_RE.sub("", rule.raw[m.end() :])
        if "/" in after:
            return DnsVerdict(DNS_REJECT, CONF_REJECT, "path_rule")

    # 纯域名规则
    if _PURE_DOMAIN_RE.match(rule.raw):
        return DnsVerdict(DNS_SAFE, CONF_PURE_DOMAIN, "pure_domain")

    # 仅带整域语义修饰（$all/$important/$match-case）的纯域名规则
    if sem and sem <= WHOLE_DOMAIN_MODIFIERS:
        if _PURE_DOMAIN_RE.match(_OPTION_RE.sub("", rule.raw)):
            return DnsVerdict(DNS_SAFE, CONF_PURE_DOMAIN, "pure_domain_modifier")

    # 仅带注解选项（$reason=…）的纯域名规则：注解不改变拦截语义
    if rule.options and not sem:
        if _PURE_DOMAIN_RE.match(_OPTION_RE.sub("", rule.raw)):
            return DnsVerdict(DNS_SAFE, CONF_PURE_DOMAIN, "pure_domain_modifier")

    # 仅带整域/导航语义修饰（$all/$important/$match-case/$popup/$doc/$document 及其
    # 组合）的纯域名规则：整域拦截语义等价，用户确认放宽后输出；含导航修饰时置信度
    # 略低，strict-safe 档仍会排除。
    if sem and sem <= DNS_TRANSLATABLE_MODIFIERS:
        if _PURE_DOMAIN_RE.match(_OPTION_RE.sub("", rule.raw)):
            return DnsVerdict(
                DNS_SAFE, CONF_DOMAIN_MODIFIER, "navigation_domain_modifier"
            )

    # 含未识别修饰符的规则一律拒绝（fail-closed）：可升级为整域拦截的修饰符是
    # 一份显式白名单（上面的整域语义 + 导航语义），任何不在白名单中的选项都可能
    # 限定类型/作用域/动作（如 $top、$stealth、$strict-first-party…），DNS 无法
    # 表达，升级成整域拦截会导致误杀。宁可漏收，也不因遗漏新修饰符而误拦截。
    if sem:
        return DnsVerdict(DNS_REJECT, CONF_REJECT, "unknown_modifier")

    return DnsVerdict(DNS_REJECT, CONF_REJECT, "untranslatable")


def resolve_policy(policy: dict | None) -> dict:
    """返回有效的策略字典，缺失或未知字段用默认等级补齐。"""
    if policy is None:
        return dict(DNS_LEVELS[DEFAULT_LEVEL])
    level = policy.get("level", DEFAULT_LEVEL)
    if level not in DNS_LEVELS:
        level = DEFAULT_LEVEL
    base = dict(DNS_LEVELS[level])
    base["level"] = level
    if "min_confidence" in policy:
        base["min_confidence"] = float(policy["min_confidence"])
    if "allow_modifier" in policy:
        base["allow_modifier"] = bool(policy["allow_modifier"])
    return base


def is_dns_eligible(rule: Rule, policy: dict | None = None) -> bool:
    """阻塞型规则是否应进入 DNS/Hosts/Domains 输出。

    未知修饰符已在 classify_dns 阶段按 fail-closed 归入 REJECT，因此这里只需判断
    置信度是否达到策略阈值。``allow_modifier`` 字段仍保留在策略字典中以兼容既有
    配置与审计报告，但不再影响分级。
    """
    verdict = classify_dns(rule)
    if not verdict.eligible:
        return False
    policy = resolve_policy(policy)
    return verdict.confidence >= policy.get("min_confidence", 0.0)


def load_dns_policy(config_path: Path) -> dict:
    """从 config 文件读取 dns_policy 段，缺省回退到默认等级。"""
    import yaml

    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    raw = data.get("dns_policy", {}) or {}
    level = raw.get("level", DEFAULT_LEVEL)
    if level not in DNS_LEVELS:
        level = DEFAULT_LEVEL
    spec = dict(DNS_LEVELS[level])
    spec["level"] = level
    if "min_confidence" in raw:
        spec["min_confidence"] = float(raw["min_confidence"])
    if "allow_modifier" in raw:
        spec["allow_modifier"] = bool(raw["allow_modifier"])
    return spec
