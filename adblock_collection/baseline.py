"""产物字节级基线比对。

用于骨架重构阶段锁定输出：增强开关关闭时，新流程产物应与基线逐字节一致。
``sources_status.json`` 的 ``generated_at`` 是唯一的时间戳字段，比对时单独剔除。
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# 需要剔除时间戳后再比较的产物
_TIMESTAMP_KEYS: dict[str, tuple[str, ...]] = {
    "sources_status.json": ("generated_at",),
}


@dataclass
class FileDiff:
    name: str
    same: bool
    missing: bool = False
    first_diff_line: int | None = None
    diff_lines: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "same": self.same,
            "missing": self.missing,
            "first_diff_line": self.first_diff_line,
            "diff_lines": self.diff_lines,
        }


@dataclass
class BaselineDiff:
    files: list[FileDiff] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(f.same for f in self.files)

    @property
    def mismatches(self) -> list[FileDiff]:
        return [f for f in self.files if not f.same]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "files": [f.to_dict() for f in self.files],
        }


def _canonical(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    keys = _TIMESTAMP_KEYS.get(name)
    if not keys:
        return text
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(data, dict):
        for key in keys:
            data.pop(key, None)
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def _relative_files(root: Path) -> set[str]:
    return {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file()
    }


def compare_baseline(
    old_dir: Path,
    new_dir: Path,
    extra_ignores: Iterable[str] | None = None,
) -> BaselineDiff:
    """逐文件比对两个产物目录，返回差异明细。"""
    ignores = set(extra_ignores or ())
    names = sorted(_relative_files(old_dir) | _relative_files(new_dir))
    files: list[FileDiff] = []
    for name in names:
        if name in ignores:
            continue
        old_file = old_dir / name
        new_file = new_dir / name
        if not old_file.exists() or not new_file.exists():
            files.append(FileDiff(name=name, same=False, missing=True))
            continue
        old_lines = _canonical(old_file, name).splitlines()
        new_lines = _canonical(new_file, name).splitlines()
        first_diff = None
        diff_lines = abs(len(old_lines) - len(new_lines))
        for idx, (a, b) in enumerate(zip(old_lines, new_lines), 1):
            if a != b:
                diff_lines += 1
                if first_diff is None:
                    first_diff = idx
        files.append(
            FileDiff(
                name=name,
                same=first_diff is None and diff_lines == 0,
                first_diff_line=first_diff,
                diff_lines=diff_lines,
            )
        )
    return BaselineDiff(files=files)
