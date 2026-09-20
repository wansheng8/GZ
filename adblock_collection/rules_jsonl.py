"""中间产物 ``rules.jsonl`` 的读写与派生。

``rules.jsonl`` 每行一条规则，字段与阶段缓存 ``pipeline.save_parsed`` 同构并额外保留
``sources`` 列表，保证「解析 -> 输出」往返无损。所有输出格式均可由该中间产物派生，
重建过程不发起网络请求。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path

from .rules import Rule

LOG = logging.getLogger("adblock_collection")

DEFAULT_JSONL_PATH = Path(".cache/build/rules.jsonl")


def rule_to_dict(rule: Rule) -> dict:
    return {
        "raw": rule.raw,
        "norm": rule.norm,
        "kind": rule.kind,
        "category": rule.category,
        "is_exception": rule.is_exception,
        "is_css": rule.is_css,
        "is_scriptlet": rule.is_scriptlet,
        "is_badfilter": rule.is_badfilter,
        "is_important": rule.is_important,
        "domains": list(rule.domains),
        "source": rule.source,
        "sources": list(rule.sources),
        "options": dict(rule.options),
    }


def rule_from_dict(item: dict) -> Rule:
    return Rule(
        raw=item["raw"],
        norm=item["norm"],
        kind=item.get("kind", "network"),
        category=item.get("category", "other"),
        is_exception=item.get("is_exception", False),
        is_css=item.get("is_css", False),
        is_scriptlet=item.get("is_scriptlet", False),
        is_badfilter=item.get("is_badfilter", False),
        is_important=item.get("is_important", False),
        domains=item.get("domains", []),
        source=item.get("source"),
        sources=item.get("sources", []),
        options=item.get("options", {}),
    )


def dump_rules_jsonl(rules: Iterable[Rule], path: Path) -> int:
    """把规则集写为 JSONL，返回写入条数。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for rule in rules:
            fh.write(json.dumps(rule_to_dict(rule), ensure_ascii=False))
            fh.write("\n")
            count += 1
    LOG.info("中间产物已写入: %s (%d 条)", path, count)
    return count


def load_rules_jsonl(path: Path) -> list[Rule]:
    """读取 JSONL；文件缺失或损坏时抛出 ``ValueError``/``OSError``。"""
    rules: list[Rule] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rules.append(rule_from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError) as exc:
                raise ValueError(f"{path}:{lineno} 规则行损坏: {exc}") from exc
    return rules


def safe_load_rules_jsonl(path: Path) -> list[Rule] | None:
    """损坏或缺失时返回 None，由调用方回退到完整重建。"""
    if not path.exists():
        return None
    try:
        return load_rules_jsonl(path)
    except (ValueError, OSError) as exc:
        LOG.warning("中间产物不可用，回退完整重建: %s", exc)
        return None


def emit_from_jsonl(jsonl_path: Path, output_dir: Path, ctx) -> int:
    """由中间产物离线重建全部输出格式，返回规则条数。

    复用 ``cli.emit_outputs`` 的写盘逻辑；不发起任何网络请求。
    """
    from .cli import emit_outputs

    rules = load_rules_jsonl(jsonl_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    emit_outputs(rules, ctx, output_dir=output_dir)
    return len(rules)
