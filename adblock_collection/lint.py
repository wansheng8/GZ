"""规则语法、冲突与分层校验（lint）。

面向本地增强规则（``config/local_rules.txt``）与任意 adblock 文本，做三件事：

1. 语法校验：空选择器、空选项名、缺失目标等明显笔误；
2. 冲突检测：同一模式的阻断与例外并存、``$badfilter`` 找不到对应规则、重复行；
3. DNS / 浏览器分层：复用 ``dns_policy`` 判定哪些规则可安全进入 DNS，其余归浏览器层。

设计原则与构建流程一致：宁可多报可疑项，也不让语法错误或冲突静默进入产物。
校验结果不修改输入文件；需要拆分产物时由调用方显式写出。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .dns_policy import (
    METADATA_OPTIONS,
    NAVIGATION_DOMAIN_MODIFIERS,
    NON_BLOCKING_MODIFIERS,
    PARTY_MODIFIERS,
    RESOURCE_TYPE_MODIFIERS,
    SCOPED_MODIFIERS,
    WHOLE_DOMAIN_MODIFIERS,
    is_dns_eligible,
)
from .rules import (
    _ELEMENT_SEP_RE,
    _NET_DOMAIN_RE,
    UBO_ENHANCED_MODIFIERS,
    Rule,
    _option_start,
    _split_options,
    parse_line,
)

# 网络规则中可识别的选项名集合，用于「未知选项」提示。取各语义分组与常见 ABP 选项的并集。
KNOWN_NETWORK_OPTIONS = frozenset(
    set(NON_BLOCKING_MODIFIERS)
    | set(SCOPED_MODIFIERS)
    | set(WHOLE_DOMAIN_MODIFIERS)
    | set(NAVIGATION_DOMAIN_MODIFIERS)
    | set(RESOURCE_TYPE_MODIFIERS)
    | set(PARTY_MODIFIERS)
    | set(UBO_ENHANCED_MODIFIERS)
    # 注解类选项（$reason= 等）只在分类时忽略，仍是合法选项名，不能报未知
    | set(METADATA_OPTIONS)
    | {
        "badfilter",
        "cname",
        "extension",
        "empty",
        "mp4",
        "important",
        "match-case",
        "genericblock",
    }
)


@dataclass
class LintIssue:
    """单条校验问题。``level`` 为 ``error``（阻断）或 ``warning``（提示）。"""

    level: str
    line: int
    text: str
    message: str

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "line": self.line,
            "text": self.text,
            "message": self.message,
        }


@dataclass
class LintReport:
    issues: list[LintIssue] = field(default_factory=list)
    # 可安全进入 DNS 的整域阻断域名
    dns_domains: list[str] = field(default_factory=list)
    # 仅浏览器扩展可用的规则原文（元素隐藏、资源类型限定、高级修饰符等）
    browser_rules: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[LintIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[LintIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": [i.to_dict() for i in self.errors],
            "warnings": [i.to_dict() for i in self.warnings],
            "dns_domains": len(self.dns_domains),
            "browser_rules": len(self.browser_rules),
        }


def _option_name(part: str) -> str:
    return part.split("=", 1)[0].lstrip("~").strip().lower()


def _lint_line(line: str, lineno: int) -> list[LintIssue]:
    issues: list[LintIssue] = []
    stripped = line.strip()
    if not stripped or stripped.startswith("!"):
        return issues
    if stripped.startswith("#") and _ELEMENT_SEP_RE.match(stripped) is None:
        return issues
    if stripped.startswith("[") and stripped.endswith("]"):
        return issues

    sep_m = _ELEMENT_SEP_RE.search(stripped)
    if sep_m:
        sep = sep_m.group(1)
        selector = stripped[sep_m.end() :].strip()
        if not selector:
            issues.append(LintIssue("error", lineno, stripped, "元素规则缺少选择器"))
        elif sep in ("##", "#@#") and selector.startswith("^") and not selector[1:].strip():
            issues.append(
                LintIssue("error", lineno, stripped, "HTML 过滤规则缺少选择器")
            )
        if "##+js()" in stripped.replace(" ", ""):
            issues.append(LintIssue("error", lineno, stripped, "scriptlet 名称不能为空"))
        return issues

    if stripped.startswith("@@"):
        if not stripped[2:].strip():
            issues.append(LintIssue("error", lineno, stripped, "@@ 例外缺少匹配模式"))
            return issues

    idx = _option_start(stripped)
    if idx is None and stripped.endswith("$"):
        issues.append(LintIssue("error", lineno, stripped, "$ 后缺少选项名"))
    if idx is not None:
        parts = _split_options(stripped[idx + 1 :])
        if not parts:
            issues.append(LintIssue("error", lineno, stripped, "$ 后缺少选项名"))
        for part in parts:
            name = _option_name(part)
            if not name:
                issues.append(
                    LintIssue("error", lineno, stripped, f"空选项片段: {part!r}")
                )
            elif name not in KNOWN_NETWORK_OPTIONS:
                issues.append(
                    LintIssue(
                        "warning",
                        lineno,
                        stripped,
                        f"未知选项名: {name}（如为拼写错误请修正）",
                    )
                )
    if "||" in stripped and not _NET_DOMAIN_RE.search(stripped):
        suffix = stripped.split("||", 1)[1]
        if not suffix.strip("^*"):
            issues.append(
                LintIssue("warning", lineno, stripped, "|| 规则未包含有效域名")
            )
    return issues


def _has_badfilter(rule: Rule, raw: str) -> bool:
    """识别 ``$...,badfilter`` 与历史写法 ``^,badfilter`` 两种标记。"""
    return rule.is_badfilter or raw.rstrip().endswith(",badfilter")


def _badfilter_base(rule: Rule, raw: str) -> str:
    if not rule.is_badfilter:
        return raw.rstrip()[: -len(",badfilter")]
    idx = _option_start(raw)
    if idx is None:
        return raw
    parts = [p for p in _split_options(raw[idx + 1 :]) if _option_name(p) != "badfilter"]
    if not parts:
        return raw[:idx]
    return raw[:idx] + "$" + ",".join(parts)


def _conflict_issues(
    parsed: list[tuple[int, str, Rule]], issues: list[LintIssue]
) -> None:
    """检测同模式阻断/例外冲突、badfilter 悬空与重复行。"""
    block_keys: dict[str, int] = {}
    exception_keys: dict[tuple[str, int], int] = {}
    badfilter_keys: list[tuple[int, str, str]] = []
    seen_norm: dict[str, int] = {}
    text_by_line = {lineno: text for lineno, text, _ in parsed}
    for lineno, text, rule in parsed:
        if _has_badfilter(rule, rule.raw):
            badfilter_keys.append((lineno, text, _badfilter_base(rule, rule.raw)))
            continue
        key = rule.raw.removeprefix("@@")
        if rule.is_exception:
            exception_keys[(key, lineno)] = lineno
        else:
            block_keys[key] = lineno
        if rule.norm in seen_norm:
            issues.append(
                LintIssue(
                    "warning", lineno, text, f"与第 {seen_norm[rule.norm]} 行规则重复"
                )
            )
        else:
            seen_norm[rule.norm] = lineno
    for lineno, text, base in badfilter_keys:
        if base not in block_keys and base not in {k for k, _ in exception_keys}:
            issues.append(
                LintIssue("warning", lineno, text, "badfilter 未找到对应规则，可能失效")
            )
    for key, lineno in exception_keys:
        if key in block_keys:
            issues.append(
                LintIssue(
                    "warning",
                    lineno,
                    text_by_line.get(lineno, key),
                    "同一模式同时存在阻断与例外，后者将覆盖前者",
                )
            )


def lint_text(
    text: str,
    *,
    source: str | None = None,
    policy: dict | None = None,
) -> LintReport:
    """校验 adblock 文本，返回问题清单与 DNS/浏览器分层结果。"""
    report = LintReport()
    parsed: list[tuple[int, str, Rule]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        report.issues.extend(_lint_line(line, lineno))
        rule = parse_line(line, source=source)
        if rule is None:
            continue
        parsed.append((lineno, line, rule))
        if (
            rule.kind == "network"
            and not rule.is_exception
            and rule.domains
            and is_dns_eligible(rule, policy)
        ):
            report.dns_domains.append(rule.domains[0])
        else:
            report.browser_rules.append(rule.raw)
    _conflict_issues(parsed, report.issues)
    report.dns_domains = sorted(set(report.dns_domains))
    return report


def lint_lines(lines: list[str], **kwargs) -> LintReport:
    return lint_text("\n".join(lines), **kwargs)
