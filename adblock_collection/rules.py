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
from collections.abc import Iterable
from dataclasses import dataclass, field

# 单个选项名的合法形态（用于在规则中定位真正的选项段起始 $）
_OPTION_HEAD_RE = re.compile(r"~?[A-Za-z0-9][A-Za-z0-9-]*")
# 采用 `name:/regex/` 取值形态的选项（头部过滤），其正则内可含逗号
_NAMED_REGEX_OPTIONS = frozenset({"header", "set-cookie", "removeheader"})
# 元素隐藏 / 扩展语法分隔符（按长度优先排列，带 @ 的例外形式在前）
# 覆盖：uBO/ABP 的 ##、#@#、#?#、#@?#；AdGuard 扩展元素规则 #$#、#@$#；
#      AdGuard 注入 #%#、#@%#；AdGuard v5.3+ HTML 过滤 $$（[domains]$$selector）。
_ELEMENT_SEP_RE = re.compile(r"\s*(#@\$#|#\$#|#@%#|#%#|#@\?#|#\?#|#@#|##|\$\$)\s*")
# 脚本注入标识（uBO +js() / script:inject；AdGuard #%#//scriptlet()，含 #@%# 例外形式）
_SCRIPTLET_RE = re.compile(
    r"#[@%$?]{0,2}#.*\bscript:(?:inject|append|set(?:-const)?|json-prune)\b"
    r"|#[@%$?]{0,2}#\+js\("
    r"|#[@%$?]{0,2}#//scriptlet\s*\("
)
# 网络规则主体（|| 之后、^ 或 / 或 $ 之前的部分），用于提取域名（允许 @@ 等前缀，故不锚行首）
_NET_DOMAIN_RE = re.compile(r"\|\|([a-z0-9*_.-]+(?:\.[a-z0-9*_.-]+)+)")
# 严格的合法域名校验：仅允许字母数字与连字符，含点分隔的标签，TLD 至少 2 字母
_VALID_DOMAIN_RE = re.compile(
    r"^(?=[a-z0-9])[a-z0-9-]{1,63}(\.[a-z0-9-]{1,63})*\.[a-z]{2,63}$"
)
# 纯域名网络规则：||domain^ 或 ||domain（无路径），允许 @@ 等前缀
_PURE_DOMAIN_RE = re.compile(r"\|\|([a-z0-9_-]+(?:\.[a-z0-9_-]+)+)\^?$")
# 第三方面选项，用于判断规则作用范围（非必需）
_THIRD_PARTY_RE = re.compile(r"\$third-party|\$~third-party")
# hosts 文件行：黑洞地址后跟一个或多个域名（如 0.0.0.0 a.com b.com）
_HOSTS_IP_RE = re.compile(r"^(?:0\.0\.0\.0|127\.0\.0\.1|::1|::)\s+(.+)$")
# 纯域名列表行（至少两级标签）；最终是否合法再由 _VALID_DOMAIN_RE 校验
_BARE_DOMAIN_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,62})?(?:\.[a-z0-9](?:[a-z0-9-]{0,62})?)+$", re.IGNORECASE
)
# 仅 IP 地址的行（hosts 黑洞占位），应跳过
_IP_ONLY_RE = re.compile(r"^(?:\d{1,3}(?:\.\d{1,3}){3}|[0-9a-f:]+)$", re.IGNORECASE)
# 系统保留别名，不应被当作广告域名拦截
_HOSTS_RESERVED = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "local",
        "broadcasthost",
        "ip6-localhost",
        "ip6-loopback",
        "ip6-localnet",
        "ip6-mcastprefix",
        "ip6-allnodes",
        "ip6-allrouters",
        "ip6-allhosts",
    }
)
# 无域名元素隐藏规则的分隔符起始，用于区分装饰规则与 hosts 文件中的 # 注释
_COSMETIC_START_RE = re.compile(r"^(?:##|#@#|#\?#|#@\?#|#\$#|#@\$#|#%#|#@%#|\$\$)")


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
    source: str | None = None
    # 去重合并后记录该规则出现的全部上游（单源去重时等于 [source]）
    sources: list[str] = field(default_factory=list)
    options: dict[str, str] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.norm)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Rule):
            return self.norm == other.norm
        return NotImplemented


# 关键字 -> 类别映射，用于统计与拆分
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "url": [
        "/ad",
        "/ads",
        "/banner",
        "ad.php",
        "ads.php",
        "click",
        "track",
        "analytics",
        "pixel",
        "beacon",
        "log.",
        "stat",
    ],
    "privacy": [
        "privacy",
        "track",
        "telemetry",
        "fingerprint",
        "webrtc",
        "geo",
        "location",
    ],
    "cookie": ["cookie", "consent", "gdpr", "ccpa"],
    "social": [
        "facebook",
        "fb.",
        "twitter",
        "instagram",
        "share",
        "social",
        "disqus",
        "vk.com",
        "ok.ru",
    ],
    "malware": ["malware", "virus", "exploit", "ransomware"],
    "phishing": ["phish", "scam", "fraud"],
    "mining": ["miner", "coinhive", "monero", "cryptonight", "mining"],
    "annoyance": [
        "popup",
        "popunder",
        "push",
        "subscribe",
        "newsletter",
        "survey",
        "cookie",
        "overlay",
    ],
    "whitelist": ["@"],
}


def _option_start(raw: str) -> int | None:
    """定位选项段起始的 `$` 下标，找不到返回 None。

    规则取值里可能含 `$`（如 `$urlskip=/a$/`），不能简单取最后一个 `$`。
    这里取「其后紧跟合法选项名」的第一个 `$` 作为选项段起点。
    """
    start = 0
    while True:
        idx = raw.find("$", start)
        if idx < 0:
            return None
        head = re.split(r"[=,]", raw[idx + 1 :], maxsplit=1)[0].strip()
        if _OPTION_HEAD_RE.fullmatch(head):
            return idx
        start = idx + 1


def _split_options(option_str: str) -> list[str]:
    """按逗号切分选项，保护引号、正则字面量与转义逗号中的内容。

    取值可能含逗号，直接 `split(",")` 会破坏选项语义与去重键，例如：

    - 裸正则取值：`$removeparam=/x{1,3}/`、`$replace='/a,b/c/'`
    - 转义逗号：`$header=name:/^a\\,b/i`
    - 具名正则取值：`$header=via:/, 1\\.1 google$/`（逗号在正则内）
    """
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    in_regex = False
    has_eq = False
    opt_name = ""
    i = 0
    n = len(option_str)
    while i < n:
        ch = option_str[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < n:
                buf.append(option_str[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
        elif in_regex:
            buf.append(ch)
            if ch == "\\" and i + 1 < n:
                buf.append(option_str[i + 1])
                i += 2
                continue
            if ch == "/":
                in_regex = False
        elif ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch == "\\" and i + 1 < n and option_str[i + 1] == ",":
            buf.append(ch)
            buf.append(option_str[i + 1])
            i += 2
            continue
        elif ch == "=" and not has_eq:
            has_eq = True
            opt_name = opt_name.strip().lstrip("~").lower()
            buf.append(ch)
            i += 1
            if i < n and option_str[i] == "/":
                in_regex = True
                buf.append("/")
                i += 1
            continue
        elif (
            ch == ":"
            and has_eq
            and opt_name in _NAMED_REGEX_OPTIONS
            and i + 1 < n
            and option_str[i + 1] == "/"
        ):
            buf.append(ch)
            buf.append("/")
            in_regex = True
            i += 2
            continue
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
            has_eq = False
            opt_name = ""
        else:
            buf.append(ch)
            if not has_eq:
                opt_name += ch
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def parse_options(option_str: str) -> dict[str, str]:
    """解析 $ 之后的选项为字典，支持 opt=value 与独立 opt。"""
    opts: dict[str, str] = {}
    for part in _split_options(option_str):
        if "=" in part:
            k, v = part.split("=", 1)
            opts[k.strip()] = v.strip()
        else:
            opts[part] = ""
    return opts


def _extract_domains(raw: str) -> list[str]:
    """提取规则「请求目标」涉及的域名。

    - 元素规则 example.com,~sub.com##.ad -> [example.com]（忽略取反域名）
    - 网络规则 ||example.com^         -> [example.com]
    - 网络规则 ||example.com/ads^     -> [example.com]（含路径时仍提取主机名）
    - 仅按 URL 模式解析，不取 domain=/from=/to= 选项：这些是**作用域**（限定规则
      在哪些来源站点生效），并非被拦截的目标域名。若误当作目标域名，会让
      `*$domain=a.com` 与 `||a.com^` 撞车，导致 remove_redundant_domains 丢规则、
      例外规则 `@@...$domain=x` 误放行 x。
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
    # 网络规则：优先匹配 ||host... 主体（不锚行首，兼容 @@ 前缀）
    nm = _NET_DOMAIN_RE.search(raw)
    if nm:
        host = nm.group(1).lower()
        if "*" not in host and _VALID_DOMAIN_RE.match(host):
            domains.append(host)
    return domains


def _classify(raw: str, category_hint: str, kind: str, is_exception: bool) -> str:
    if is_exception:
        return "whitelist"
    if category_hint and category_hint != "other":
        return category_hint
    # 元素/脚本类按其类型归类，优先于关键词匹配，避免注入规则被误判为隐私等类别
    if kind in ("css", "scriptlet", "html", "js"):
        return kind
    low = raw.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(k in low for k in kws):
            return cat
    if re.search(r"\$.*(redirect|rewrite)", raw, re.IGNORECASE):
        return "redirect"
    if re.search(r"\$.*(regexp)", raw, re.IGNORECASE):
        return "regexp"
    if re.search(r"\$.*(websocket|webrtc)", raw, re.IGNORECASE):
        return "network"
    return "other"


def _normalize(raw: str) -> str:
    """生成去重键：折叠空白、统一选项顺序、剔除无关空白。"""
    r = raw.strip()
    if not r:
        return r
    idx = _option_start(r)
    if idx is not None:
        opts = _split_options(r[idx + 1 :])
        # badfilter 单独保留其语义位置，但仍是选项之一
        opts_sorted = ",".join(sorted(opts))
        r = r[:idx] + "$" + opts_sorted
    r = re.sub(r"\s+", " ", r)
    return r


def _detect_kind(raw: str) -> str:
    if _SCRIPTLET_RE.search(raw):
        return "scriptlet"
    m = _ELEMENT_SEP_RE.search(raw)
    if m:
        sep = m.group(1)
        after = raw[m.end() :].lstrip()
        # HTML 过滤：uBO/AdGuard 的 ##^、例外 #@#^，以及 AdGuard v5.3+ 的 $$ 分隔符
        if (sep in ("##", "#@#") and after.startswith("^")) or sep == "$$":
            return "html"
        # AdGuard JS 注入（#%#var ... / #@%#var ...）
        if sep in ("#%#", "#@%#"):
            return "js"
        return "css"
    if raw.startswith("!") or (raw.startswith("[") and raw.endswith("]")):
        return "comment"
    return "network"


def _hosts_line_domains(line: str) -> list[str] | None:
    """若为 hosts 行，返回其中的合法域名列表；否则返回 None。

    hosts 行形如 `0.0.0.0 a.com b.com`、`127.0.0.1 ads.example.com # 注释`、
    `:: tracker.net`。系统保留别名（localhost 等）与非法域名会被剔除，返回空列表
    表示该 hosts 行不含可用域名。
    """
    m = _HOSTS_IP_RE.match(line)
    if not m:
        return None
    payload = m.group(1).split("#", 1)[0]
    domains: list[str] = []
    for token in payload.split():
        token = token.strip().lower().rstrip(".")
        if not token or token in _HOSTS_RESERVED:
            continue
        if _VALID_DOMAIN_RE.match(token):
            domains.append(token)
    return domains


def expand_line(line: str) -> list[str]:
    """把一行原始文本规范化为零到多条标准 adblock 规则行。

    上游存在 hosts / 纯域名两种非 adblock 格式（config 中标记 compatible: [hosts]），
    若原样保留会产出非法规则、且域名无法进入 DNS 产物，因此在此统一规范化：

    - hosts 行（0.0.0.0 a.com b.com） -> `||a.com^`、`||b.com^`
    - 纯域名行（a.com）             -> `||a.com^`（比裸子串匹配更精确，且可进 DNS）
    - hosts 注释 / 空行 / [header] / 纯 IP 占位行 -> []
    - 已是标准 adblock 的行原样返回

    返回 [] 表示该行应被跳过。
    """
    stripped = line.strip()
    if not stripped:
        return []
    if stripped.startswith("!"):
        return []
    if stripped.startswith("[") and stripped.endswith("]"):
        return []
    hosts = _hosts_line_domains(stripped)
    if hosts is not None:
        return [f"||{d}^" for d in hosts]
    if _IP_ONLY_RE.match(stripped):
        return []
    if stripped.startswith("#") and not _COSMETIC_START_RE.match(stripped):
        return []
    if _BARE_DOMAIN_RE.match(stripped):
        dom = stripped.lower().rstrip(".")
        if _VALID_DOMAIN_RE.match(dom):
            return [f"||{dom}^"]
    return [stripped]


def parse_line(
    line: str, category_hint: str = "other", source: str | None = None
) -> Rule | None:
    """解析单行文本为 Rule；hosts/纯域名行会先被规范化。

    注意：一条 hosts 行可能含多个域名，此时仅取第一个域名。需要完整展开请使用
    parse_lines（构建主流程使用它）。
    """
    expanded = expand_line(line)
    if not expanded:
        return None
    return _parse_adblock_line(expanded[0], category_hint=category_hint, source=source)


def parse_lines(
    lines: Iterable[str], category_hint: str = "other", source: str | None = None
) -> list[Rule]:
    """逐行解析并把 hosts/纯域名行完整展开为多条 Rule（构建主流程入口）。"""
    parsed: list[Rule] = []
    for line in lines:
        for normalized in expand_line(line):
            rule = _parse_adblock_line(
                normalized, category_hint=category_hint, source=source
            )
            if rule is not None:
                parsed.append(rule)
    return parsed


def _parse_adblock_line(
    stripped: str, category_hint: str = "other", source: str | None = None
) -> Rule | None:
    raw = stripped.rstrip("\n")
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

    # 例外判定：@@ 网络例外，或带 @ 的元素/扩展分隔符（#@# / #@?# / #@$# / #@%#）
    sep_m = _ELEMENT_SEP_RE.search(stripped)
    is_exception = "@@" in stripped[:4] or (
        sep_m is not None and sep_m.group(1).startswith("#@")
    )
    is_css = kind == "css"
    is_scriptlet = kind == "scriptlet"

    options: dict[str, str] = {}
    is_badfilter = False
    is_important = False
    m = _option_start(stripped)
    if m is not None:
        options = parse_options(stripped[m + 1 :])
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
        sources=[source] if source else [],
        options=options,
    )
