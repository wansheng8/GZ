# 规则语法与产物升级建议报告

本报告基于对当前代码库的逐项自查（解析层、DNS 分级、lint、连接层算子、产物清单、CI 门禁），给出两类改进建议：

- **A. 过滤语法 / 解析覆盖**
- **B. 生成文件与内容**

每项均给出：现状、证据（含代码位置与复现命令）、根因、建议改动（含可直接落地的 diff 或配置）、影响面、兼容性与版本、风险与回滚、测试与验收。

## 0. 元信息与优先级

- 生成日期：2026-09-25
- 基线提交：`576373a chore: auto update filter lists [skip ci]`
- 版本常量（`adblock_collection/pipeline.py:47-49`）：`PARSER_VERSION=1.9.0`、`NORMALIZER_VERSION=1.4.0`、`CLASSIFIER_VERSION=1.9.0`
- 基线指标：`total_rules=799470`、`dns_domains=545800`、`browser_network=635403`、`cosmetic=164067`、`ubo_enhance=30721`；`dist/manifest.json` 共 82 个产物。
- 本地校验状态：`ruff` 全绿、`pytest` 293 passed。

| 编号 | 优先级 | 主题 | 类型 | 是否改产物内容 |
| :--- | :--- | :--- | :--- | :--- |
| A1 | P1 | lint 对合法选项误报（`reason` 等） | 代码 + 测试 | 仅 `*.dns_safety.json` 的 reason 计数 |
| A2 | P3 | 扩展 CSS 伪类 `:contains()` 未识别 | 代码 + 测试 | 是（分层变化） |
| A3 | P3 | 未知 `!#` 指令块体未排除 | 代码（需先核实） | 可能 |
| A4 | P3 | lint 中 `noopjs` 等死条目 | 代码清理 | 否 |
| B1 | P1 | manifest 缺体积/构建溯源字段 | 代码 + 测试基线 | 是（`manifest.json`） |
| B2 | P2 | Surge 缺 `DOMAIN-SET` 高效产物 + 接入片段缺失 | 代码 + 文档 | 是（新增文件） |
| B3 | P2 | manifest `name` 语义未说明 | 文档 | 否 |
| B4 | P2 | Surge/QuanX 分片缺分片指示 | 代码 | 是（分片注释） |
| B5 | P3 | 空 DNS 产物未标注 | 代码 | 是（manifest 字段） |
| B6 | P2 | `stats` 命令重写 manifest 会降级 | 代码 | 是（manifest） |
| — | 不建议 | sing-box 版本追到 4/5；生成 mrs/srs 二进制 | 维持现状 | 否 |

### 0.1 实施状态（2026-09-25 全部落地）

| 编号 | 状态 | 落地要点 |
| :--- | :--- | :--- |
| A1 | 已实施 | `dns_policy` 登记 `network`/`client`/`ctag`（作用域）与 `dnsrewrite`（非阻断）；`lint` 并入 `METADATA_OPTIONS`；`writer._is_global_domain_exception` 同步收紧（作用域例外不再当全局例外） |
| A2 | 已实施 | `PROCEDURAL_PSEUDOS` 补 `:contains(`；`CLASSIFIER_VERSION` → 1.10.0 |
| A3 | 不实施 | 复核 AdGuard 官方语法后确认：`!#safari_cb_affinity(<content_blockers>)` … `!#safari_cb_affinity` 只是给 Safari 内容拦截器标注亲和性分组，**块内是正常规则**（如 `@@\|\|example.org^`），排除块体会漏掉真实放行/拦截规则。维持现状：指令行按注释剔除，块内规则保留。补测试 `test_preprocess_safari_cb_affinity_keeps_body` 锁定该语义；`PARSER_VERSION` 保持 1.9.0 |
| A4 | 已实施 | 移除 `KNOWN_NETWORK_OPTIONS` 中永不匹配的 `noop*` 死条目 |
| B1 | 已实施 | `write_manifest` 增每文件 `bytes`、顶层 `versions`/`generated_at`；`baseline` 忽略 `manifest.json` 的 `generated_at`；重生成 m2/m3 基线。附带修复：`security/` 独立发行的 manifest 条目此前只写裸文件名（缺 `security/` 前缀），导致 `bytes` 无法解析，现按相对 manifest 的路径写入 |
| B2 | 已实施 | 新增 `adblock_surge_domain_set.txt` 与 manifest 条目；README / OPS 增各内核接入片段 |
| B3 | 已实施 | README / OPS 明确 `file` 唯一、`name` 仅为逻辑分组 |
| B4 | 已实施 | `split_text_list` 分片头追加 `# Part i/N`，并为指示行预留字节预算 |
| B5 | 已实施 | manifest 条目对 `rules == 0` 标注 `empty: true` |
| B6 | 已实施 | `stats_cmd` 按既有 manifest 的 `file` 合并，仅重算 `.txt` 的 `rules`，保留规则集条目与其它字段 |

实施后版本：`PARSER_VERSION=1.9.0`（A3 不实施）、`NORMALIZER_VERSION=1.4.0`、`CLASSIFIER_VERSION=1.10.0`。

> 后续 C/U 轮（`docs/BLOCKING_AUDIT.md`）继续推进至 `PARSER_VERSION=1.9.1`（C8 行内注释剥离）、`CLASSIFIER_VERSION=1.12.0`（C1 + C7），`NORMALIZER_VERSION` 不变。自本文件 §0.1 起，版本以该节行末与 `docs/BLOCKING_AUDIT.md` §6 为准。

补充完善（同一轮）：

- **README 规则类型表自动同步**：`stats_badge.sync_kind_table` 依据 `dist/adblock_collection_full.stats.json` 的 `by_kind` 重写 README 中 `kind-stats` 标记区间，表格数字不再随上游变化而漂移；移除 README 中写死的「约 24MB」。
- **CI 产物完整性门禁**：`build.yml` 健康检查新增 manifest `bytes` 自洽、`versions` 存在、Surge `DOMAIN-SET` 存在且 ≤ 1,000,000 且与 DNS 域名数一致。
- **DOMAIN-SET 上限告警**：`writer.write_surge_domain_set` 超过 `SURGE_DOMAIN_SET_MAX` 时记录 warning，便于本地构建提前发现。

## 1. 现状基线

### 1.1 关键模块职责

| 文件 | 职责 | 本次涉及 |
| :--- | :--- | :--- |
| `adblock_collection/rules.py` | 行解析、kind 判定、选项切分、分类、增强识别 | A2、A4 |
| `adblock_collection/dns_policy.py` | DNS 可表达性分级、修饰符白名单 | A1 |
| `adblock_collection/lint.py` | 语法/冲突/未知选项校验 | A1、A4 |
| `adblock_collection/preprocess.py` | `!#if`/`!#include` 预处理 | A3 |
| `adblock_collection/writer.py` | 所有产物写出、manifest、分片 | B1、B2、B4 |
| `adblock_collection/cli.py` | 构建编排、不变量、manifest 刷新 | B1、B5、B6 |
| `adblock_collection/baseline.py` | 字节基线比对（时间戳剔除） | B1 影响 |
| `adblock_collection/stats_badge.py` | README 徽章 / 规则类型表 / `stats.svg` 同步 | 本轮增强 |
| `tests/baseline/m2,m3/` | 字节基线 golden | B1 需重生成 |
| `.github/workflows/build.yml` | CI：ruff → pytest → build → 门禁 → 提交 dist | 全部 + 产物完整性门禁 |

### 1.2 DNS 分级与 fail-closed 现状

`dns_policy.classify_dns` 的判定顺序（`dns_policy.py:213-285`）：

1. 非 `network` / `css` / `scriptlet` → `REJECT`
2. `_REGEX_REDIRECT_MODIFIERS`（`regexp`/`redirect`/`redirect-rule`/`rewrite`）→ `REJECT`
3. `NON_BLOCKING_MODIFIERS` → `REJECT`（`non_blocking_modifier`）
4. `SCOPED_MODIFIERS` → `REJECT`（`scoped_modifier`）
5. `MATCH_METHOD_MODIFIERS`（`cname`）→ `REJECT`
6. `RESOURCE_TYPE_MODIFIERS` → `REJECT`
7. `PARTY_MODIFIERS` → `REJECT`
8. 含路径 → `REJECT`
9. 纯域名 / 仅整域语义 / 仅导航语义 → `SAFE`
10. 其余含选项者 → `REJECT`（`unknown_modifier`）

结论：**未知修饰符 fail-closed，无安全缺口**。A1 只影响 REJECT 的 reason 归类与 lint 提示，不改变可升级集合。

### 1.3 产物清单（`dist/manifest.json`，B2 后为 83 条；唯一 file 83 个）

| 产物 | 文件 | 大小 | 说明 |
| :--- | :--- | ---: | :--- |
| 完整版 | `adblock_collection_full.txt` | 25.10 MiB | >18 MiB，已有 `_include` 分片主链 |
| 网络层 | `adblock_collection_full_browser_network.txt` | — | kind=network |
| 元素层 | `adblock_collection_full_cosmetic.txt` | — | css/scriptlet/html/js |
| hosts | `adblock_collection_full_dns.txt` | 14.71 MiB | `0.0.0.0 domain` |
| hosts ipv6 | `adblock_collection_full_dns_ipv6.txt` | — | `:: domain` |
| domains | `adblock_collection_full_domains.txt` | 10.54 MiB | 纯域名 |
| DNS 等价 | `adblock_collection_full_dns_abp.txt` | — | `||domain^` |
| uBO 增强 | `adblock_collection_ubo_enhance.txt` | 3.01 MiB | 高级修饰符/scriptlet/HTML |
| DNS 白名单 | `dns_allow.txt` | ~0 | 自定义白名单整域例外 |
| mihomo | `rulesets/adblock_clash.yaml` | 14.67 MiB | `behavior: domain` |
| sing-box | `rulesets/adblock_singbox.json` | 12.11 MiB | `version: 3` |
| Surge | `rulesets/adblock_surge.list` | 21.34 MiB | + `_part01/_part02` |
| Surge DOMAIN-SET | `rulesets/adblock_surge_domain_set.txt` | 11.08 MiB | 前导点含子域；裸域名精确（B2 新增） |
| Quantumult X | `rulesets/adblock_quanx.list` | 21.34 MiB | + `_part01/_part02` |
| 类别拆分 | `adblock_collection_full_<cat>.{txt,_dns.txt,_domains.txt,_dns_ipv6.txt}` | — | 20 类 |
| 安全专项 | `security/` | — | malware/phishing/mining |
| 报告 | `manifest.json`、`build_report.json`、`sources_status.json`、`regression_report.json`、`*.stats.{txt,json}`、`*.dns_safety.json` | — | 校验/审计 |

### 1.4 已核对的上游语义（用于确认现状正确性）

- **mihomo**（`wiki.metacubex.one/en/handbook/syntax/`、`.../config/rule-providers/content/`）：
  - `+.baidu.com` 匹配 `tieba.baidu.com`、`123.tieba.baidu.com`、`baidu.com`（等价 `DOMAIN-SUFFIX`，含本体）。
  - 裸 `books.itunes.apple.com` 为精确匹配（等价 `DOMAIN`）。
  - → 与 `write_clash_ruleset`（`writer.py:315-338`）的 `+.domain` / 裸 `domain` 完全一致。
- **sing-box**（`sing-box.sagernet.org/configuration/rule-set/source-format/` 与 `.../rule-set/`）：
  - `version` 版本：1=1.8.0、2=1.10.0、3=1.11.0、4=1.13.0、5=1.14.0。
  - v3 之后新增的是 `network_type`、`network_interface_address`、`package_name_regex` 等**路由匹配项**，与纯域名规则集无关。
  - 远程规则集 `format` 支持 `source`/`binary`，且 `.json` 扩展名可自动推断为 `source`。
  - → 当前 `{"version": 3, "rules": [...]}` 正确且兼容面最广。
- **Surge**（`manual.nssurge.com/rules/domain.html`）：
  - `DOMAIN-SET` 专为超大 adblock 列表设计，单集上限 1,000,000 条，预建索引快速查找。
  - 文件格式：裸行 `example.com` = 精确；前导点 `.ads.example.org` = 本体 + 全部子域。
  - `DOMAIN-SUFFIX,example.com,Proxy` 本体 + 子域；`RULE-SET,<url>,<policy>` 引用外部规则包。
  - 同一 URL 不能同时作为 `RULE-SET` 与 `DOMAIN-SET`。

## 2. A 语法 / 解析层建议

### A1（P1）lint 对合法选项误报

#### 现状

`lint._lint_line`（`lint.py:144-165`）对网络规则逐个选项调用 `_option_name`，若不在 `KNOWN_NETWORK_OPTIONS` 则报 warning。`KNOWN_NETWORK_OPTIONS`（`lint.py:37-60`）由 `dns_policy` 的各语义分组并集加一个手工集合构成，**未并入** `METADATA_OPTIONS`。

#### 证据

代码位置：

- `lint.py:37-60`：`KNOWN_NETWORK_OPTIONS` 组成
- `dns_policy.py:124`：`METADATA_OPTIONS = frozenset({"reason"})`
- `dns_policy.py:134-146`：`SCOPED_MODIFIERS`（缺 `network`/`client`/`ctag`）
- `dns_policy.py:127-129`：`_REGEX_REDIRECT_MODIFIERS`（缺 `dnsrewrite`）

复现命令与输出（已在本地执行）：

```bash
python3 -c "
from adblock_collection.lint import _lint_line
for line in ['||ads.example.com^\$reason=malicious','||ads.example.com^\$all,reason=x','||a.com^\$network=1.2.3.4','||a.com^\$client=1.2.3.4','||a.com^\$dnsrewrite=1.2.3.4','||a.com^\$ctag=c']:
    print(line)
    for i in _lint_line(line,1): print('   ',i.level,i.message)
"
```

输出：

```
||ads.example.com^$reason=malicious
    warning 未知选项名: reason（如为拼写错误请修正）
||ads.example.com^$all,reason=x
    warning 未知选项名: reason（如为拼写错误请修正）
||a.com^$network=1.2.3.4
    warning 未知选项名: network（如为拼写错误请修正）
||a.com^$client=1.2.3.4
    warning 未知选项名: client（如为拼写错误请修正）
||a.com^$dnsrewrite=1.2.3.4
    warning 未知选项名: dnsrewrite（如为拼写错误请修正）
||a.com^$ctag=c
    warning 未知选项名: ctag（如为拼写错误请修正）
```

DNS 分级复现：

```bash
python3 -c "
from adblock_collection.rules import parse_line
from adblock_collection.dns_policy import classify_dns
for line in ['||a.com^\$network=1.2.3.4','||a.com^\$client=1.2.3.4','||a.com^\$dnsrewrite=1.2.3.4','||a.com^\$ctag=c']:
    r=parse_line(line); v=classify_dns(r)
    print(line,'->',v.eligibility,v.reason)
"
```

输出：

```
||a.com^$network=1.2.3.4 -> REJECT unknown_modifier
||a.com^$client=1.2.3.4 -> REJECT unknown_modifier
||a.com^$dnsrewrite=1.2.3.4 -> REJECT unknown_modifier
||a.com^$ctag=c -> REJECT unknown_modifier
```

#### 根因

1. `$reason` 是注解选项，语义等价于无选项，但 `KNOWN_NETWORK_OPTIONS` 未包含 `METADATA_OPTIONS`，故误报。
2. `$network`（按 IP / 网络环境限定）在 `docs/SYNTAX.md` §4 已列为作用域型，但 `SCOPED_MODIFIERS` 未登记；因 fail-closed 仍被拒绝，但 reason 落到 `unknown_modifier`，审计报告不精确。
3. `$client` / `$ctag`（AdGuard：按客户端 / 分类标签限定）与 `$dnsrewrite`（AdGuard：改写 DNS 响应）是合法修饰符，未登记。

#### 建议改动

`adblock_collection/dns_policy.py`：

```python
# 作用域限定选项：新增 AdGuard 客户端/网络/分类标签限定
SCOPED_MODIFIERS = frozenset(
    {
        "domain",
        "from",
        "to",
        "top",
        "denyallow",
        "ipaddress",
        "method",
        "app",
        "dnstype",
        # AdGuard：按客户端 IP / 网络环境 / 分类标签限定，DNS 层无法表达来源范围
        "network",
        "client",
        "ctag",
    }
)

# 非阻断动作型：新增 AdGuard DNS 响应改写
NON_BLOCKING_MODIFIERS = frozenset(
    {
        # ... 既有项 ...
        # AdGuard：改写 DNS 解析结果，不构成整域拦截
        "dnsrewrite",
    }
)
```

`adblock_collection/lint.py`：

```python
from .dns_policy import (
    NAVIGATION_DOMAIN_MODIFIERS,
    NON_BLOCKING_MODIFIERS,
    PARTY_MODIFIERS,
    RESOURCE_TYPE_MODIFIERS,
    SCOPED_MODIFIERS,
    WHOLE_DOMAIN_MODIFIERS,
    METADATA_OPTIONS,          # 新增导入
    is_dns_eligible,
)

KNOWN_NETWORK_OPTIONS = frozenset(
    set(NON_BLOCKING_MODIFIERS)
    | set(SCOPED_MODIFIERS)
    | set(WHOLE_DOMAIN_MODIFIERS)
    | set(NAVIGATION_DOMAIN_MODIFIERS)
    | set(RESOURCE_TYPE_MODIFIERS)
    | set(PARTY_MODIFIERS)
    | set(UBO_ENHANCED_MODIFIERS)
    | set(METADATA_OPTIONS)    # 新增：reason=... 等注解
    | { "badfilter", "cname", "extension", "empty", "mp4", "noopjs",
        "noopcss", "noopframe", "noopmp4", "noopimage", "important",
        "match-case", "genericblock" }
)
```

同步更新 `docs/SYNTAX.md` §4：把 `$client`、`$ctag`、`$dnsrewrite` 纳入对应分组表格。

#### 影响面

- `lint` 输出：上述 6 类规则不再产生「未知选项」warning。
- `classify_dns` 的 reason：`$network/$client/$ctag` → `scoped_modifier`；`$dnsrewrite` → `non_blocking_modifier`；`$reason` 随注解忽略。
- **`dist/*.dns_safety.json` 的 `by_reason` 计数会变化**（`unknown_modifier` 拆分到 `scoped_modifier`/`non_blocking_modifier`），由 CI 重新构建并提交；`dns_eligible_network_rules` / `dns_rejected_network_rules` 不变。
- 域名集合、hosts/domains/rulesets 产物 **不变**。

#### 兼容性与版本

- 不需要递增 `PARSER_VERSION` / `NORMALIZER_VERSION`（解析结果不变）。
- 若团队要求 `*_dns_safety.json` 变更也纳入版本追踪，可递增 `CLASSIFIER_VERSION`；因其只改 reason 文本，建议不递增。
- **字节基线影响**：`tests/baseline/m2,m3` 的 fixture 规则不含 `$reason/$network/$client/$ctag/$dnsrewrite`，故 `test_baseline.py` 不受影响；真实数据侧由 CI 刷新 `dist`。

#### 风险与回滚

- 风险极低：仅收窄 warning、细化 reason，不改变任何产物域名。
- 回滚：还原上述常量即可。

#### 测试与验收

新增/补充测试：

- `tests/test_dns_policy`（若无则新增）：断言上述规则 `eligibility == REJECT`，且 reason 分别为 `scoped_modifier` / `non_blocking_modifier`。
- lint 测试：断言 `$reason=...`、`$network=...` 等不再产生 warning。
- 复跑 `python3 -m ruff check . && python3 -m pytest -q`。

验收命令：

```bash
python3 -c "from adblock_collection.lint import _lint_line; assert _lint_line('||a.com^\$reason=x',1)==[]; print('ok')"
```

### A2（P3）扩展 CSS 伪类 `:contains()` 未识别

#### 现状

`rules.PROCEDURAL_PSEUDOS`（`rules.py:369-392`）覆盖 `:remove()`、`:has-text()`、`:matches-*`、`:style()` 等，但未含 AdGuard 旧扩展选择器 `:contains(`（ABP 对应 `:-abp-contains()`）。

#### 证据

```bash
python3 -c "
from adblock_collection.rules import parse_line, is_ubo_only_cosmetic
r=parse_line('example.com##.ad:contains(Sponsored)')
print(r.kind, is_ubo_only_cosmetic(r))
"
```

预期输出 `css False`：被当作普通 CSS 规则，进入 ABP 通用层而非 uBO 增强层。

#### 建议改动

`adblock_collection/rules.py`：

```python
PROCEDURAL_PSEUDOS = (
    ":remove()",
    ":remove-attr(",
    ":remove-class(",
    ":has-text(",
    ":contains(",          # 新增：AdGuard 旧扩展选择器
    # ... 其余不变 ...
)
```

#### 影响面

- 含 `:contains(` 的规则从「通用元素隐藏层」迁到「uBO 增强层」，`adblock_collection_full_cosmetic.txt`、`adblock_collection_full.txt`、`_ubo_enhance.txt` 与 `manifest` 计数变化。
- 需递增 `CLASSIFIER_VERSION`（分类归属变化）。

#### 风险与回滚

- 需先统计上游命中量；命中量极低时收益有限，可不做。
- 回滚：移除该伪类。

#### 测试与验收

- 新增测试断言 `example.com##.ad:contains(x)` 的 `is_ubo_only_cosmetic` 为 `True`。
- 重新生成受影响的 `tests/baseline`，`pytest` 通过。

### A3（P3）未知 `!#` 指令块体未排除

> **复核结论（2026-09-25）：不实施。** AdGuard 官方语法为 `!#safari_cb_affinity(<content_blockers>)` … `!#safari_cb_affinity`（结束为裸指令），块内是**正常规则**（如 `@@||example.org^`、`example.org#@#.adBanner`），只是被标注归入哪些 Safari 内容拦截器。排除块体会丢掉真实的放行/拦截规则。正确行为是：指令行按注释剔除、块内规则保留（即当前实现）。本节的 `(block)/(unblock)` 假设不成立，仅作历史记录保留；现状与测试见 §0.1 与 `tests/test_preprocess.py::test_preprocess_safari_cb_affinity_keeps_body`。

#### 现状

`preprocess.preprocess`（`preprocess.py:174-225`）只识别 `if`/`else`/`endif`/`include`；其它 `!#` 指令在 `preprocess.py:225` 按注释忽略，但**不改变 `stack`**，因此其后的规则行仍处于 `active()` 状态被原样保留。

#### 证据

```bash
sed -n '174,229p' adblock_collection/preprocess.py
```

关键行：

```python
elif name == "include":
    ...
# 其它 !# 指令（如 !#endif 缺失、未知指令）按注释忽略
```

AdGuard 有一个块指令 `!#safari_cb_affinity(block)` / `(unblock)`（Safari 内容拦截器亲和块）。`_match_directive`（`preprocess.py:140-146`）按第一个空格切分 name/arg，`safari_cb_affinity(block)` 无空格 → name 为该整串，命中「未知指令」分支被忽略，块内规则被无条件纳入。

#### 证据（当前源样本）

```bash
rg -o '^\s*!#[A-Za-z_][A-Za-z0-9_]*' .cache/sources | sed 's/.*!#//' | sort | uniq -c | sort -rn
```

本地 `.cache/sources`（仅 5 个文件）只出现 `include`/`if`/`endif`，**未观测到**该指令。需在完整 60 源上统计。

#### 建议改动（确认存在后再实施）

在 `preprocess` 中为已知「块指令」维护一个 `_BLOCK_DIRECTIVES` 映射（如 `safari_cb_affinity`），`(block)` 入栈 False、`(unblock)` 出栈，语义与 `!#if` 一致（保守排除）。

#### 影响面

- 若上游确有该块，块内规则被正确排除；否则无变化。
- 需先量化命中量，避免为未使用的语法增加复杂度。

#### 风险与回滚

- 主要是「是否需要做」的问题，而非正确性风险。
- 回滚：移除块指令处理。

#### 测试与验收

- 构造含 `!#safari_cb_affinity(block) ... !#safari_cb_affinity(unblock)` 的样例，断言块内规则不进入输出。
- 在完整源统计命中量后决定是否排期。

### A4（P3）lint 中的死条目

#### 现状

`KNOWN_NETWORK_OPTIONS`（`lint.py:45-59`）含 `noopjs`、`noopcss`、`noopframe`、`noopmp4`、`noopimage`。但 `_option_name`（`lint.py:111-112`）取 `=` 前的部分，而 `$redirect=noopjs` 的 name 是 `redirect`，这些取值永远不会被匹配。

#### 证据

```bash
python3 -c "
from adblock_collection.lint import _option_name
print(_option_name('redirect=noopjs'))  # -> redirect
print(_option_name('noopjs'))           # -> noopjs，仅当规则误写裸 noopjs 才命中
"
```

#### 建议改动

方案一（清理）：从 `KNOWN_NETWORK_OPTIONS` 移除 5 个 `noop*`。
方案二（增强）：保留并把 `$redirect`/`$rewrite` 的取值校验为白名单（`noopjs`/`noopcss`/`noopmp4`/`noopimage`/`noopframe`/`nooptext` 或 `noop*.js` 资源名），对非法取值给 warning。

#### 影响面

- 方案一：无产物影响，仅去除永不触发的常量。
- 方案二：`lint` 对 `$redirect` 取值新增校验，可能新增 warning。

#### 风险与回滚

- 极低。

#### 测试与验收

- 方案二需补 `$redirect=noopjs`（通过）与 `$redirect=not-a-resource`（warning）用例。

## 3. B 生成文件与内容建议

### B1（P1）manifest 增加体积与构建溯源字段

#### 现状

`write_manifest`（`writer.py:477-484`）：

```python
def write_manifest(entries: list[dict], output_dir: Path) -> None:
    payload = {
        "generator": "adblock-rule-collection",
        "generated_files": entries,
    }
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

条目键仅 `file`/`format`/`name`/`parts`/`rules`/`source`，无字节数、无生成时间、无版本、无内容校验。

调用点：`cli.py:921`（build）与 `cli.py:1064`（`stats` 命令，见 B6）。

#### 证据

```bash
python3 -c "
import json
m=json.load(open('dist/manifest.json'))
print('top:', list(m))
print('entry keys:', sorted({k for g in m['generated_files'] for k in g}))
"
```

输出：

```
top: ['generator', 'generated_files']
entry keys: ['file', 'format', 'name', 'parts', 'rules', 'source']
```

#### 建议改动

`adblock_collection/writer.py`：

```python
from datetime import datetime, timezone

def write_manifest(
    entries: list[dict],
    output_dir: Path,
    *,
    versions: dict | None = None,
    generated_at: str | None = None,
) -> None:
    for entry in entries:
        path = output_dir / entry["file"]
        if path.exists():
            entry.setdefault("bytes", path.stat().st_size)
    payload = {
        "generator": "adblock-rule-collection",
        "generated_files": entries,
    }
    if versions:
        payload["versions"] = versions
    if generated_at:
        payload["generated_at"] = generated_at
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

`adblock_collection/cli.py:921`（build 路径）注入版本与时间：

```python
from .pipeline import PARSER_VERSION, NORMALIZER_VERSION, CLASSIFIER_VERSION
import os
from datetime import datetime, timezone

write_manifest(
    manifest,
    output_dir,
    versions={
        "parser": PARSER_VERSION,
        "normalizer": NORMALIZER_VERSION,
        "classifier": CLASSIFIER_VERSION,
    },
    generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
)
```

`adblock_collection/baseline.py`（保持基线可比）：

```python
_TIMESTAMP_KEYS: dict[str, tuple[str, ...]] = {
    "sources_status.json": ("generated_at",),
    "manifest.json": ("generated_at",),   # 新增，避免时间戳导致基线抖动
}
```

#### 影响面

- `dist/manifest.json` 新增 `versions`、`generated_at` 与每文件 `bytes`。
- 订阅端可用 `bytes` 做预校验/缓存判断；审计可追溯解析/分类版本与时间。
- `stats` 命令调用点不传 `versions`/`generated_at`，仍会补 `bytes`（向后兼容）。

#### 兼容性与版本

- 新增字段，向后兼容；旧消费者按固定键读取不受影响。
- **必须同步**：
  1. `baseline._TIMESTAMP_KEYS` 增加 `manifest.json` 的 `generated_at`，否则 `test_baseline.py` 会因时间戳抖动。
  2. `bytes` 为确定性字段，需**重生成 `tests/baseline/m2/manifest.json` 与 `tests/baseline/m3/manifest.json`**，否则 `test_baseline.py` 报字节差异。
- 是否递增版本常量：建议不递增（规则集合不变），由 `versions` 字段自描述。

#### 风险与回滚

- 风险：若忘记重生成基线，CI 的 pytest 步骤会失败（可及时发现）。
- 回滚：移除新增字段与基线改动。

#### 测试与验收

- 重生成基线：`python3 -m pytest tests/test_baseline.py -q` 通过。
- 断言 `manifest.json` 含 `versions.{parser,normalizer,classifier}`、`generated_at`，且每个条目的 `bytes` 与文件实际大小一致。

### B2（P2）Surge 缺 `DOMAIN-SET` 高效产物 + 客户端接入片段缺失

#### 现状

`write_surge_ruleset`（`writer.py:363-379`）输出 `DOMAIN-SUFFIX,<d>,REJECT` / `DOMAIN,<d>,REJECT` 逐行规则，21.34 MiB，已拆 `_part01/_part02`。`docs/OPS.md`/README 未给出四种内核的可粘贴接入配置。

#### 证据

```bash
python3 - <<'PY'
import os
suffix=[];exact=[]
for ln in open('dist/rulesets/adblock_clash.yaml',encoding='utf-8'):
    s=ln.strip()
    if s.startswith("- '+."): suffix.append(s[5:-1])
    elif s.startswith("- '") and s.endswith("'"): exact.append(s[3:-1])
size=sum(len('.'+d)+1 for d in suffix)+sum(len(d)+1 for d in exact)
print('suffix',len(suffix),'exact',len(exact))
print(f'DOMAIN-SET 估算 {size/1048576:.2f} MiB；当前 RULE-SET {os.path.getsize("dist/rulesets/adblock_surge.list")/1048576:.2f} MiB')
PY
```

输出：

```
suffix 525999 exact 19801
DOMAIN-SET 估算 11.05 MiB；当前 RULE-SET 21.34 MiB
```

Surge 官方（`manual.nssurge.com/rules/domain.html`）明确：`DOMAIN-SET` 单集上限 1,000,000 条、预建索引；裸行=精确、前导点=本体+子域。**与本项目的 suffix/exact 拆分天然对齐**。

#### 建议改动

1. 新增 Surge `DOMAIN-SET` 产物（域名行，无需逐行策略），估算 11.05 MiB，预计**不触发 18 MiB 分片**：

```python
def write_surge_domain_set(
    domains: Iterable[str], path: Path, title: str,
    exact_domains: Iterable[str] | None = None,
) -> int:
    """Surge DOMAIN-SET：前导点=本体+子域，裸域名=精确。"""
    suffix = sorted(domains)
    exact = sorted(exact_domains or ())
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n")
        fh.write(f"# DOMAIN-SET,<url>,REJECT\n# Total Domains: {len(suffix)+len(exact)}\n")
        for d in suffix:
            fh.write(f".{d}\n")
        for d in exact:
            fh.write(f"{d}\n")
    return len(suffix) + len(exact)
```

在 `write_rulesets`（`writer.py:439`）内与其它三份一起写出并登记 manifest（`format: "surge_domain_set"`）。保留现有 `RULE-SET` 产物以兼容旧订阅（或逐步弃用）。

2. 在 `docs/OPS.md` 增加各内核最小接入片段：

mihomo（Clash Meta）：

```yaml
rule-providers:
  adblock:
    type: http
    behavior: domain
    format: yaml
    interval: 86400
    url: "https://cdn.jsdelivr.net/gh/<owner>/<repo>@main/dist/rulesets/adblock_clash.yaml"
    path: ./ruleset/adblock_clash.yaml
rules:
  - RULE-SET,adblock,REJECT
```

sing-box（1.11+，远程 `source` 无需编译；也可本地 `sing-box rule-set compile` 后用 `binary`）：

```json
{
  "route": {
    "rule_set": [
      {
        "tag": "adblock",
        "type": "remote",
        "format": "source",
        "url": "https://cdn.jsdelivr.net/gh/<owner>/<repo>@main/dist/rulesets/adblock_singbox.json",
        "update_interval": "1d"
      }
    ],
    "rules": [
      { "rule_set": "adblock", "action": "reject" }
    ]
  }
}
```

Surge：

```
DOMAIN-SET,https://cdn.jsdelivr.net/gh/<owner>/<repo>@main/dist/rulesets/adblock_surge_domain_set.txt,REJECT
# 或（逐行规则包）：
RULE-SET,https://cdn.jsdelivr.net/gh/<owner>/<repo>@main/dist/rulesets/adblock_surge.list,REJECT
```

Quantumult X：

```ini
[filter_remote]
https://cdn.jsdelivr.net/gh/<owner>/<repo>@main/dist/rulesets/adblock_quanx.list, tag=adblock, force-policy=reject, enabled=true
```

> 注：现有 `adblock_surge.list` 每行含第三列 `,REJECT`，作为独立规则包应经 `RULE-SET` 引用；Surge 外部 `RULE-SET` 文件是否接受行内策略需实测。`DOMAIN-SET` 是本项目大规模域名集的更优路径。

#### 影响面

- 新增 1 个产物文件（manifest 81→83 或按实现）。
- 若把该文件加入 `tests/baseline` 比对，需重生成基线；否则 `compare_baseline` 会因「新文件缺失于 golden」判失败。建议同步更新 `tests/baseline/m2,m3`。

#### 兼容性与版本

- 新增产物，不影响既有产物内容；建议递增 `PARSER_VERSION`/`NORMALIZER_VERSION` 无必要，仅 `writer` 层新增输出。
- manifest 新增条目，B1/B3 的说明需同步。

#### 风险与回滚

- 风险：新文件的 JSON/YAML 转义（域名均为 ASCII，无风险）；分片逻辑需确认新文件 <18 MiB（估算 11.05 MiB）。
- 回滚：移除新 writer 与 manifest 条目。

#### 测试与验收

- `tests/test_rulesets.py` 增加断言：DOMAIN-SET 的前导点/裸域名正确；`suffix + exact` 等于 `dns_domains`。
- 校验体积 < `JSDELIVR_MAX_BYTES`，不产生 `_part`。

### B3（P2）manifest `name` 语义未说明

#### 现状

`name` 是逻辑分组名，非唯一；`file` 才唯一。

#### 证据

```bash
python3 -c "
import json,collections
m=json.load(open('dist/manifest.json'))
names=collections.Counter(g['name'] for g in m['generated_files'])
print({k:v for k,v in names.items() if v>1})
print('files',len(m['generated_files']),'unique',len({g['file'] for g in m['generated_files']}))
"
```

输出（节选）：

```
{'adblock_collection_full': 5, 'ruleset_surge_part': 2, 'ruleset_quanx_part': 2,
 'adblock_collection_full_annoyance': 4, ... }
files 82 unique 82
```

#### 建议改动

在 `docs/OPS.md` / README 的 manifest 说明中明确：**`file` 是唯一键，`name` 仅为逻辑分组**。可选：为每个条目增加稳定 `id`（如 `f"{name}:{format}"`）供程序化引用。

#### 影响面

- 纯文档（或新增 `id` 字段，兼容）。

#### 风险与回滚

- 无。

#### 测试与验收

- 文档评审通过即可。

### B4（P2）Surge/QuanX 分片缺分片指示

#### 现状

`split_text_list`（`writer.py:401-436`）把注释头复制到每个分片，但分片自身不标注 `part i/N`，也不列出同组其它分片；`manifest.parts` 中才有列表，而订阅端通常只拿到单个文件。

#### 证据

```bash
head -3 dist/rulesets/adblock_surge_part01.list
```

分片头与主文件头相同，无分片序号信息。

#### 建议改动

`writer.py:427-435` 写出每片时追加分片指示：

```python
for index, chunk in enumerate(chunks, 1):
    name = f"{path.stem}_part{index:02d}{path.suffix}"
    with path.with_name(name).open("w", encoding="utf-8") as fh:
        for ln in header:
            fh.write(ln + "\n")
        fh.write(f"# Part {index}/{len(chunks)}: {name}\n")
        if len(chunks) > 1:
            others = ", ".join(
                f"{path.stem}_part{j:02d}{path.suffix}"
                for j in range(1, len(chunks) + 1)
            )
            fh.write(f"# All parts: {others}\n")
        for ln in chunk:
            fh.write(ln + "\n")
    names.append(name)
```

#### 影响面

- 分片文件内容变化，需重生成 `tests/baseline/m2,m3/rulesets/adblock_{surge,quanx}_part*.list`（若在基线内）。当前基线 m2/m3 的 rulesets 目录含 `adblock_surge.list`/`adblock_quanx.list`，需确认 fixture 是否触发分片；未触发则无需改。

#### 兼容性与版本

- 注释行被引擎忽略，不影响匹配语义。

#### 风险与回滚

- 极低。

#### 测试与验收

- 构造超限文本，断言每个分片含 `# Part i/N`。

### B5（P3）空 DNS 产物未标注

#### 现状

类别拆分按类别无条件产出 `_dns.txt`/`_domains.txt`/`_dns_ipv6.txt`。对 `whitelist`、`css`、`scriptlet` 等类别，这些文件基本为空，但仍出现在 manifest 中易造成困惑。

#### 证据

```bash
for f in dist/adblock_collection_full_{whitelist,css,scriptlet}_dns.txt; do
  printf '%s %s\n' "$f" "$(wc -l < "$f")"
done
```

#### 建议改动

在 manifest 条目中写入 `rules`（已有）并增加 `empty: true` 语义；或在文档说明「空文件表示该类别无 DNS 可表达规则」。**不要直接跳过空文件**，因为 `_check_category_invariant`（`cli.py:439-465`）按类别子列表并集计算，跳过会改变不变量判定逻辑，需一并调整。

#### 影响面

- manifest 新增 `empty` 字段；文件集合不变。

#### 风险与回滚

- 低。回滚：移除字段。

#### 测试与验收

- 断言空文件的 manifest 条目 `rules == 0` 且 `empty is True`。

### B6（P2）`stats` 命令重写 manifest 会降级

#### 现状

`stats_cmd`（`cli.py:1033-1065`）基于已有 dist 重新生成 manifest：

```python
manifest = []
for txt in sorted(output_dir.glob("*.txt")):
    ...
    manifest.append(
        {"name": txt.stem, "file": txt.name, "format": "auto", "rules": rule_count}
    )
write_manifest(manifest, output_dir)
```

它只 glob `*.txt`，不包含 `rulesets/*.yaml|json`，且 `name=txt.stem`、`format="auto"`，丢弃 build 生成的 `parts`/`source` 与规则集条目。

#### 证据

```bash
python3 - <<'PY'
import glob, os, json
m=json.load(open('dist/manifest.json'))
print('build manifest entries:', len(m['generated_files']))
txts=[f for f in glob.glob('dist/*.txt') if not f.endswith('.stats.txt')]
print('stats glob *.txt entries:', len(txts), '(含 rulesets 目录? 否)')
print('rulesets:', sorted(os.path.basename(p) for p in glob.glob('dist/rulesets/*')))
PY
```

输出：

```
build manifest entries: 82
stats glob *.txt entries: 72 (含 rulesets 目录? 否)
rulesets: ['adblock_clash.yaml','adblock_quanx.list','adblock_quanx_part01.list','adblock_quanx_part02.list','adblock_singbox.json','adblock_surge.list','adblock_surge_part01.list','adblock_surge_part02.list']
```

即运行一次 `stats` 会把 82 条的富 manifest 覆盖为 72 条「降级」manifest，丢失所有连接层规则集条目与 `parts`/`source`/`format` 细节。

#### 建议改动

任选其一：

- 方案 A（推荐）：`stats_cmd` 同时 glob `rulesets/*`（`.yaml/.json/.list`），并复用 build 侧的 `name/format/source/parts` 约定；或
- 方案 B：`stats_cmd` 改为「按 `file` 合并」——读取既有 manifest，仅刷新 `rules` 字段，保留其它字段与规则集条目；或
- 方案 C：文档明确 `stats` 仅用于无规则集的临时目录，勿在发布 dist 上运行。

#### 影响面

- 方案 A/B 修正后，`stats` 与 `build` 产出的 manifest 语义一致，避免审计/订阅端字段缺失。

#### 兼容性与版本

- 方案 B 最稳（不丢字段）。需注意 `stats` 无法恢复 `source`（文档已注明）。

#### 风险与回滚

- 低。

#### 测试与验收

- 新增测试：构造含 `rulesets/` 的 dist，运行 `stats`，断言 manifest 仍包含规则集条目且字段结构不变。

## 4. 明确不建议做的

### 4.1 不把 sing-box 规则集版本追到 4/5

官方版本历史：3=1.11.0、4=1.13.0、5=1.14.0。v4/v5 新增的是 `network_interface_address`、`package_name_regex` 等路由匹配项，本项目的纯域名规则集用不到；维持 `version: 3` 可兼容更多客户端。

### 4.2 不生成 `.mrs`/`.srs` 二进制

需要 mihomo / sing-box 外部工具链，纯 Python 构建流程无法生成。若未来需要，应作为独立 CI 步骤（联网安装工具），不进入主构建。

### 4.3 不改动已确认忠实的算子语义

mihomo `+.domain`/裸域名、sing-box `domain_suffix`/`domain`、Surge `DOMAIN-SUFFIX`/`DOMAIN`、QuanX `host-suffix`/`host` 与官方语义一致，无需调整。

## 5. 建议落地顺序与验收

1. **A1 + 测试**（P1，低风险）：lint 误报收窄、DNS reason 更准；不影响域名集合。
2. **B1**（P1）：manifest 体积/溯源字段；同步 `baseline._TIMESTAMP_KEYS` 并重生成 m2/m3 manifest 基线。
3. **B2 + B6**（P2）：新增 Surge `DOMAIN-SET` 产物与接入文档；修复 `stats` 的 manifest 降级。
4. **B3 + B4**（P2）：manifest `name` 语义说明；分片指示。
5. **A2/A3/A4/B5**（P3）：按上游命中量与排期决定。

统一验收：

```bash
python3 -m ruff check .
python3 -m pytest -q          # 期望 293+ passed
```

CI：推送后约 7–9 分钟完成，成功后 bot 自动提交 `dist`（`[skip ci]`）。校验用 `git fetch origin && git log --oneline -2 origin/main`，构建健康看 `dist/build_report.json` 的 `passed` 与 `metrics`。

## 6. 后续升级拆分（独立发布单元）

第 5 节是已落地内容的顺序；本节把后续建议拆成**可独立提交、独立回滚**的升级单元。核心约束：一个单元只触碰**一条版本轴**，产物层 / 门禁层 / 文档层不改版本轴；触碰规则集合的单元必须单独提交，避免与其它单元混提后无法归因。

### 6.1 三层版本轴与职责

`adblock_collection/pipeline.py` 的三个常量分别对应三层，语义变化时才递增：

| 版本常量 | 归属层 | 递增时机 | 副作用 |
| :--- | :--- | :--- | :--- |
| `PARSER_VERSION` | 规则 / 语法解析、`!#` 预处理 | 规则文本解析结果变化（如 A2 的 `:contains()`） | `.cache/parsed` 失效重建 |
| `NORMALIZER_VERSION` | 处理 / 规范化、去重、别名、合并 | 规范化或去重结果变化（域名集合改变） | 产物规则集合变化 |
| `CLASSIFIER_VERSION` | 分类 / DNS 判定 / lint 语义 | 分类或 DNS 分级结果变化（如 A1） | 分类缓存失效 |

### 6.2 独立升级单元

| 单元 | 层 | 主要文件 | 版本轴 | 产物变化 | 可独立发布 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| U1 未知修饰符可见性 | 分类 + 处理 | `dns_policy.py`、`writer.py`、`docs/SYNTAX.md` | 无（只增可观测字段） | `*.dns_safety.json` 增 `unknown_modifiers` | 是 |
| U2 未知修饰符门禁告警 | CI / 门禁 | `.github/workflows/build.yml` | 无 | 无（只读报告） | 依赖 U1 |
| U3 本地名单 lint 门禁 | CI / 门禁 | `.github/workflows/build.yml` | 无 | 无 | 是 |
| U4 README 类别订阅表自动同步 | 统计 / 展示 | `stats_badge.py`、`README.md`、`tests/test_stats_badge.py` | 无 | 仅 `README.md` | 是 |
| U5 manifest `sha256` | 产物 + 基线 | `writer.py`、`tests/baseline/{m2,m3}/manifest.json`、`docs/OPS.md` | 无（不改规则集合） | `manifest.json` 每条目增 `sha256` | 是 |
| U6 Python 版本边界 | 构建 / 环境 | `ruff.toml`、`README.md`、`.github/workflows/build.yml` | 无 | 无 | 是 |
| U7 上游新修饰符跟进（持续） | 规则 / 分类 | `dns_policy.py` 的 `WHOLE_DOMAIN_MODIFIERS` / `SCOPED_MODIFIERS` 等 | `CLASSIFIER_VERSION` | 域名集合可能变化 | 每次单独提交 |

> 实施状态（2026-09-25）：**U1–U6 已全部实施**（`unknown_modifiers` 明细 + CI 只读告警 + lint 门禁 + README 类别表自动同步 + manifest `sha256` + Python 3.10 边界），详见 `docs/BLOCKING_AUDIT.md` §6。U1 只新增可观测字段、不改变 DNS 判定，故未递增 `CLASSIFIER_VERSION`。**U7 为持续项**，由上游新修饰符触发。

### 6.3 每个单元的实施要点

**U1（未知修饰符可见性）**
`classify_dns` 的 `unknown_modifier` 分支返回时带出 `sem` 集合（`DnsVerdict.unknown_modifiers`）；`write_dns_safety_report` 聚合为 `unknown_modifiers: {token: count}`（按次数降序、名称升序）。只新增字段、不改判定结果，分类缓存与基线判定不变。

**U2（未知修饰符门禁）**
在 `build.yml` 的「Check build health」之后读取 `dist/adblock_collection_full.dns_safety.json`，对单一 token 超过阈值（50）以 `::warning::` annotation 提示，只告警不阻断。

**U3（本地名单 lint 门禁）**
`build.yml` 增加一步对 `config/lists/{blocklist,allowlist}.txt` 运行 lint 子命令。只读，秒级，完全独立。

**U4（README 类别表）**
复用 `stats_badge` 已有的 `kind-stats` 标记区与 `sync_kind_table` 模式，按分类计数生成完整类别表，替换 README 中写死的 8 类。

**U5（manifest sha256）**
对每个产物条目计算 SHA-256 写入 manifest；因 manifest 进入 `tests/baseline/{m2,m3}` 夹具，需在本单元内一并重生成基线。不影响 `PARSER/NORMALIZER/CLASSIFIER` 版本。

**U6（Python 版本边界）**
二选一：CI 加 3.8 矩阵验证，或把下限提到 3.10 并同步 `ruff.toml`、README。二选一即可，不要同时声称 3.8 与 3.10。

### 6.4 发布顺序与统一验收

1. **U1 → U2** 串行（U2 依赖 U1 的字段）。
2. **U3 / U4 / U6** 互相独立，可任意穿插。
3. **U5** 单独提交（触碰基线夹具，混提会导致 baseline 归因困难）。
4. **U7** 由上游变化触发，不与上述单元合并。

```bash
python3 -m ruff check .
python3 -m pytest -q
```

推送与 CI 校验沿用第 5 节末尾流程。

> 广告拦截正确性（漏拦/误拦）专项审计与 `C*` 修复单元见 `docs/BLOCKING_AUDIT.md`，与本节 `U*` 单元互补。
