"""需求 9：解析与序列化往返一致性校验。

对每种输出格式，把已落盘的产物重新解析回来，再与源规则比对：

- adblock：重新解析出的规则归一化集合 SHALL 与源规则集合一致（逐条无损）。
- hosts / ipv6 hosts / domains / adblock_domains：这四种是 DNS 层的等价表达，
  重新解析出的域名集合 SHALL 等于源规则的整域阻断域名集合。

一旦不一致，调用方（``cli.emit_outputs``）以退出码 3 结束，并指出格式与差异条目。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from .rules import Rule, parse_lines
from .writer import _blocked_domains

# 完整版 adblock 列表逐条比对；其余四种按 DNS 域名集合比对
ADBLOCK_FORMATS = ("adblock",)
DOMAIN_FORMATS = ("hosts", "hosts_ipv6", "domains", "adblock_domains")

_COMMENT_PREFIXES = {
    "adblock": ("!",),
    "adblock_domains": ("!",),
    "hosts": ("#",),
    "hosts_ipv6": ("#",),
    "domains": ("#",),
}


def _payload_lines(path: Path, format_name: str) -> list[str]:
    """读取产物中的规则行，跳过头部注释、空行与 ``[header]``。"""
    prefixes = _COMMENT_PREFIXES.get(format_name, ("!", "#"))
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            continue
        if stripped.startswith(prefixes):
            continue
        lines.append(line)
    return lines


def _norm_counter(rules: Iterable[Rule]) -> Counter:
    return Counter(r.norm for r in rules if r.norm)


def _sample(items: list[str], n: int = 3) -> str:
    shown = ", ".join(repr(x) for x in items[:n])
    more = "" if len(items) <= n else f" 等 {len(items)} 条"
    return shown + more


def check_roundtrip(
    paths: dict[str, Path],
    rules: Iterable[Rule],
    policy: dict | None = None,
) -> list[str]:
    """校验产物往返一致性，返回不一致描述列表；空列表表示全部通过。

    ``paths`` 为 ``{格式名: 产物路径}``，仅校验存在的文件。
    """
    source = list(rules)
    source_norms = _norm_counter(source)
    source_domains = _blocked_domains(source, policy)

    issues: list[str] = []
    for fmt, path in paths.items():
        if path is None or not Path(path).exists():
            continue
        parsed = parse_lines(_payload_lines(Path(path), fmt))
        if fmt in ADBLOCK_FORMATS:
            parsed_norms = _norm_counter(parsed)
            missing = list(source_norms - parsed_norms)
            extra = list(parsed_norms - source_norms)
            if missing:
                issues.append(
                    f"{fmt} 往返丢失 {len(missing)} 条规则: {_sample(missing)}"
                )
            if extra:
                issues.append(
                    f"{fmt} 往返多出 {len(extra)} 条规则: {_sample(extra)}"
                )
        else:
            parsed_domains = _blocked_domains(parsed, policy)
            missing = sorted(source_domains - parsed_domains)
            extra = sorted(parsed_domains - source_domains)
            if missing:
                issues.append(
                    f"{fmt} 往返丢失 {len(missing)} 个域名: {_sample(missing)}"
                )
            if extra:
                issues.append(
                    f"{fmt} 往返多出 {len(extra)} 个域名: {_sample(extra)}"
                )
    return issues


class RoundTripError(Exception):
    """解析-序列化往返不一致。"""


def assert_roundtrip(
    paths: dict[str, Path],
    rules: Iterable[Rule],
    policy: dict | None = None,
) -> None:
    """往返校验失败时抛出 ``RoundTripError``。"""
    issues = check_roundtrip(paths, rules, policy)
    if issues:
        raise RoundTripError("往返校验失败: " + "; ".join(issues))

