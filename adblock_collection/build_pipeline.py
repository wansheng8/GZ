"""显式阶段化流水线。

把构建流程拆成命名、有序、接收并返回规则集的纯函数阶段，由 ``Pipeline`` 负责计时、
计数与报告收集。副作用集中在采集阶段（网络/缓存）与输出阶段（写文件），
其余阶段不感知 I/O。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from .rules import Rule

LOG = logging.getLogger("adblock_collection")


class BuildError(RuntimeError):
    """构建期内部一致性错误，对应退出码 3。"""


class StageError(BuildError):
    """阶段执行失败。"""


class InvariantError(BuildError):
    """产物不变量被破坏。"""


@dataclass(frozen=True)
class BuildFlags:
    alias_normalize: bool = True
    resolve_conflicts: bool = True
    per_rule_classify: bool = True
    domain_fold: bool = True
    # 兼容旧 `--redundant`：仅当增强折叠关闭时用于复现重构前产物（P10 字节基线）
    redundant: bool = False
    split_by_category: bool = False
    gen_dns: bool = True
    gen_rulesets: bool = True
    dry_run: bool = False


@dataclass
class BuildContext:
    config_path: Path
    output_dir: Path
    dns_policy: dict
    security_policy: dict
    flags: BuildFlags
    # 阶段产出的报告与统计（enhancements / source_counts / failed_sources 等）
    artifacts: dict = field(default_factory=dict)


@dataclass
class StageReport:
    name: str
    in_rules: int
    out_rules: int
    elapsed_ms: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "in_rules": self.in_rules,
            "out_rules": self.out_rules,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class PipelineReport:
    stages: list[StageReport] = field(default_factory=list)

    @property
    def total_elapsed_ms(self) -> int:
        return sum(s.elapsed_ms for s in self.stages)

    def to_dict(self) -> dict:
        return {
            "stages": [s.to_dict() for s in self.stages],
            "total_elapsed_ms": self.total_elapsed_ms,
        }


@runtime_checkable
class Stage(Protocol):
    name: str

    def __call__(self, rules: list[Rule], ctx: BuildContext) -> list[Rule]: ...


@dataclass
class FunctionStage:
    """把一个 ``(rules, ctx) -> rules`` 函数包装为命名阶段。"""

    name: str
    func: Callable[[list[Rule], BuildContext], list[Rule]]

    def __call__(self, rules: list[Rule], ctx: BuildContext) -> list[Rule]:
        return self.func(rules, ctx)


class Pipeline:
    def __init__(self, stages: list[Stage]) -> None:
        self.stages = list(stages)

    def run(
        self, rules: list[Rule], ctx: BuildContext
    ) -> tuple[list[Rule], PipelineReport]:
        report = PipelineReport()
        for stage in self.stages:
            started = time.perf_counter()
            try:
                produced = stage(rules, ctx)
            except BuildError:
                raise
            except Exception as exc:  # noqa: BLE001 - 统一转为 StageError 以给出退出码 3
                LOG.error("阶段 %s 执行失败: %s", stage.name, exc)
                raise StageError(f"阶段 {stage.name} 失败: {exc}") from exc
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            report.stages.append(
                StageReport(stage.name, len(rules), len(produced), elapsed_ms)
            )
            LOG.info(
                "阶段 %-14s %d -> %d 条 (%d ms)",
                stage.name,
                len(rules),
                len(produced),
                elapsed_ms,
            )
            rules = produced
        return rules, report
