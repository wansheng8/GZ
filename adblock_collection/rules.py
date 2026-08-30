"""规则解析、规范化与分类工具。

支持 Adblock Plus、uBlock Origin、AdGuard 三类语法的过滤器列表。
每条规则被解析为 Rule 对象，用于后续去重、合并、badfilter 处理、冗余消除与按类别统计。

规则类型（kind）：
- network : 网络/URL 过滤（含 ||domain^、$script、regexp 等）
- css     : 元素隐藏（## / #@# / #?#）
- scriptlet: 脚本注入（## + script:inject / uBO scriptlet）
- comment : 注释/元数据行
- other   : 无法归类的纯文本规则
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# 网络规则选项段（位于 $ 之后）
_PARAM_OPTION_RE = re.compile(r"\$([^$]*)$")
# 元素隐藏分隔符
_ELEMENT_SEP_RE = re.compile(r"\s*(##|#@#|#\?#|#@\?#)\s*")
# 脚本注入标识
_SCRIPTLET_RE = re.compile(r"#(?:@|@\?)?#.*\bscript:(?:inject|append|set(?:-const)?|json-prune)\b|#(?:@|@\?)?#\+js\(")
# 域名选项 domain=/from=/to=
_DOMAIN_OPTION_RE = re.compile(r"(?:domain|from|to)=([^,)]+)")
# 网络规则主体（|| 之后、^ 或 / 或 $ 之前的部分），用于提取域名
_NET_DOMAIN_RE = re.compile(r"^\|\|([a-z0-9*_.-]+(?:\.[a-z0-9*_.-]+)+)")
# 严格的合法域名校验：仅允许字母数字与连字符，含点分隔的标签，TLD 至少 2 字母
_VALID_DOMAIN_RE = re.compile(r"^(?=[a-z0-9])[a-z0-9-]{1,63}(\.[a-z0-9-]{1,63})*\.[a-z]{2,63}$")
# 纯域名网络规则：||domain^ 或 ||domain/ 结尾
_PURE_DOMAIN_RE = re.compile(r"^\|\|([a-z0-9_-]+(?:\.[a-z0-9_-]+)+)\^?$")
# 第三方面选项，用于判断规则作用范围（非必需）
_THIRD_PARTY_RE = re.compile(r"\$third-party|\$~third-party")


@dataclass
class Rule:
    raw: str
    norm: str
    kind: str = "network"
    category: str = "other"
    is_exception: bool = False
    is_css: bool = False
    is_scriptlet: bool = False
    is_badfilter: bool = False
    is_important: bool = False
    # 该规则作用到的域名（网络规则为 blocked domain，元素规则为限定域名）
    domains: list[str] = field(default_factory=list)
    source: Optional[str] = None
    options: dict[str, str] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.norm)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Rule):
            return self.norm == other.norm
        return NotImplemented


# 关键字 -> 类别映射，用于统计与拆分
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "url": ["/ad", "/ads", "/banner", "ad.php", "ads.php", "click", "track", "analytics", "pixel", "beacon", "log.", "stat"],
    "privacy": ["privacy", "track", "telemetry", "fingerprint", "webrtc", "geo", "location"],
    "cookie": ["cookie", "consent", "gdpr", "ccpa"],
    "social": ["facebook", "fb.", "twitter", "instagram", "share", "social", "disqus", "vk.com", "ok.ru"],
    "malware": ["malware", "virus", "exploit", "ransomware"],
    "phishing": ["phish", "scam", "fraud"],
    "mining": ["miner", "coinhive", "monero", "cryptonight", "mining"],
    "annoyance": ["popup", "popunder", "push", "subscribe", "newsletter", "survey", "cookie", "overlay"],
    "whitelist": ["@"],
}


def parse_options(option_str: str) -> dict[str, str]:
    """解析 $ 之后的选项为字典，支持 opt=value 与独立 opt。"""
    opts: dict[str, str] = {}
    for part in option_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            opts[k.strip()] = v.strip()
        else:
            opts[part] = ""
    return opts


def _extract_domains(raw: str) -> list[str]:
    """提取规则涉及的域名。

    - 元素规则 example.com,~sub.com##.ad -> [example.com]（忽略取反域名）
    - 网络规则 ||example.com^         -> [example.com]
    - 网络规则 ||example.com/ads^     -> [example.com]（含路径时仍提取主机名）
    - 回退：从 domain=/from=/to= 选项提取
    """
    domains: list[str] = []
    m = _ELEMENT_SEP_RE.search(raw)
    if m:
        prefix = raw[: m.start()]
        for d in prefix.split(","):
            d = d.strip().lower()
            if d and not d.startswith("~") and _VALID_DOMAIN_RE.match(d):
                domains.append(d)
        return domains
    # 网络规则：优先匹配 ||host... 主体
    nm = _NET_DOMAIN_RE.match(raw)
    if nm:
        host = nm.group(1).lower()
        if "*" not in host and _VALID_DOMAIN_RE.match(host):
            domains.append(host)
            return domains
    # 退而求其次，从 domain= 选项提取
    for dm in _DOMAIN_OPTION_RE.finditer(raw):
        val = dm.group(1)
        for d in val.split("|"):
            d = d.strip().lstrip("~").lower()
            if d and "*" not in d and _VALID_DOMAIN_RE.match(d):
                domains.append(d)
    return domains


def _classify(raw: str, category_hint: str, kind: str, is_exception: bool) -> str:
    if is_exception:
        return "whitelist"
    if category_hint and category_hint != "other":
        return category_hint
    low = raw.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(k in low for k in kws):
            return cat
    if kind == "css":
        return "css"
    if kind == "scriptlet":
        return "scriptlet"
    if re.search(r"\$.*(redirect|rewrite)", raw, re.I):
        return "redirect"
    if re.search(r"\$.*(regexp)", raw, re.I):
        return "regexp"
    if re.search(r"\$.*(websocket|webrtc)", raw, re.I):
        return "network"
    return "other"


def _normalize(raw: str) -> str:
    """生成去重键：折叠空白、统一选项顺序、剔除无关空白。"""
    r = raw.strip()
    if not r:
        return r
    m = _PARAM_OPTION_RE.search(r)
    if m:
        opts = [o.strip() for o in m.group(1).split(",") if o.strip()]
        # badfilter 单独保留其语义位置，但仍是选项之一
        opts_sorted = ",".join(sorted(opts))
        r = r[: m.start(1)] + opts_sorted + r[m.end(1):]
    r = re.sub(r"\s+", " ", r)
    return r


def _detect_kind(raw: str) -> str:
    if _SCRIPTLET_RE.search(raw):
        return "scriptlet"
    if _ELEMENT_SEP_RE.search(raw):
        return "css"
    if raw.startswith("!") or (raw.startswith("[") and raw.endswith("]")):
        return "comment"
    if "@@" in raw[:4]:
        return "network"
    return "network"


def parse_line(line: str, category_hint: str = "other", source: Optional[str] = None) -> Optional[Rule]:
    raw = line.rstrip("\n")
    stripped = raw.strip()
    if not stripped:
        return None
    if stripped.startswith("!"):
        return None
    if stripped.startswith("[") and stripped.endswith("]"):
        return None

    kind = _detect_kind(stripped)
    norm = _normalize(stripped)
    if not norm:
        return None

    is_exception = "@@" in stripped[:4] or "#@#" in stripped or "#@?#" in stripped
    is_css = kind == "css"
    is_scriptlet = kind == "scriptlet"

    options: dict[str, str] = {}
    is_badfilter = False
    is_important = False
    m = _PARAM_OPTION_RE.search(stripped)
    if m:
        options = parse_options(m.group(1))
        is_badfilter = "badfilter" in options
        is_important = "important" in options

    domains = _extract_domains(stripped)
    cat = _classify(stripped, category_hint, kind, is_exception)

    return Rule(
        raw=stripped,
        norm=norm,
        kind=kind,
        category=cat,
        is_exception=is_exception,
        is_css=is_css,
        is_scriptlet=is_scriptlet,
        is_badfilter=is_badfilter,
        is_important=is_important,
        domains=domains,
        source=source,
        options=options,
    )
