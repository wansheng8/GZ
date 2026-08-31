"""来源血缘与语义去重增强。

Provenance（血缘）：
    聚合每条规范化规则来自哪些上游、属于哪些「独立源组」、跨源一致度（出现源数 /
    独立组数），并据此给出置信度（0~1）。用于排查「为何某域名被封」与评估规则可信度。

Semantic dedup（语义去重增强）：
    在文本去重（norm 相等）之上，补充语义关系识别并输出关系图：
    - PARENT_CHILD：父域规则已阻断时，子域纯域名规则在阻断语义上冗余（已由
      remove_redundant_domains 处理，此处做计数与关系图记录）。
    - CROSS_SOURCE_DUPLICATE：同一规则出现在多个源，仅保留一份但保留血缘。
    - EXCEPTION_CONFLICT：阻断规则与例外（@@）作用于同一域名，记录冲突供审计。

置信度公式（示例）：
    confidence = min(1.0, 0.5 + 0.1 * independent_group_count)
即单一源 0.6，每多一个独立组 +0.1，封顶 1.0。独立组比单纯 source_count 更能反映
「多个列表共享同一上游」造成的虚高。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .rules import Rule


# 独立源组归类：同一组的源视为一个信息源，避免共享上游虚高计数。
# 归类依据为源名关键前缀；未匹配归入自身。
_SOURCE_GROUP_RULES = {
    "adguard": ["AdGuard", "Adguard"],
    "easylist": ["EasyList", "Easy", "easylist"],
    "ubo": ["uBlock", "ubo", "uBO"],
    "chinese": ["China", "Chinese", "CJX", "EasyListChina"],
    "security": ["Malware", "Phishing", "MalwareDomain", "Abuse", "security", "Security", "urlhaus", "URLHaus"],
    "community": ["Fanboy", "FanBoy", "community", "Community", "wangwang", "AdblockPlus"],
}


def source_group(source_name: str) -> str:
    if not source_name:
        return "unknown"
    for group, keys in _SOURCE_GROUP_RULES.items():
        if any(k.lower() in source_name.lower() for k in keys):
            return group
    return source_name


@dataclass
class Provenance:
    norm: str
    raw: str
    sources: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    source_count: int = 0
    independent_group_count: int = 0
    confidence: float = 0.0
    is_exception: bool = False
    category: str = "other"
    conflict_with: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "rule": self.raw,
            "norm": self.norm,
            "sources": self.sources,
            "groups": self.groups,
            "source_count": self.source_count,
            "independent_group_count": self.independent_group_count,
            "confidence": round(self.confidence, 3),
            "is_exception": self.is_exception,
            "category": self.category,
            "conflict_with": self.conflict_with,
        }


def _confidence(independent_group_count: int) -> float:
    return min(1.0, 0.5 + 0.1 * max(0, independent_group_count))


def build_provenance(rules: Iterable[Rule]) -> dict[str, Provenance]:
    """聚合规范化规则的血缘信息。返回 norm -> Provenance。"""
    by_norm: dict[str, Provenance] = {}
    for r in rules:
        if r.norm not in by_norm:
            p = Provenance(
                norm=r.norm,
                raw=r.raw,
                is_exception=r.is_exception,
                category=r.category,
            )
            by_norm[r.norm] = p
        p = by_norm[r.norm]
        # 优先使用去重合并后的 sources，回退到单值 source
        srcs = r.sources if getattr(r, "sources", None) else ([r.source] if r.source else [])
        for sname in srcs:
            if not sname:
                continue
            if sname not in p.sources:
                p.sources.append(sname)
                grp = source_group(sname)
                if grp not in p.groups:
                    p.groups.append(grp)
    for p in by_norm.values():
        p.source_count = len(p.sources)
        p.independent_group_count = len(p.groups)
        p.confidence = _confidence(p.independent_group_count)
    return by_norm


def detect_exception_conflicts(rules: Iterable[Rule]) -> dict[str, list[str]]:
    """检测阻断规则与例外规则作用于同一域名族的冲突。

    返回 domain -> [冲突的 norm 列表]。用于审计「同一域名既被封又被放行」的情况。
    """
    blocked_roots: dict[str, list[str]] = defaultdict(list)
    exception_norms: dict[str, list[str]] = defaultdict(list)
    for r in rules:
        if not r.domains:
            continue
        d = r.domains[0]
        if r.is_exception:
            exception_norms[d].append(r.norm)
        else:
            blocked_roots[d].append(r.norm)
    conflicts: dict[str, list[str]] = {}
    for d, ex_norms in exception_norms.items():
        if d in blocked_roots:
            conflicts[d] = blocked_roots[d] + ex_norms
    return conflicts


# 语义关系类型
REL_PARENT_CHILD = "PARENT_CHILD"
REL_CROSS_SOURCE = "CROSS_SOURCE_DUPLICATE"
REL_EXCEPTION_CONFLICT = "EXCEPTION_CONFLICT"
REL_EXACT = "EXACT_DUPLICATE"


@dataclass
class Relation:
    kind: str
    a: str
    b: str


def build_relation_graph(rules: Iterable[Rule], provenance: Optional[dict] = None) -> list[Relation]:
    """构建规则间的语义关系图。

    - PARENT_CHILD：纯域名阻断规则中，父域已存在阻断规则时，子域规则标记为子关系。
    - EXCEPTION_CONFLICT：阻断与例外作用于同域名。
    - CROSS_SOURCE_DUPLICATE：同一 norm 出现在多个独立源组。
    """
    # 父/子域关系与跨源重复基于阻断型单域名规则
    rules = [r for r in rules if r.domains and len(r.domains) == 1]
    blocked: dict[str, Rule] = {}
    for r in rules:
        if r.kind == "network" and not r.is_exception:
            blocked.setdefault(r.domains[0], r)
    relations: list[Relation] = []
    for domain, r in blocked.items():
        parts = domain.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[i:])
            if parent in blocked and parent != domain:
                relations.append(Relation(REL_PARENT_CHILD, parent, domain))
                break

    # 例外冲突（保留例外规则用于检测）
    conflicts = detect_exception_conflicts(rules)
    for d, norms in conflicts.items():
        for n in norms:
            relations.append(Relation(REL_EXCEPTION_CONFLICT, d, n))

    # 跨源重复（基于血缘，复用已计算结果避免重复 O(N) 重建）
    prov = provenance if provenance is not None else build_provenance(rules)
    for p in prov.values():
        if p.source_count > 1:
            relations.append(Relation(REL_CROSS_SOURCE, p.norm, ",".join(p.sources)))
    return relations


def semantic_dedupe(rules: Iterable[Rule]) -> list[Rule]:
    """在文本去重基础上保留血缘，返回去重后的规则列表（与 dedupe 行为一致，保留首次出现）。"""
    seen: dict[str, Rule] = {}
    order: list[str] = []
    for r in rules:
        if r.norm not in seen:
            seen[r.norm] = r
            order.append(r.norm)
    return [seen[k] for k in order]


def cross_source_duplicate_count(provenance: dict[str, Provenance]) -> int:
    """统计出现在多于一个源的规范化规则数（用于报告跨源重复率）。"""
    return sum(1 for p in provenance.values() if p.source_count > 1)


def load_security_policy(config_path: Path) -> dict:
    """读取 security_policy 配置，返回安全类独立发行策略。"""
    import yaml

    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    raw = data.get("security_policy", {}) or {}
    return {
        "categories": raw.get("categories", ["malware", "phishing", "mining"]),
        "source_drop_percent": float(raw.get("source_drop_percent", 80)),
    }
