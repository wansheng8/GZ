# 流程细节管理（FLOW）

本文档定义 `build` 主流程各阶段的**输入 → 执行 → 校验 → 产物 → 失败处置**，供维护者与 CI 排查使用。目标：任何一次构建异常都能按本文档定位到具体阶段并执行标准处置。

入口命令（与 CI 完全一致）：

```bash
python3 -m adblock_collection build --out dist --split-by-category --redundant
```

退出码约定：

| 码 | 含义 |
|----|------|
| 0 | 成功（门禁与回归均通过） |
| 1 | 构建完成但门禁或误杀回归失败 |
| 2 | 本地增强规则校验未通过（构建前阻断） |
| 其他 | 配置/环境错误（见各阶段） |

---

## 阶段总览

```
配置加载 → 本地规则校验 → 上游收集(并行下载) → 合并去重 → 冗余消除
        → 多格式输出 → 血缘/关系图 → 上游健康报告 → 误杀回归 → 质量门禁 → manifest
```

| 阶段 | 输入 | 执行位置 | 校验 | 产物 | 失败处置 |
|------|------|----------|------|------|----------|
| 1 配置加载 | `config/sources.yaml` | `merge.load_sources` | YAML 可解析、源无重复 | `sources` 列表 | 文件缺失/解析失败 → 返回 1 |
| 2 本地规则校验 | `config/local_rules.txt` | `merge.validate_local_rules` | 无通配误伤（`##*`/`##body`/域通配/裸 `*`） | 校验报告（日志） | 有违规 → 返回 2 阻断发布 |
| 3 上游收集 | 51 源 + mirror | `merge.collect`（线程池并行） | 失败源记录、过期缓存回退 | `.cache/sources/`、`sources_status.json` | 单源失败 → 容忍并记录；全源失败 → 产物为空 |
| 4 合并去重 | 各源 Rule 列表 | `merge.dedupe` / `apply_allowlist` / `apply_badfilter` | 白名单精确放行、badfilter 抵消 | 去重后规则集 | 逻辑错误 → 测试兜底（tests/） |
| 5 冗余消除 | 去重后规则 | `remove_redundant_domains` / `remove_redundant_css` | 仅纯域名/纯类名归并 | 精简规则集 | 仅记录移除数，不阻断 |
| 6 多格式输出 | 全量规则 | `writer._emit` + `_emit_by_category` + `_emit_security` | 分类子列表并集 == 完整版 | `dist/*.txt` / `*_dns.txt` / `*_dns_ipv6.txt` / `*_domains.txt` / `*.stats.*` / `*.dns_safety.json` | 不变量断言失败 → 报错阻断 |
| 7 血缘/关系图 | 全量规则 | `provenance.build_provenance` / `build_relation_graph` | 跨源重复、例外冲突计数 | `provenance.json` / `relation_graph.json` | 容忍（仅日志） |
| 8 上游健康报告 | 失败源列表 | `cli` 写入 | 源数量、失败清单 | `sources_status.json` | 仅记录 |
| 9 误杀回归 | `config/false_positives.yaml` | `regression.run_regression` | `allow_violations == 0` | `regression_report.json` | 有误杀 → 返回 1 阻断 |
| 10 质量门禁 | 本批 vs 上批 metrics | `quality_gate.evaluate` | 增长率在阈值内 | `build_report.json` / `previous_metrics.json` | 超阈值 → 返回 1 阻断 |

---

## 阶段 1：配置加载

**前置条件**：`config/sources.yaml` 存在且为合法 YAML。

**自检**：

```bash
python3 -m adblock_collection sources   # 列出全部源，检查是否有重复 URL/名称
```

**失败处置**：
- 文件缺失：检查是否误删；从 git 恢复。
- 重复源：删除重复条目；`sources` 命令输出中检查。

---

## 阶段 2：本地规则校验

**触发**：每次 build 自动执行，无需手动。校验逻辑位于 `merge.validate_local_rules`。

**禁止的规则模式**（触发返回码 2）：

| 模式 | 示例 | 原因 |
|------|------|------|
| 全局隐藏 | `##*`、`*##` | 无差别隐藏整页 |
| 整页主体 | `example.com##body` / `##html` / `##head` | 隐藏页面骨架 |
| 域名级通配 | `*.example.com##`、`*##.banner` | 跨域误伤 |
| 选择器裸通配 | `example.com##*`、`##.a *, ##.b > *` | 扩大隐藏范围 |

**允许**：精确类名/ID 选择器、属性包含匹配（`[class*="ad"]`）。

**自检**：

```bash
python3 - <<'PY'
from pathlib import Path
from adblock_collection.merge import validate_local_rules
v = validate_local_rules(Path("config/sources.yaml"))
print(f"违规数: {len(v)}")
for x in v: print(" ", x)
PY
```

**失败处置**：删除/修正违规行，改用精确选择器后重试。

---

## 阶段 3：上游收集（并行下载）

**行为**：线程池（最多 16 并发）下载全部源；单源失败不中断整体；主源失败自动尝试 mirror；二者皆失败且存在过期缓存时回退缓存。

**关键文件**：
- `.cache/sources/<sha256>.` ：源原始文本缓存
- `dist/sources_status.json` ：本次构建的失败源清单

**自检**：

```bash
python3 -c "import json;d=json.load(open('dist/sources_status.json'));print('失败源:',d['failed_sources'])"
```

**失败处置**：
- 失败源 **< 5**：容忍，等待下一次构建自动恢复（CI 输出 WARNING 不阻断）。
- 失败源 **≥ 5**：按 `docs/OPS.md` 第 6 节「源失效」处置。
- 全部失败：产物将为空，质量门禁必然失败，检查网络/代理。

---

## 阶段 4：合并去重

**顺序**（`cli.py` build 内固定）：
1. `dedupe`：按规范化键（norm）去重，保留首次出现；合并跨源来源。
2. `apply_allowlist`：白名单**精确匹配**放行——`tencent.com` 仅放行裸域，`ad.tencent.com` 仍拦截。
3. `apply_badfilter`：移除被 `,badfilter` 抵消的规则。

**不可变更点**：apply_allowlist 必须保持精确匹配（祖先匹配会把子域广告一并放行，历史教训）。

---

## 阶段 5：冗余消除（--redundant）

**范围**：仅 `||a.com^` 这类纯域名阻断规则做父域归并；CSS 仅对「单域 + 纯类名」去重。复杂选择器（含逗号/属性/伪类）不参与，避免误删。

**注意**：此阶段只减不加。若某次构建规则数异常增加且启用了 redundant，先检查是否为新增源贡献。

---

## 阶段 6：多格式输出

**产物矩阵**（完整版 + 每个类别子集）：

| 文件 | 格式 |
|------|------|
| `adblock_collection_full[_category].txt` | Adblock Plus / uBO / AdGuard |
| `*_dns.txt` | hosts（`0.0.0.0 domain`） |
| `*_dns_ipv6.txt` | hosts（`:: domain`） |
| `*_domains.txt` | 每行一域名（AdGuard DNS/Home） |
| `*.stats.txt` / `*.stats.json` | 分类/来源统计 |
| `*.dns_safety.json` | DNS 安全分级分布 |
| `security/adblock_collection_security*.txt` | 安全类独立发行 |

**不变量**：按类别拆分的子列表（非 DNS 后缀文件）并集必须等于完整版。若被破坏，构建报错（`cli.py` 断言）。

---

## 阶段 7：血缘/关系图

**输出**：
- `provenance.json`：规则总数、跨源重复数、例外冲突、父域子域关系、高置信度占比。
- `relation_graph.json`：语义关系明细（PARENT_CHILD / EXCEPTION_CONFLICT / CROSS_SOURCE）。

**用途**：排查「为何某域名被封」、审计跨源一致性。

---

## 阶段 8：上游健康报告

每次构建写入 `dist/sources_status.json`，含总源数、失败源清单、生成时间。供订阅者判断数据完整性。

---

## 阶段 9：误杀回归

**校验清单**：`config/false_positives.yaml` 的 `allow`（大站不应被整域误封）与 `block`（广告域名应被拦截，缺失仅 WARNING）。

**判定**：`allow_violations` 非空 → 构建失败（返回 1）。`block_missing` 仅 WARNING 不阻断。

**失败处置**：见 `docs/OPS.md` 第 4 节「改白名单」。

---

## 阶段 10：质量门禁

**阈值**（`config/sources.yaml` `quality_gate`）：

| 指标 | 阈值 |
|------|------|
| total_rule_growth_percent | 20% |
| dns_growth_percent | 15% |
| source_drop_percent | 50% |
| category_growth_percent | 30% |

**机制**：`previous_metrics.json` 记录上一次构建的基线，本次对比增长率。超出阈值 → 失败。

**失败处置**：见 `docs/OPS.md` 第 5 节「门禁失败」。**关键**：`previous_metrics.json` 是门禁基线，删除/覆盖会导致误判（历史教训：一次离线测试把基线写成 10 条，导致门禁误报 1300 万倍增长）。
