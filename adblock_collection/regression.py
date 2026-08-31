"""误杀回归校验。

维护一份「必须允许 / 必须拦截」的域名清单（config/false_positives.yaml），每次构建后
自动校验，把「大站突然被整域封禁」在发生前拦住。

校验基于最终发布的整域阻断集合（与 DNS/Hosts 输出一致）：

- allow 清单：若某域名或其任意祖先域出现在整域阻断集合中，视为误杀，记录违规。
- block 清单：若某域名及其任意祖先域均不在整域阻断集合中，视为漏拦，记录缺失。

设计原则：仅校验「整域阻断」类规则（纯域名 / 带修饰符的单域名规则），不校验 CSS 元素
隐藏类规则，避免把页面去广告误判为误杀。校验集合与写入 DNS/Hosts 的策略一致，因此
对哪些域名会被整域拦截有最准确的判断。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import yaml

from .rules import Rule
from .writer import _blocked_domains


def load_false_positives(config_path: Path) -> dict:
    """读取 false_positives 配置，返回 {"allow": [...], "block": [...]}。

    查找顺序：若传入文件本身是 false_positives.yaml 则直接用；否则优先取同级目录下的
    false_positives.yaml（即传入 sources.yaml 时自动定位到 config/false_positives.yaml）。
    """
    if config_path.name == "false_positives.yaml" and config_path.exists():
        path = config_path
    else:
        path = config_path.parent / "false_positives.yaml"
    if not path.exists():
        return {"allow": [], "block": []}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return {
        "allow": [str(d).strip().lower() for d in (data.get("allow") or []) if d],
        "block": [str(d).strip().lower() for d in (data.get("block") or []) if d],
    }


def _ancestors(domain: str) -> list[str]:
    parts = domain.split(".")
    return [".".join(parts[i:]) for i in range(len(parts))]


def check_allow(rules: Iterable[Rule], fps: list[str], policy: Optional[dict] = None) -> list[dict]:
    """返回误杀违规：allow 域名或其祖先被整域阻断。"""
    blocked = _blocked_domains(rules, policy)
    violations: list[dict] = []
    for d in fps:
        for anc in _ancestors(d):
            if anc in blocked:
                violations.append({"domain": d, "blocked_by": anc})
                break
    return violations


def check_block(rules: Iterable[Rule], fps: list[str], policy: Optional[dict] = None) -> list[dict]:
    """返回漏拦：block 域名及其祖先均未被整域阻断。"""
    blocked = _blocked_domains(rules, policy)
    missing: list[dict] = []
    for d in fps:
        if not any(anc in blocked for anc in _ancestors(d)):
            missing.append({"domain": d})
    return missing


def run_regression(rules: Iterable[Rule], fps: dict, policy: Optional[dict] = None) -> dict:
    return {
        "allow_violations": check_allow(rules, fps.get("allow", []), policy),
        "block_missing": check_block(rules, fps.get("block", []), policy),
    }
