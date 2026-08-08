"""解析器模块 - 解析 adblock 语法规则，分类为结构化 Rule 对象

基于 Adblock Plus 语法体系（uBlock Origin / AdGuard 扩展兼容）：
- 网络请求规则: ||domain^pattern$options、|pattern|、普通字符串
- 例外规则: @@
- 元素隐藏规则: ## 隐藏、#@# 隐藏例外、#?# 扩展 CSS、##+js / #%# 脚本注入、$$ HTML 过滤
- 元数据: ! 注释、[Adblock Plus x.x] 块标记
"""

import logging
import re
from dataclasses import dataclass, field

from src.config import SourceConfig

logger = logging.getLogger(__name__)

# 规则类型常量
RULE_BLOCK = "block"                    # 网络拦截规则
RULE_EXCEPTION = "exception"            # 网络例外规则 @@
RULE_HIDE = "hide"                      # 元素隐藏规则 ##
RULE_HIDE_EXCEPTION = "hide-exception"  # 元素隐藏例外 #@#（含 #@#^ uBO HTML 例外）
RULE_CSS_EXT = "css-ext"                # 扩展 CSS 规则 #?# / #@?# (uBlock Origin)
RULE_SCRIPTLET = "scriptlet"            # 脚本注入规则 ##+js / #%# / #$# (脚本内容)
RULE_CSS_INJECT = "css-inject"          # 样式注入规则 #$# / #%# (样式内容) 及例外 #@$# / #@%# (AdGuard)
RULE_HTML = "html"                      # HTML 过滤规则 $$ (AdGuard)
RULE_HTML_EXCEPTION = "html-exception"  # HTML 过滤例外 #@$$ (AdGuard)
RULE_HEADER = "header"                  # 元数据行 ! Title / ! Expires / ! Homepage

# 元素类规则类型（输出时统一归入 Hide 分区）
HIDE_TYPES = (
    RULE_HIDE,
    RULE_HIDE_EXCEPTION,
    RULE_CSS_EXT,
    RULE_SCRIPTLET,
    RULE_CSS_INJECT,
    RULE_HTML,
    RULE_HTML_EXCEPTION,
)


@dataclass
class Rule:
    """单条广告过滤规则"""
    raw: str          # 原始规则文本
    normalized: str   # 标准化后的规则文本（用于去重比较）
    rule_type: str    # 见 RULE_* 常量
    domain: str       # 规则匹配的域名部分
    source: str     # 来源名称
    priority: int     # 来源优先级
    options: dict[str, str | bool] = field(default_factory=dict)  # 解析后的 $options
    pattern: str = ""  # 去除 @@ 前缀与 $options 后的匹配模式
    domains: list[str] = field(default_factory=list)  # 元素规则的多站点限定域名列表
    comments: list[str] = field(default_factory=list)  # 输入中位于该规则之前的注释行（输出时透传）


# 匹配以 ! 开头的注释行
METADATA_PATTERN = re.compile(r'^!')

# 匹配 [Adblock Plus x.x] 等元数据块标记
ADGUARD_META_PATTERN = re.compile(r'^\[.*\]$')

# 匹配例外规则 @@
EXCEPTION_PATTERN = re.compile(r'^@@')

# 元素规则分隔符（按特异性从高到低依次检测）
HIDE_EXCEPTION_SEP = "#@#"    # 元素隐藏例外（含 #@#^ uBO HTML 过滤例外）
CSS_EXT_EXCEPTION_SEP = "#@?#"  # 扩展 CSS 例外 (uBO)
CSS_EXT_SEP = "#?#"           # 扩展 CSS (uBO)
ADGUARD_HTML_EXCEPTION_SEP = "#@$$"  # HTML 过滤例外 (AdGuard)
ADGUARD_HTML_SEP = "$$"       # HTML 过滤 (AdGuard)
SCRIPTLET_SEPS = ("#%#", "#$#")      # 脚本注入 (AdGuard)，需内容嗅探区分脚本/样式
UBO_SCRIPTLET_SEP = "##+js("  # 脚本注入 (uBO)，恒为脚本
STYLE_INJECT_EXCEPTION_SEPS = ("#@$#", "#@%#")  # 样式注入例外 (AdGuard)
STYLE_CSS_EXT_SEPS = ("#@$?#", "#$?#")  # 扩展选择器样式注入及例外 (AdGuard) #$?# / #@$?#
HIDE_SEP = "##"               # 普通元素隐藏

# #%# / #$# 分隔符后判定为脚本注入的内容前缀（否则视为样式注入）
SCRIPT_INJECT_PREFIXES = ("script:", "//scriptlet", "script(")

# 以 # 开头的合法元素规则前缀（用于区分 hosts 的 # 注释行）
_GLOBAL_ELEMENT_PREFIXES = (
    "##", "#@#", "#@?#", "#?#", "#@$$", "#@$#", "#@%#", "#%#", "#$#",
    "#@$?#", "#$?#",
)

# 匹配域名模式的规则 ||domain^
DOMAIN_PATTERN = re.compile(r'\|\|([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*)')

# 匹配 hosts 格式的规则 127.0.0.1 domain 或 0.0.0.0 domain
HOSTS_PATTERN = re.compile(r'^(?:127\.0\.0\.1|0\.0\.0\.0)\s+(.+)')

# 已知选项名（ABP 基础 + uBlock Origin / AdGuard 扩展）
# 用于校验 $ 之后是否真的是选项区，避免 URL 中的裸 $ 被误判
KNOWN_OPTIONS = frozenset({
    # 请求类型
    "script", "image", "stylesheet", "object", "xmlhttprequest", "subdocument",
    "document", "other", "ping", "websocket", "webrtc", "media", "font", "popup",
    # 行为选项
    "important", "third-party", "match-case", "collapse", "all",
    "elemhide", "genericblock", "generichide", "specifichide",
    "inline-script", "inline-font", "strict1p", "3p", "1p", "doc", "frame",
    "empty", "mp4", "jsinject", "content", "network", "permissions",
    # 带值选项
    "domain", "csp", "redirect", "replace", "removeparam", "method", "header",
    "removeheader", "urlskip", "denyallow", "from", "to", "badfilter", "ext",
    "app", "strict-block", "uuid", "redirect-rule", "rewrite", "permissions",
    # 别名与隐身选项
    "xhr", "stealth",
})


def is_metadata_line(line: str) -> bool:
    """判断是否为元数据/注释行"""
    stripped = line.strip()
    if not stripped:
        return True
    if METADATA_PATTERN.match(stripped):
        return True
    if ADGUARD_META_PATTERN.match(stripped):
        return True
    return False


def _classify_with_sep(line: str) -> tuple[str, str]:
    """分类规则类型并返回使用的分隔符

    Returns:
        (rule_type, 元素分隔符)；网络规则的分隔符为空字符串
    """
    stripped = line.strip()

    # 元素类规则优先检测（按分隔符特异性从高到低）
    if HIDE_EXCEPTION_SEP in stripped:      # #@# 元素隐藏例外（含 #@#^ uBO HTML 例外）
        return RULE_HIDE_EXCEPTION, HIDE_EXCEPTION_SEP
    if CSS_EXT_EXCEPTION_SEP in stripped:   # #@?# 扩展 CSS 例外
        return RULE_CSS_EXT, CSS_EXT_EXCEPTION_SEP
    if CSS_EXT_SEP in stripped:             # #?# 扩展 CSS
        return RULE_CSS_EXT, CSS_EXT_SEP
    if ADGUARD_HTML_EXCEPTION_SEP in stripped:  # #@$$ HTML 过滤例外
        return RULE_HTML_EXCEPTION, ADGUARD_HTML_EXCEPTION_SEP
    if ADGUARD_HTML_SEP in stripped:        # $$ HTML 过滤
        return RULE_HTML, ADGUARD_HTML_SEP
    for sep in STYLE_CSS_EXT_SEPS:          # #$?# / #@$?# 扩展选择器样式注入 (AdGuard)
        if sep in stripped:
            return RULE_CSS_INJECT, sep
    for sep in STYLE_INJECT_EXCEPTION_SEPS:  # #@$# / #@%# 样式注入例外
        if sep in stripped:
            return RULE_CSS_INJECT, sep
    for sep in SCRIPTLET_SEPS:              # #%# / #$#: 内容嗅探区分脚本/样式注入
        if sep in stripped:
            _, _, body = stripped.partition(sep)
            if body.lstrip().startswith(SCRIPT_INJECT_PREFIXES):
                return RULE_SCRIPTLET, sep
            return RULE_CSS_INJECT, sep
    if UBO_SCRIPTLET_SEP in stripped:       # ##+js( 脚本注入 (uBO)
        return RULE_SCRIPTLET, UBO_SCRIPTLET_SEP
    if HIDE_SEP in stripped:                # ## 普通元素隐藏（含 ##^ uBO HTML 过滤）
        return RULE_HIDE, HIDE_SEP

    # 网络类规则
    if EXCEPTION_PATTERN.match(stripped):
        return RULE_EXCEPTION, ""
    return RULE_BLOCK, ""


def _is_hash_comment(line: str) -> bool:
    """判断是否为 hosts 文件风格的 # 注释行

    注意: ##.ad 等全局元素规则也以 # 开头，需排除元素分隔符前缀，
    避免把合法规则误判为注释。

    Args:
        line: 去除首尾空白后的行

    Returns:
        是 # 注释行则返回 True
    """
    if not line.startswith("#"):
        return False
    return not any(line.startswith(p) for p in _GLOBAL_ELEMENT_PREFIXES)


def classify_rule(line: str) -> str:
    """分类规则类型（兼容接口，仅返回类型字符串）

    Returns:
        RULE_* 常量之一
    """
    rule_type, _ = _classify_with_sep(line)
    return rule_type


def _split_options(opts_str: str) -> list[str]:
    """拆分选项列表，兼容正则形式选项值（/.../ 包裹，内部可含逗号）

    例如 $replace=/(a,b)/g 或 $removeparam=/^utm_/：
    以 / 开头的值会被完整收集到闭合斜杠（支持 \\/ 转义）及 flags，
    期间逗号属于值的一部分，不作为选项分隔符。
    """
    parts: list[str] = []
    current: list[str] = []
    i = 0
    n = len(opts_str)

    while i < n:
        ch = opts_str[i]
        if ch == "\\" and i + 1 < n and opts_str[i + 1] == ",":
            # 转义逗号: $permissions=autoplay=()\, camera=() 中逗号是值的一部分
            current.append(ch)
            current.append(",")
            i += 2
            continue

        if ch == ",":
            parts.append("".join(current))
            current = []
            i += 1
            continue

        if ch == "/":
            # 正则形式值：收集到闭合 /（转义 / 除外），闭合后跟 flags 字母
            current.append(ch)
            i += 1
            in_escape = False
            while i < n:
                c = opts_str[i]
                current.append(c)
                if in_escape:
                    in_escape = False
                elif c == "\\":
                    in_escape = True
                elif c == "/":
                    # 尝试读 flags（连续字母），仅当其后再遇分隔符或结束才确认闭合
                    # 避免 /a/b/ 中正则体内部的斜杠后字母被误当 flags
                    flags_start = i + 1
                    j = flags_start
                    while j < n and opts_str[j].isalpha():
                        j += 1
                    if j >= n or opts_str[j] in (",", "|", "$"):
                        current.extend(opts_str[flags_start:j])
                        i = j
                        break
                    i += 1
                    continue
                i += 1
            continue

        current.append(ch)
        i += 1

    if current:
        parts.append("".join(current))
    return parts


def _looks_like_option(token: str) -> bool:
    """判断 token 是否形如合法选项

    - 带值形式（key=value）：仅要求 key 非空
    - 布尔形式：须为已知选项名（支持 ~ 否定前缀）
    """
    name = token.lstrip("~")
    if "=" in name:
        key = name.split("=", 1)[0].strip()
        return bool(key)
    return name in KNOWN_OPTIONS


def parse_options(rule_text: str) -> tuple[dict[str, str | bool], str]:
    """解析网络规则的 $options 部分

    Args:
        rule_text: 规则文本（含 @@ 前缀与 $options）

    Returns:
        (options 字典, 匹配模式部分)

    Note:
        - 使用第一个 $ 作为分隔符；若 $ 之后拆分不出合法选项，
          说明 $ 属于匹配模式本身（URL 中含 $ 的罕见写法），整行按无选项处理
        - 正则形式选项值（$replace=/$removeparam=）内部逗号不会被误拆
    """
    if "$" not in rule_text:
        return {}, rule_text

    match_part, _, opts_str = rule_text.partition("$")
    tokens = _split_options(opts_str)

    # 校验：拆分出的选项全部非法时，判定 $ 属于匹配模式而非选项分隔符
    if tokens and not any(_looks_like_option(t) for t in tokens):
        return {}, rule_text

    options: dict[str, str | bool] = {}
    for part in tokens:
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, _, value = part.partition("=")
            options[key.strip()] = value
        else:
            options[part] = True
    return options, match_part


def _extract_element_domains(rule_text: str, sep: str) -> list[str]:
    """提取元素规则的多站点限定域名列表

    Args:
        rule_text: 元素规则文本（如 example.com,foo.org##.sponsor）
        sep: 元素分隔符（## / #@# / #?# / $$ 等）

    Returns:
        域名列表；无站点限定的全局规则返回空列表。
        否定域名保留 ~ 前缀（如 ~foo.org），多站点顺序保持原文。

    Examples:
        example.com,foo.org##.sponsor -> ["example.com", "foo.org"]
        example.com,~foo.org#@#.x     -> ["example.com", "~foo.org"]
        ##.ad-banner                  -> []
    """
    prefix, _, _ = rule_text.partition(sep)
    prefix = prefix.strip()
    if not prefix:
        return []
    return [d.strip() for d in prefix.split(",") if d.strip()]


def extract_domain(rule_text: str) -> str:
    """从规则中提取域名

    Args:
        rule_text: 规则文本（网络规则建议传入去除 $options 后的匹配模式）

    Returns:
        提取的域名字符串，若无法提取则返回空字符串
    """
    # 先尝试匹配 ||domain^ 模式
    match = DOMAIN_PATTERN.search(rule_text)
    if match:
        return match.group(1).lower()

    # 尝试匹配 hosts 格式
    match = HOSTS_PATTERN.match(rule_text.strip())
    if match:
        return match.group(1).strip().lower()

    # 尝试从 URL 模式中提取域名
    # 简单模式: 移除协议、端口和路径
    cleaned = rule_text.strip()
    # 移除 @@ 前缀（例外规则）
    if cleaned.startswith("@@||"):
        cleaned = cleaned[4:]
    elif cleaned.startswith("@@"):
        cleaned = cleaned[2:]
    if cleaned.startswith("||"):
        cleaned = cleaned[2:]

    # 匹配可能包含通配符的域名模式
    domain_match = re.match(
        r'([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+)',
        cleaned,
    )
    if domain_match:
        return domain_match.group(1).lower()

    return ""


def parse_rules(raw_content: str, source: SourceConfig) -> list[Rule]:
    """解析原始规则文本，转换为 Rule 对象列表

    Args:
        raw_content: 从上游下载的原始规则文本
        source: 来源配置

    Returns:
        Rule 对象列表

    Note:
        - 普通 ! 注释行（非 Title/Expires/Homepage）会缓存并挂载到紧随其后的
          规则上，输出时透传，保证输入源的注释分组信息不丢失
        - hosts 行（127.0.0.1 / 0.0.0.0）保留原始格式（仅剥除行内注释），
          不再转换为 ||domain^ 形式
    """
    rules: list[Rule] = []
    pending_comments: list[str] = []

    for line in raw_content.splitlines():
        stripped = line.strip()

        # 空行跳过
        if not stripped:
            continue

        # 元数据/注释行
        if METADATA_PATTERN.match(stripped):
            # 保留 Title/Expires/Homepage；Version 由聚合器自身生成，丢弃上游值避免冲突
            if stripped.startswith(("! Title:", "! Expires:", "! Homepage:")):
                rules.append(Rule(
                    raw=stripped,
                    normalized=stripped.lower(),
                    rule_type=RULE_HEADER,
                    domain="",
                    source=source.name,
                    priority=source.priority,
                    comments=pending_comments,
                ))
                pending_comments = []
            elif stripped.startswith("! =") and stripped.endswith("="):
                # 输入源的分区标记注释（! ===== xxx =====）：聚合器输出统一分区标记，
                # 跳过避免与生成的分区标题重复
                continue
            else:
                # 普通注释行：缓存，透传到紧随其后的规则前
                pending_comments.append(stripped)
            continue

        # [Adblock Plus x.x] 等块标记跳过
        if ADGUARD_META_PATTERN.match(stripped):
            continue

        # 跳过 hosts 文件的 # 注释行（避免误判为网络规则）
        if _is_hash_comment(stripped):
            continue

        # hosts 格式规则：保留原始格式（剥除行内注释），不再转换为 ||domain^
        host_match = HOSTS_PATTERN.match(stripped)
        if host_match:
            domain = host_match.group(1).strip()
            # 剥除行内注释: 127.0.0.1 ad.tracker.com   # 追踪服务器
            domain = domain.split(" #", 1)[0].strip()
            if not domain:
                continue
            raw_host = stripped.split(" #", 1)[0].strip()
            rules.append(Rule(
                raw=raw_host,
                normalized=raw_host.lower(),
                rule_type=RULE_BLOCK,
                domain=domain.lower(),
                source=source.name,
                priority=source.priority,
                pattern=raw_host,
                comments=pending_comments,
            ))
            pending_comments = []
            continue

        # 分类规则（记录元素分隔符，用于提取多站点限定域名）
        rule_type, sep = _classify_with_sep(stripped)

        # 仅网络规则解析 $options；元素规则（##/#@#/#?#/#%#/$$）不适用
        if rule_type in (RULE_BLOCK, RULE_EXCEPTION):
            options, pattern = parse_options(stripped)
            domains: list[str] = []
        else:
            options, pattern = {}, stripped
            # 元素规则：解析多站点限定域名（example.com,foo.org##.x）
            domains = _extract_element_domains(stripped, sep)

        domain = extract_domain(pattern)

        # 多站点规则: 域名排序后作为去重键，保证域名顺序不影响去重
        normalized = stripped.lower().strip()
        if len(domains) > 1:
            _, _, selector = stripped.partition(sep)
            normalized = ",".join(sorted(d.lower() for d in domains)) + sep + selector.lower()

        rules.append(Rule(
            raw=stripped,
            normalized=normalized,
            rule_type=rule_type,
            domain=domain,
            source=source.name,
            priority=source.priority,
            options=options,
            pattern=pattern,
            domains=domains,
            comments=pending_comments,
        ))
        pending_comments = []

    return rules
