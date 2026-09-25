# 广告拦截正确性审计与升级方案

本文是对「为什么会出现不拦截（漏拦）与误拦截（误拦）」的专项审计，基于当前 `dist/` 产物与源码只读分析，给出根因、证据与可独立发布的升级方案。方案编号 `C*` 表示 correctness 修复；与 `docs/UPGRADE_PROPOSAL.md` §6 的单元 `U*` 互补，重叠处已互相引用。

## 0. 结论摘要

| 类别 | 主因 | 量级 | 优先级 |
| :--- | :--- | :--- | :--- |
| 漏拦 | 仲裁把「非阻断型例外」误当整域全局白名单，撤销了整域阻断 | 33 个域名 | P0 |
| 漏拦 | DNS / 连接层规则集只覆盖整域可表达规则，路径/类型/作用域规则不进产物 | 约 82,425 条网络阻断规则 | P1 |
| 误拦 | 导航修饰（`$popup`/`$document`）被放大为整域拦截 | 108 个域名 | P1 |
| 误拦 | 上游整域误标，仅靠静态 `false_positives.yaml`（约 125 条）事后兜底 | 静态清单 | P1 |
| 漏拦 | DNS 清单用例混淆 / DoH 绕过 / 测试站以元素测试为主，用户误判「0 拦截」 | 认知与文档 | P2 |

最高优先：修复 `writer._is_global_domain_exception`（C1），它以缺陷方式同时污染浏览器与 DNS 两条产物链。

## 1. 调查范围与方法

只读复现，不依赖构建：

- 读取 `dist/adblock_collection_full.txt`、`*_domains.txt`、`*_dns.txt`、`rulesets/*`、`*.dns_safety.json`、`arbitration.json`、`build_report.json`；
- 用真实模块复核判定，例如：

```bash
PYTHONPATH=/workspace python3 - <<'PY'
from adblock_collection.rules import parse_lines
from adblock_collection.writer import _is_global_domain_exception
from adblock_collection.arbitrate import arbitrate
block = parse_lines(["||tiktok.com^"], category_hint="ads", source="Upstream")
exc = parse_lines(["@@||tiktok.com^$generichide"], category_hint="ads", source="Upstream")
kept, recs = arbitrate(block + exc)
print([r.raw for r in kept])           # 只剩例外，阻断被撤销
print(recs[0].to_dict())
PY
```

## 2. 漏拦（该拦的没拦）

### C1 非阻断型例外被当成整域全局白名单（P0，缺陷）

**现象**：`@@||ads.microsoft.com^$generichide`、`@@||tradedoubler.com^$removeparam=tduid`、`@@||readmng.com^$csp=...` 这类只关外观过滤/只去参/只注入 CSP 的**修饰型例外**，被 `arbitrate` 当作「整域全局例外」，从而删除同域整域阻断规则。

**证据**（`dist/arbitration.json`）：122 条仲裁记录中，115 条原因为「整域全局例外优先于整域阻断」，其中 **33 条的胜出例外带非阻断修饰**，被删掉的都是 `||domain^`：

- `ads.microsoft.com`（广告域）、`em.dynamicyield.com`（追踪）、`adshnk.com`、`awempire.com`、`tradedoubler.com`、`fingerprintjs.com`、`freebitco.in`、`ucooz.com`、`appnee.com` 等。

**根因**：`adblock_collection/writer.py` 的 `_is_global_domain_exception` 只排除了 `SCOPED_MODIFIERS | RESOURCE_TYPE_MODIFIERS | PARTY_MODIFIERS`，没有排除 `NON_BLOCKING_MODIFIERS`（`$generichide/$elemhide/$specifichide/$removeparam/$csp/$genericblock/$permissions/...`）。`$generichide` 占被误判例外的 1,426 条，是绝对主因。

**影响面**：`writer._is_global_domain_exception` 同时被 `arbitrate.arbitrate` 与 `writer._scan_dns_domains` 使用，因此**浏览器订阅 `full.txt` 与 DNS/hosts/连接层规则集同时漏拦**。

**修复方案**：

1. 重定义「整域全局例外」：额外要求选项名（去 `~` 前缀）**全部落在整域放行白名单**内：
   `{"all", "document", "doc", "important", "match-case"}`（空选项也算）。
   显式排除 `NON_BLOCKING_MODIFIERS`、`NAVIGATION_DOMAIN_MODIFIERS` 中的 `popup/popunder`、`SCOPED/RESOURCE/PARTY` 以及任何未知选项（fail-closed）。
2. `writer.py` 引入该常量并修改 `_is_global_domain_exception`；`arbitrate.py` 复用同一判定，不新增第二份逻辑。
3. 版本：递增 `CLASSIFIER_VERSION`（DNS 分级/仲裁语义变更）。
4. 基线：`tests/baseline/{m2,m3}` 需重生成（产物含 `arbitration.json`、`full.txt`、`*_domains.txt`）。
5. 测试：新增 `tests/test_arbitrate.py` 用例——
   - `@@||d^$generichide` **不**撤销 `||d^`；
   - `@@||d^$removeparam=x`、`@@||d^$csp=...` **不**撤销；
   - `@@||d^`、`@@||d^$document`、`@@||d^$all` **撤销**。
6. 验收：`ruff` 与 `pytest` 全绿；`dist/arbitration.json` 中「非阻断型例外胜出」计数归零；33 个域名重新出现在 `domains.txt`。

**风险**：收紧后，若用户用 `@@||d^$generichide` 表达 DNS 放行将不再生效，属正确行为（`$generichide` 不改变网络放行语义），需在 `docs/SYNTAX.md` 说明。

### C2 DNS / 连接层覆盖率缺口（P1，结构性）

**现象**：DNS、hosts、`domains`、连接层规则集同源，只包含「整域可表达」规则。大量真实拦截规则只对浏览器全量清单有效。

**证据**（`dist/adblock_collection_full.dns_safety.json`，`level=safe`）：

| 拒绝原因 | 条数 | 是否属于真实网络阻断 |
| :--- | ---: | :--- |
| `path_rule` | 51,253 | 是（路径级） |
| `untranslatable` | 11,913 | 部分是 |
| `scoped_modifier` | 9,239 | 是（作用域） |
| `resource_type_modifier` | 6,057 | 是（类型） |
| `party_modifier` | 1,882 | 是（1p/3p） |
| `regex_or_redirect_rule` | 1,333 | 部分是 |
| `unknown_modifier` | 719 | 待分类 |
| `match_method_modifier` | 29 | 是 |
| `non_blocking_modifier` | 5,364 | 否（不阻断） |
| `css_rule` / `script_rule` | 163,660 | 否（非网络层） |

即约 **82,425 条会阻断请求的网络规则不进 DNS 及连接层产物**，DNS 侧覆盖约 87%。

**方案 A（文档与可见性，低风险）**：在 README、`docs/OPS.md` 与 `manifest.json` 标注每个产物的「拦截覆盖面」，并给出 `by_reason` 的人类可读解释，避免用户把 DNS 清单当成全量清单。

**方案 B（新增连接层 URL 规则集，中风险，需评审）**：为 mihomo（`behavior: classical`）与 sing-box（`url_regex` 规则集）新增一个可选产物，把 `path_rule`、`regex_or_redirect_rule` 转成 URL 匹配规则，补齐 DNS 无法覆盖的路径级广告。前置约束：先验证两类内核对 `URL-REGEX` 规则集的支持与体积上限，再决定是否进入主构建；不得影响现有 `behavior: domain` 产物。

### C3 上游源失败与缓存回退（P2）

**现象**：单源失败会丢失该源规则。`sources_status.json` 记录 `failed_sources`，CI 容忍少量失败。

**方案**：保持容忍策略；在 `manifest.json`/README 暴露本次失败源与回退状态，让订阅者判断数据完整性。仅在失败源数达到阈值时阻断（沿用 `docs/OPS.md` 处置），不改变现有默认行为。

### C4 用户侧认知与文档（P2）

**现象**：用户导入 DNS 清单后浏览器测试站「0 拦截」。已确认两类原因：浏览器走 DoH 绕过本地 DNS；测试站大量用例是元素隐藏/脚本注入，DNS 层天然无法覆盖。

**方案**：README 增加「导入后为什么看不到拦截」FAQ 与两条自检：

```bash
# 是否真的经过本地 DNS（应返回 0.0.0.0 或 NXDOMAIN）
nslookup doubleclick.net <DNS地址>

# 浏览器扩展订阅应使用全量清单，DNS 端使用 _dns.txt 或 _domains.txt
```

## 3. 误拦（不该拦的拦了）

### C5 导航修饰整域放大（P1）

**现象**：`||d^$popup`、`||d^$document` 只针对打开页面动作，进入 DNS/连接层后被放大为整域拦截。

**证据**：`dist/adblock_collection_full_domains.txt` 中 **108 个域名仅由导航修饰放大**。抽样多为广告/追踪/跳转域（`adserving.unibet.com`、`display.intdmp.com`、`changelnow-io.us` 等），现阶段误伤面有限，但机制上仍是整域放大。

**方案**：为导航来源单独打标并在报告中计数（`dns_safety` 已有 `navigation_domain_modifier: 237`）；提供策略开关，允许用户选择是否把导航规则纳入 DNS；在 README 标注该部分为「降置信度整域拦截」。默认维持现状，仅增强可见性与可退出性。

### C6 上游整域误标与事后兜底（P1）

**现象**：上游 `||legit.com^` 会整域封锁正常站点；当前仅靠 `config/false_positives.yaml`（约 125 条 allow）事后拦截。

**方案**：
1. 扩充 allow/block 回归用例，覆盖本次发现的 33 个广告域与 108 个导航域，防止修复 C1 后回归；
2. 新增「新出现整域阻断」复核：结合 `dist/build_diff.txt` 的逐条新增与域名热度/公共后缀启发式，输出待人工确认清单；
3. 把 `block_missing` 从 WARNING 提升为可配置阻断项（默认仍 WARNING）。

### C7 `$important` 与例外优先级（P2，潜性）

**现象**：`arbitrate` 让普通 `@@` 例外胜过 `$important` 阻断；uBO 语义中 `$important` 阻断应胜过普通例外（例外需自身带 `$important`）。

**证据**：当前数据 0 命中，属潜性偏差。

**方案**：可选对齐——`$important` 整域阻断仅被带 `$important` 的整域全局例外抵消。改动会影响 `arbitration.json` 与基线，作为独立单元评审。

### C8 行内注释污染选项（P2）

**现象**：源中出现 `@@||milfzr.com^$generichide! url: https://...` 形态（DandelionSprout `clear_urls_uboified.txt` 折出的聚合列表）。行内 `!` 注释使 `_option_start` 的选项头校验失败，整段 `$…` 不被识别为选项段，该例外因此被解析成**无选项的整域放行**，撤销同域整域阻断（漏拦）；`classify_dns` 也因原始行尾含 `$…` 判为 `untranslatable`。

**方案**：解析阶段剥离选项段内的行内注释（未被引号/正则包裹的 `!`，其后为空白或行尾，起至行尾），并把选项头校验改为容忍该注释。版本：递增 `PARSER_VERSION`（1.9.0 → 1.9.1）。

## 4. 升级拆分与版本轴

| 单元 | 根因 | 主要文件 | 版本轴 | 依赖 | 是否动基线 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C1 修正整域全局例外 | 漏拦缺陷 | `writer.py`、`arbitrate.py`、`docs/SYNTAX.md` | `CLASSIFIER_VERSION` | 无 | 是 |
| C2A 覆盖率原因说明 | 漏拦结构 | `dns_policy.py`、`writer.py` | 无 | 无 | 否 |
| C2B 连接层 URL 规则集 | 漏拦结构 | `cli.py`、`writer.py`、`docs/OPS.md` | 新增产物 | 设计与评审 | 是 |
| C3 失败源可见性 | 漏拦 | `cli.py`、`manifest`/`README` | 无 | 无 | 否 |
| C4 FAQ 与自检 | 认知 | `README.md` | 无 | 无 | 否 |
| C5 导航域可见性 | 误拦 | `dns_policy.py`、`cli.py`、`writer.py`、`docs` | 无 | 无 | 否 |
| C6-1 回归清单扩充 | 误拦 | `config/false_positives.yaml` | 无 | C1 | 否 |
| C6-2 新增整域阻断复核 | 误拦 | `build_diff.py`、`cli.py` | 无 | C1 | 是（新产物已忽略） |
| C6-3 `block_missing` 可配置 | 误拦 | `regression.py`、`cli.py` | 无 | 无 | 否 |
| C7 `$important` 对齐 | 误拦/漏拦 | `arbitrate.py` | `CLASSIFIER_VERSION` | 独立评审 | 是 |
| C8 行内注释剥离 | 漏拦 | `rules.py` | `PARSER_VERSION` | 无 | 是 |
| U1/U2 未知修饰符可见性 | 漏拦 | `dns_policy.py`、`writer.py`、`build.yml` | 无（不改判定） | 见 §6 | 否 |
| U3 lint 门禁 / U4 README 类别表 / U6 版本边界 | 运维 / 展示 | `build.yml`、`stats_badge.py`、`ruff.toml` | 无 | 无 | 是（U4 README） |
| U5 manifest `sha256` | 产物 + 基线 | `writer.py`、`baseline.py` | 无（不改规则集合） | 无 | 是 |
| U7 上游新修饰符跟进 | 规则 / 分类 | `dns_policy.py` 各修饰符集合 | `CLASSIFIER_VERSION` | 上游变化触发 | 每次单独提交 |

## 5. 落地顺序与验收

1. **C1**（P0）：先加回归用例锁定 33 个域名，再改判定，重生成 `tests/baseline/{m2,m3}`，提交后跑 CI。
2. **C8 + U1/U2**（低风险，补齐可观测性）：行内注释剥离、未知修饰符明细与门禁。
3. **C6 + C3 + C4**（误拦兜底与用户文档）：扩充回归清单、失败源可见、FAQ。
4. **C5 + C2A**（可见性）：标注导航域、退出开关与覆盖率原因说明。
5. **C7**（需评审）：`$important` 语义对齐，单独递增 `CLASSIFIER_VERSION` 并重生成基线。
6. **U3–U6**（运维/展示/产物）：lint 门禁、README 类别表自动同步、版本边界、manifest `sha256`。
7. **C2B**（需评审，暂缓）：连接层 URL 规则集，扩大发布面，留待单独设计。

统一验收：

```bash
python3 -m ruff check .
python3 -m pytest -q
```

CI 通过标准沿用 `docs/UPGRADE_PROPOSAL.md` §5 末尾流程；C1 落地后重点核对 `dist/arbitration.json` 与 `dist/adblock_collection_full_domains.txt` 的差异。

## 6. 实施状态

| 单元 | 状态 | 说明 |
| :--- | :--- | :--- |
| C1 修正整域全局例外 | 已实施 | `writer._is_global_domain_exception` 收紧；新增 `DOMAIN_ALLOW_MODIFIERS`；`CLASSIFIER_VERSION` → 1.11.0；`tests/test_arbitrate.py` 增 7 例；基线夹具重生成 |
| C2A DNS 覆盖率原因说明 | 已实施 | `dns_policy.REASON_DESCRIPTIONS`；`dns_safety.json` 增 `by_reason_labels` 与 `navigation_eligible_rules`；`tests/test_collection.py` 覆盖 |
| C2B 连接层 URL 规则集 | 暂缓（需评审） | 新增 `url` 规则集产物，扩大发布面与运维成本，留待单独设计评审 |
| C3 失败源可见性 | 已实施 | `sources_status.json` 增 `complete`/`failed_sources`；`manifest.json` 顶层内嵌 `sources_status`；`stats` 保留顶层字段 |
| C4 README FAQ 与自检 | 见 README | 「导入后为什么看不到拦截」FAQ 与 DoH/清单类型自检；不改版本轴 |
| C5 导航域可见性与可退出 | 已实施 | `dns_policy` 增 `include_navigation_domains`（默认 True）；`cli` 增 `--[no-]navigation-domains`；报告增 `navigation_eligible_rules` |
| C6-1 回归清单扩充 | 已实施 | `config/false_positives.yaml` 的 `block` 增非阻断型例外域 33 个 + 导航放大域 108 个 |
| C6-2 新增整域阻断复核 | 已实施 | `build_diff.review_new_domains` 输出 `new_domain_review.json`（risk=critical/high/low，命中 allow 为 critical），CI 门禁不阻断 |
| C6-3 `block_missing` 可配置阻断 | 已实施 | `regression.load_regression_options` 读 `regression.block_missing_strict`（默认 False，只告警） |
| C7 `$important` 优先级对齐 | 已实施 | `arbitrate` 中 `$important` 整域阻断仅被 `$important` 整域例外抵消；`CLASSIFIER_VERSION` → 1.12.0；`tests/test_arbitrate.py` 覆盖 |
| C8 行内注释剥离 | 已实施 | `rules` 剥离选项段行内注释；`PARSER_VERSION` → 1.9.1；`tests/test_collection.py` 增 2 例 |
| U1 未知修饰符可见性 | 已实施 | `DnsVerdict.unknown_modifiers` + `dns_safety.json` 的 `unknown_modifiers` 明细；不改判定 |
| U2 未知修饰符门禁告警 | 已实施 | `build.yml` 只读告警步骤（单 token ≥50，`::warning::`），不阻断 |
| U3 本地名单 lint 门禁 | 已实施 | `build.yml` 在测试后运行 `python -m adblock_collection lint`（只读） |
| U4 README 类别订阅表自动同步 | 已实施 | `stats_badge` 增 `category-stats` 标记区与 `sync_category_table`，README 按 `by_category` 自动生成 |
| U5 manifest `sha256` | 已实施 | `writer._file_sha256` 分块哈希，`manifest.json` 每条目增 `sha256`；基线比对忽略该派生字段与内嵌时间戳 |
| U6 Python 版本边界 | 已实施 | 统一为 3.10：`ruff.toml` `target-version="py310"`、README 徽章 `Python-3.10+`，并修复由此暴露的 `B905`/`F821`/`FURB188` |
| U7 上游新修饰符跟进 | 持续 | CI U2 告警触发时，将新 token 归入 `dns_policy` 对应集合，递增 `CLASSIFIER_VERSION` 后单独提交 |

版本现状（工作区）：`PARSER_VERSION=1.9.1`、`NORMALIZER_VERSION=1.4.0`、`CLASSIFIER_VERSION=1.12.0`。

C1–U6 未提交前 `dist/` 仍是旧产物（`parser=1.9.0`、`classifier=1.10.0`、33 个阻断被误删、无 `unknown_modifiers`/`sources_status`/`sha256` 字段）；推送后由 CI 重建并自动提交 dist。
