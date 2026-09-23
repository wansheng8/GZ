"""uBO / AdGuard 列表预处理器指令支持。

上游列表（尤其 uBO 与 AdGuard 维护的列表）会用 ``!#`` 开头的预处理器指令组织内容：

- ``!#include <path|url>``：就地引入另一个列表，路径相对当前文件解析。其它引擎会把
  该指令当作注释忽略，因此维护者借此把「仅 uBO 可用」的子列表挂在通用列表里。
- ``!#if <cond>`` / ``!#else`` / ``!#endif``：条件编译。条件支持标识符、``!``、
  ``&&``、``||`` 与括号。``!#if false`` 用于临时禁用整块规则。

早期实现把这些指令当注释跳过、却保留**所有**条件分支内容，既漏掉 ``!#include``
的子列表（漏拦），又把 ``!#if env_mobile`` 等条件块无条件纳入（多拦）。本模块按
目标环境 token 求值条件，并在下载阶段解析并内联 ``!#include``。

条件求值采用保守口径：``TARGET_TOKENS`` 之外的标识符一律视为 False，未知引擎/浏览器
分支不纳入（宁愿少拦）；条件无法解析时同样按 False 处理并告警。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable

LOG = logging.getLogger("adblock_collection")

# ``!#include`` 递归深度上限，防止上游互引或深链导致无限展开。
INCLUDE_MAX_DEPTH = 5

# 目标环境 token：条件式 ``!#if`` 按此集合求值。未列出的 token 一律视为 False。
# 选择原则是「通用桌面浏览器 + 支持 HTML 过滤」，覆盖 uBO 经典版与 AdGuard，
# 但不纳入 env_mobile / env_firefox / env_chromium / env_safari / ext_ubol 等
# 特定环境分支，避免把仅移动端或特定内核的规则带入通用订阅。
TARGET_TOKENS = frozenset(
    {
        "ext_ublock",
        "adguard",
        "cap_html_filtering",
    }
)

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")

# include 解析回调：给定已解析的绝对地址，返回 (文本行, 该文件地址) 或 None（不可用）。
IncludeResolver = Callable[[str], "tuple[list[str], str] | None"]


def _tokenize(condition: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(condition)
    while i < n:
        ch = condition[i]
        if ch.isspace():
            i += 1
            continue
        if condition.startswith("&&", i):
            tokens.append("&&")
            i += 2
            continue
        if condition.startswith("||", i):
            tokens.append("||")
            i += 2
            continue
        if ch in "!()":
            tokens.append(ch)
            i += 1
            continue
        m = _IDENT_RE.match(condition, i)
        if m:
            tokens.append(m.group(0))
            i = m.end()
            continue
        raise ValueError(f"无法识别的条件字符: {ch!r}")
    return tokens


class _ConditionParser:
    """``!#if`` 条件表达式的递归下降解析器（|| 优先级低于 &&）。"""

    def __init__(self, tokens: list[str], env: frozenset[str]) -> None:
        self.tokens = tokens
        self.env = env
        self.i = 0

    def _peek(self) -> str | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def parse(self) -> bool:
        value = self._or()
        if self.i != len(self.tokens):
            raise ValueError(f"条件存在多余标记: {self.tokens[self.i]!r}")
        return value

    def _or(self) -> bool:
        value = self._and()
        while self._peek() == "||":
            self.i += 1
            rhs = self._and()
            value = value or rhs
        return value

    def _and(self) -> bool:
        value = self._unary()
        while self._peek() == "&&":
            self.i += 1
            rhs = self._unary()
            value = value and rhs
        return value

    def _unary(self) -> bool:
        if self._peek() == "!":
            self.i += 1
            return not self._unary()
        return self._primary()

    def _primary(self) -> bool:
        token = self._peek()
        if token == "(":
            self.i += 1
            value = self._or()
            if self._peek() != ")":
                raise ValueError("条件括号不匹配")
            self.i += 1
            return value
        if token is None or token in ("&&", "||", ")"):
            raise ValueError("条件表达式不完整")
        self.i += 1
        return token.lower() in self.env


def evaluate_condition(condition: str, tokens: frozenset[str]) -> bool:
    """求值 ``!#if`` 条件；无法解析时按 False 处理（保守排除该分支）。"""
    try:
        return _ConditionParser(_tokenize(condition), tokens).parse()
    except ValueError as exc:
        LOG.warning("无法解析 !#if 条件 %r: %s，按 False 处理", condition, exc)
        return False


def _match_directive(stripped: str) -> tuple[str, str] | None:
    """识别 ``!#`` 指令，返回 (指令名, 参数)。"""
    if not stripped.startswith("!#"):
        return None
    body = stripped[2:]
    name, _, arg = body.partition(" ")
    return name.strip().lower(), arg.strip()


def preprocess(
    lines: Iterable[str],
    *,
    tokens: frozenset[str] = TARGET_TOKENS,
    resolve_include: IncludeResolver | None = None,
    base_url: str | None = None,
    depth: int = 0,
    chain: set[str] | None = None,
) -> list[str]:
    """按预处理器指令过滤并展开列表文本。

    - ``!#if``/``!#else``/``!#endif``：按 ``tokens`` 求值，仅保留生效分支的内容。
    - ``!#include``：在生效分支内通过 ``resolve_include`` 解析并递归展开；未提供
      回调或解析失败则跳过该 include。
    - 其它 ``!`` 注释与普通规则行原样保留（仅当其所在分支生效）。
    """
    if chain is None:
        chain = set()

    out: list[str] = []
    stack: list[bool] = []

    def active() -> bool:
        return all(stack)

    for raw in lines:
        directive = _match_directive(raw.strip())
        if directive is None:
            if active():
                out.append(raw)
            continue

        name, arg = directive
        if name == "if":
            stack.append(evaluate_condition(arg, tokens))
        elif name == "else":
            if stack:
                stack[-1] = not stack[-1]
            else:
                LOG.warning("出现无匹配 !#if 的 !#else")
        elif name == "endif":
            if stack:
                stack.pop()
            else:
                LOG.warning("出现无匹配 !#if 的 !#endif")
        elif name == "include":
            if not active() or not arg:
                continue
            if resolve_include is None:
                continue
            if depth >= INCLUDE_MAX_DEPTH:
                LOG.warning("!#include 递归超过 %d 层，跳过: %s", INCLUDE_MAX_DEPTH, arg)
                continue
            from urllib.parse import urljoin

            target = urljoin(base_url or "", arg) if base_url else arg
            if target in chain:
                LOG.warning("检测到 !#include 循环，跳过: %s", target)
                continue
            resolved = resolve_include(target)
            if resolved is None:
                LOG.warning("无法解析 !#include: %s", target)
                continue
            sub_lines, sub_url = resolved
            chain.add(target)
            out.extend(
                preprocess(
                    sub_lines,
                    tokens=tokens,
                    resolve_include=resolve_include,
                    base_url=sub_url or target,
                    depth=depth + 1,
                    chain=chain,
                )
            )
            chain.discard(target)
        # 其它 !# 指令（如 !#endif 缺失、未知指令）按注释忽略

    if stack:
        LOG.warning("列表存在未闭合的 !#if（缺少 !#endif）")
    return out
