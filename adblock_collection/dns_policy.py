"""DNS 输出安全分级。

把每条规则按 DNS 可表达性分为 REJECT（绝不进 DNS）、SAFE、CONDITIONAL 三档，
并给出 confidence（0~1）。再结合 config 中的 dns_policy.level 决定最终是否进入
hosts / domains 文件。目的是在「宁愿少拦截、不要误拦截」原则下，避免把只应阻断某
路径或带作用域限制（如 $third-party）的规则错误地升级成整域拦截。

分级依据（参考 Adblock 语义）：

- REJECT  : CSS 元素隐藏、脚本注入、正则、重定向、含路径的网络规则，
            以及带动作/修饰选项（$csp/$removeparam/$replace/$empty…）、作用域限定选项
            （$domain/$from/$to/$denyallow/$ipaddress/$method/$app/$dnstype）、匹配方式
            限定（$cname）、资源类型选项（$script/$image/$websocket/$fetch…）或
            第一/第三方限定（$third-party）的规则，取反形式（$~script/$~third-party）
            同理。DNS 只能看到域名，整域拦截会严重误伤，直接拒绝。
- SAFE    : 纯域名网络规则（||ads.example.com^），整域拦截语义等价，confidence=1.0。
            仅带「整域语义」修饰（$all/$important/$match-case，不限定类型与作用域）
            的规则语义等价于纯域名，同样归为 SAFE。仅带导航/弹窗修饰
            （$popup/$doc/$document）的单域名规则在用户确认放宽后按整域拦截输出。
- CONDITIONAL: 单域名规则带未识别修饰符时的保守回退档，confidence=0.8，
            是否进入 DNS 由策略的 allow_modifier 决定。资源类型/作用域/动作类
            选项已被 REJECT，因此该档实际只覆盖未知选项组合。

策略等级（config 的 dns_policy.level）：

- all        : 仅接受 SAFE（纯域名）。与旧版行为一致，最保守的向后兼容默认。
- safe       : 接受 SAFE + CONDITIONAL（min_confidence=0.8, allow_modifier=True）。
- strict-safe: 仅接受 SAFE（min_confidence=0.9, allow_modifier=False），最不易误杀。
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

_OPTION_RE = re.compile(r"\$([^$]*)$")

# 元数据/注解类选项：仅标注规则来源或拦截原因，不改变匹配与拦截语义，分类时忽略。
# 例如 `||x^$all,reason=malicious` 语义等同于 `||x^$all`。
METADATA_OPTIONS = frozenset({"reason"})

# 正则 / 重定向类选项：规则无法翻译为域名语义，硬拒绝。
_REGEX_REDIRECT_MODIFIERS = frozenset(
    {"regexp", "redirect", "redirect-rule", "rewrite"}
)

# 作用域限定选项：DNS 只能按整域拦截，无法表达「仅在某来源站点 / 某目标域名 /
# 某 IP / 某请求方法 / 某 App / 某 DNS 记录类型下生效」。带这些选项的规则一旦升级
# 为 DNS 拦截，会波及作用域之外的全部正常流量，属于误拦截，因此必须硬拒绝。
SCOPED_MODIFIERS = frozenset(
    {
        "domain",
        "from",
        "to",
        "denyallow",
        "ipaddress",
        "method",
        "app",
        "dnstype",
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
    }
)

# 第一/第三方限定选项：DNS 无法区分请求来源关系，升级会误伤同域的合法请求，硬拒绝。
PARTY_MODIFIERS = frozenset(
    {
        "third-party",
        "first-party",
        "strict1p",
        "strict3p",
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

    # 仅带导航/弹窗修饰（$popup/$popunder/$doc/$document）的纯域名规则：用户确认放宽，
    # 按整域拦截输出；置信度略低，strict-safe 档仍会排除。
    if sem and sem <= NAVIGATION_DOMAIN_MODIFIERS:
        if _PURE_DOMAIN_RE.match(_OPTION_RE.sub("", rule.raw)):
            return DnsVerdict(
                DNS_SAFE, CONF_DOMAIN_MODIFIER, "navigation_domain_modifier"
            )

    # 带未识别修饰符的单域名规则：保守回退到 CONDITIONAL，是否进入 DNS 由策略决定。
    # 仅当模式仍是纯域名时才可进入；带通配/查询串等模式限定（如
    # ||bet365.com^*affiliate=$popup）不构成整域语义，仍按不可翻译拒绝。
    if rule.domains and len(rule.domains) == 1 and rule.options:
        if _PURE_DOMAIN_RE.match(_OPTION_RE.sub("", rule.raw)):
            return DnsVerdict(DNS_CONDITIONAL, CONF_DOMAIN_MODIFIER, "domain_modifier")
        return DnsVerdict(DNS_REJECT, CONF_REJECT, "untranslatable")

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
    """阻塞型规则是否应进入 DNS/Hosts/Domains 输出。"""
    verdict = classify_dns(rule)
    if not verdict.eligible:
        return False
    policy = resolve_policy(policy)
    if verdict.reason == "domain_modifier" and not policy.get("allow_modifier", False):
        return False
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
