"""DNS 输出安全分级。

把每条规则按 DNS 可表达性分为 REJECT（绝不进 DNS）、SAFE、CONDITIONAL 三档，
并给出 confidence（0~1）。再结合 config 中的 dns_policy.level 决定最终是否进入
hosts / domains 文件。目的是在「宁愿少拦截、不要误拦截」原则下，避免把只应阻断某
路径或带作用域限制（如 $third-party）的规则错误地升级成整域拦截。

分级依据（参考 Adblock 语义）：

- REJECT  : CSS 元素隐藏、脚本注入、正则、重定向、含路径的网络规则。
            DNS 只能看到域名，整域拦截会严重误伤，直接拒绝。
- SAFE    : 纯域名网络规则（||ads.example.com^），整域拦截语义等价，confidence=1.0。
- CONDITIONAL: 带修饰符的单域名规则（如 ||example.com^$third-party），作用域受限，
            confidence=0.8，是否进入 DNS 由策略的 allow_modifier 决定。

策略等级（config 的 dns_policy.level）：

- all        : 仅接受 SAFE（纯域名）。与旧版行为一致，最保守的向后兼容默认。
- safe       : 接受 SAFE + CONDITIONAL（min_confidence=0.8, allow_modifier=True）。
- strict-safe: 仅接受 SAFE（min_confidence=0.9, allow_modifier=False），最不易误杀。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .rules import Rule, _PURE_DOMAIN_RE, _NET_DOMAIN_RE

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

_OPTION_RE = re.compile(r"\$([^$]*)$")


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

    # 正则 / 重定向类规则无法转 DNS（白名单例外也转不出域名语义）
    if rule.options:
        if any(k in rule.options for k in ("regexp", "redirect", "rewrite")):
            return DnsVerdict(DNS_REJECT, CONF_REJECT, "regex_or_redirect_rule")

    # 含路径的网络规则：DNS 只能看到域名，整域拦截会误伤，拒绝
    m = _NET_DOMAIN_RE.search(rule.raw)
    if m:
        after = _OPTION_RE.sub("", rule.raw[m.end():])
        if "/" in after:
            return DnsVerdict(DNS_REJECT, CONF_REJECT, "path_rule")

    # 纯域名规则
    if _PURE_DOMAIN_RE.match(rule.raw):
        return DnsVerdict(DNS_SAFE, CONF_PURE_DOMAIN, "pure_domain")

    # 带修饰符的单域名规则（如 $third-party）：作用域受限，保守处理
    if rule.domains and len(rule.domains) == 1 and rule.options:
        return DnsVerdict(DNS_CONDITIONAL, CONF_DOMAIN_MODIFIER, "domain_modifier")

    return DnsVerdict(DNS_REJECT, CONF_REJECT, "untranslatable")


def resolve_policy(policy: Optional[dict]) -> dict:
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


def is_dns_eligible(rule: Rule, policy: Optional[dict] = None) -> bool:
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
