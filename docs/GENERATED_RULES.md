# 生成产物语法与用法

本文件是 `adblock_collection` 构建产物的**语法规范**：每个文件里一行/一条长什么样、字段含义、以及该导到哪里用。

- 过滤规则本身的语义（`||`、`^`、`$` 修饰符、`##` 元素隐藏等）：见 `docs/SYNTAX.md`。
- 客户端订阅地址与配置示例：见 `README.md`「订阅中心」。
- 构建、配置、排障流程：见 `docs/OPS.md`；流水线阶段：见 `docs/FLOW.md`。
- 面向单个客户端的即用配置：见第 5 节 `adapters/`；订阅与一键导入地址：见 `README.md`「客户端适配产物」。

程序把 60+ 上游列表下载、预处理、合并、去重、分类后，统一输出到 `dist/`。同一个规则集合会派生出多种载体格式；所有文件由 `dist/manifest.json` 索引。

## 1. 命名规则

| 片段 | 含义 |
| :--- | :--- |
| `adblock_collection_full` | 完整版基础前缀 |
| `adblock_collection_full_<category>` | 按类别拆分的子列表（`network` / `privacy` / `phishing` / `url` / `scriptlet` / `whitelist` / `malware` / `annoyance` / `social` / `cookie` / `redirect` / `html` / `mining` / `js` / `css`） |
| `adblock_collection_full_browser_network` | 三层产物·扩展网络层 |
| `adblock_collection_full_cosmetic` | 三层产物·扩展元素隐藏层 |
| `adblock_collection_full_dns_abp` | 三层产物·DNS 等价域名层（`||domain^`） |
| `adblock_collection_ubo_enhance` | uBO/AdGuard 高级增强层（不参与类别并集） |
| `security/adblock_collection_security` | 安全专项（`malware`/`phishing`/`mining`）独立发行 |
| `rulesets/adblock_*` | 连接层规则集（mihomo / sing-box / Surge / Quantumult X） |

后缀决定语法载体：

| 后缀 | 语法 | 用例 |
| :--- | :--- | :--- |
| `.txt` | adblock（ABP/uBO/AdGuard） | 浏览器扩展、AdGuard Home 域名规则 |
| `_dns.txt` | hosts，IPv4 | Pi-hole / dnsmasq / 路由器 / 系统 hosts |
| `_dns_ipv6.txt` | hosts，IPv6 | 双栈 IPv6 兜底 |
| `_domains.txt` | 裸域名逐行 | AdGuard DNS / AdGuard Home 自定义黑名单 |
| `_dns_abp.txt` | `||domain^` | DNS 等价域名规则 |
| `_jsdelivr.txt` + `_jsdelivr_partNN.txt` | adblock 分片主链 | 超过 jsDelivr 单文件上限时 |
| `.stats.txt` / `.stats.json` | 统计 | 人读 / 程序读 |
| `.dns_safety.json` | DNS 分级审计 | 评估 DNS 覆盖面与误杀面 |

目录：`dist/`（主产物）、`dist/security/`（安全专项）、`dist/rulesets/`（连接层）。

## 2. adblock 列表语法（`.txt`）

每份列表第一块是固定头部，之后逐行是原始规则：

```text
[Adblock Plus 2.0]
! Title: Adblock Rule Collection (Full)
! Description: 完整版广告拦截与 DNS 过滤规则集合，含大量上游列表，可能有误杀。
! Expires: 1 day
! Homepage: https://github.com/wansheng8/GZ
! License: MIT
! Total Rules: 793579
! ------------------------------------------
live.bilibili.com##.live-room-app .ad-deck
||ads.example.com^
@@||cdn.example.com^$script
```

- `[Adblock Plus 2.0]` 是 ABP 识别过滤列表的前提，uBO/AdGuard 同样接受。
- `!` 开头是注释；`! Total Rules:` 为规则行数。
- 规则体不做改写，原样保留上游写法，常见形态见 `docs/SYNTAX.md`：网络阻断 `||domain^`、路径 `||domain/path/*`、例外 `@@||domain^`、元素隐藏 `domain##selector`、取消隐藏 `domain#@#selector`、scriptlet `##+js(...)`、HTML 过滤 `##^...`、过程式 `#?#...`。

### 2.1 jsDelivr 分片主链

当单文件超过 jsDelivr 上限（18 MiB 预算）时，除完整 `.txt` 外额外生成：

```text
[Adblock Plus 2.0]
! Title: ...（jsDelivr 分片主链）
...
!#include adblock_collection_full_jsdelivr_part01.txt
!#include adblock_collection_full_jsdelivr_part02.txt
```

uBO/AdGuard 会递归跟随相对路径的 `!#include`，订阅方只需订阅主链文件。GitHub 上仍保留完整单文件。Surge/Quantumult X 这类无 include 机制的逐行规则集改用 `_partNN` 分片，需把各分片全部加入。

## 3. DNS / hosts 系

四种产物同源（同一「应拦截纯域名」集合），只换载体。集合规则：只收录满足 DNS 安全分级的单域名网络阻断；`config/lists/allowlist.txt` 的整域全局例外从集合中剔除。

### 3.1 hosts（IPv4）`*_dns.txt`

```text
# Adblock Rule Collection (Full)
# Format: hosts (0.0.0.0 domain), total 539768
0.0.0.0 0--4.com
```

每行 `0.0.0.0 <domain>`，按域名升序。适配 Pi-hole、dnsmasq、路由器、系统 hosts。

### 3.2 hosts（IPv6）`*_dns_ipv6.txt`

```text
# Adblock Rule Collection (Full)
# Format: hosts (:: domain, IPv6 NXDOMAIN), total 539768
:: 0--4.com
```

每行 `:: <domain>`，给纯 IPv6 网络做兜底；与 IPv4 版本域名集合一致。

### 3.3 裸域名 `*_domains.txt`

```text
# Adblock Rule Collection (Full)
# Format: one domain per line (AdGuard DNS / AdGuard Home), total 539768
0--4.com
```

每行一个域名，适配 AdGuard Home 自定义黑名单、AdGuard DNS。这三种文本产物天然只匹配域名本体，不含子域。

### 3.4 DNS 等价域名规则 `*_dns_abp.txt`

```text
[Adblock Plus 2.0]
! Title: Adblock Rule Collection (DNS-domain rules)
! Description: DNS 等价域名阻断：整域 ||domain^ 纯域名规则，无修饰符，浏览器与 DNS 端均可导入
! Total Rules: 539768
! ------------------------------------------
||0--4.com^
```

同样带完整 adblock 头部，每行 `||domain^`，无任何 `$` 修饰符与元素隐藏规则。既可导入浏览器扩展补齐域名层，也可作为 AdGuard Home 的域名规则。

### 3.5 DNS 白名单 `dns_allow.txt`

```text
# Adblock Rule Collection (DNS allowlist)
# Format: DNS allowlist (AdGuard Home / Pi-hole), total 0
example.com
```

内容完全来自 `config/lists/allowlist.txt` 中的整域全局例外（`@@||example.com^` 或仅带 `$all`/`$document`/`$doc`/`$important`/`$match-case`）。供 AdGuard Home / Pi-hole 的「允许清单」分组导入。作用域/路径/导航/非阻断类局部例外不进此文件。

### 3.6 空产物

某类别没有 DNS 可表达规则时仍会生成文件（只有头部），并在 `manifest.json` 中标记 `"empty": true`。例如 `adblock_collection_full_css_dns.txt`。这是正常结果，不是缺漏。

## 4. 连接层规则集（`rulesets/`）

与 DNS 域名集合同源，并同样尊重 `config/lists/allowlist.txt`。TUN 模式下内核按 TLS/QUIC SNI 匹配域名，可穿透 App 的 HTTPDNS 与 IP 直连。

语义：含子域来源（`||domain^`）用 `DOMAIN-SUFFIX` 类算子（匹配域名及其所有子域）；精确来源（hosts 行 / 纯域名行）用 `DOMAIN` 类算子（仅匹配域名本体）。同一域名两种来源并存时按更宽的含子域处理。规则集忽略 `$` 修饰符——它只承载域名。

### 4.1 mihomo / Clash Meta `adblock_clash.yaml`

```yaml
# rule-providers: { type: http, behavior: domain, format: yaml }
# Total Domains: 539768
payload:
  - '+.example.com'
  - 'exact.example.com'
```

`+.domain` 等价 `DOMAIN-SUFFIX`；裸 `domain` 等价 `DOMAIN`。rule-provider 需配 `behavior: domain`、`format: yaml`。

### 4.2 sing-box `adblock_singbox.json`

```json
{"version": 3, "rules": [{"domain_suffix": ["example.com"]}, {"domain": ["exact.example.com"]}]}
```

源规则集（source rule-set，version 3，需 sing-box 1.11+）。使用前编译：

```bash
sing-box rule-set compile adblock_singbox.json -o adblock.srs
```

`domain_suffix` 匹配域名及子域，`domain` 仅匹配本体。

### 4.3 Surge 规则集 `adblock_surge.list`

```text
# Total Rules: 539768
DOMAIN-SUFFIX,example.com,REJECT
DOMAIN,exact.example.com,REJECT
```

### 4.4 Surge 域名集 `adblock_surge_domain_set.txt`

```text
# Format: Surge DOMAIN-SET (.domain = domain + subdomains, bare = exact), total 539768
.example.com
exact.example.com
```

前导点 `.domain` = 本体 + 子域，裸域名 = 精确。用 `DOMAIN-SET,<url>,REJECT` 引用；由 Surge 预建索引，单集上限 1,000,000 条，体积与匹配效率优于逐行 `RULE-SET`。

### 4.5 Quantumult X `adblock_quanx.list`

```text
# Total Rules: 539768
host-suffix, example.com, reject
host, exact.example.com, reject
```

### 4.6 分片

Surge 逐行规则集与 Quantumult X 规则集超过 jsDelivr 上限时，额外输出 `adblock_surge_partNN.list` / `adblock_quanx_partNN.list`（`# Part i/N` 标注序号），订阅方需全部加入。Surge 推荐直接用无需分片的 `DOMAIN-SET` 单文件。

## 5. 客户端适配产物（`adapters/`）

面向单个客户端、可直接粘贴或导入的适配文件，共 9 个。适配文件只做「引用 + 配置」：拦截范围完全来自被引用的规范规则集（第 3、4 节），不新增任何判定、不整份替换用户配置。文件无生成时间戳，相同输入逐字节一致。

获取地址：`https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adapters/<文件名>`，镜像 `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adapters/<文件名>`。

| 文件 | 客户端 | 引用的规范产物 |
| :--- | :--- | :--- |
| `mihomo.yaml` | mihomo / Clash Meta | `rulesets/adblock_clash.yaml` |
| `singbox.json` | sing-box | `rulesets/adblock_singbox.json` |
| `surge.conf` | Surge | `rulesets/adblock_surge_domain_set.txt` |
| `quanx.conf` | Quantumult X | `rulesets/adblock_quanx*.list` |
| `adguardhome.yaml` | AdGuard Home | `adblock_collection_full_domains.txt` |
| `pihole.txt` | Pi-hole | `adblock_collection_full_dns.txt` |
| `dnsmasq.conf` | dnsmasq | `adblock_collection_full_dns.txt` |
| `hosts.md` | 系统 hosts | `adblock_collection_full_dns[_ipv6].txt` |
| `browsers.md` | 浏览器扩展 | `adblock_collection_full.txt` / `ubo_enhance.txt` |

### 5.1 `mihomo.yaml`

```yaml
rule-providers:
  adblock:
    type: http
    behavior: domain
    format: yaml
    url: "https://raw.githubusercontent.com/wansheng8/GZ/main/dist/rulesets/adblock_clash.yaml"
    path: ./ruleset/adblock.yaml
    interval: 86400
rules:
  - RULE-SET,adblock,REJECT
```

把 `rule-providers` 与 `rules` 两段并入 `config.yaml`；`path` 指向本地缓存位置。

### 5.2 `singbox.json`

JSONC（`//` 注释由 sing-box 支持）。使用远端源格式规则集，需 sing-box 1.11+，无需先 `rule-set compile`：

```json
{
  "route": {
    "rule_set": [
      {
        "type": "remote",
        "tag": "adblock",
        "format": "source",
        "url": "https://raw.githubusercontent.com/wansheng8/GZ/main/dist/rulesets/adblock_singbox.json",
        "update_interval": "1d"
      }
    ],
    "rules": [{ "rule_set": "adblock", "action": "reject" }]
  }
}
```

把 `route.rule_set` 与 `route.rules` 并入 `config.json`。远端规则集缓存依赖 `experimental.cache_file.enabled=true`；未开启时每次启动都会重新下载（仍可用，仅无本地缓存）。

### 5.3 `surge.conf`

```ini
DOMAIN-SET,https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_surge_domain_set.txt,REJECT,update-interval=86400
```

加入 `[Rule]` 段。`DOMAIN-SET` 单文件无需分片，是 Surge 推荐形态；`update-interval=<秒>` 为官方可选参数（默认 86400 秒，负值关闭自动更新），此处显式写出。

### 5.4 `quanx.conf`

```ini
filter_remote = https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_quanx_part01.list, tag=Adblock-1, force-policy=reject, enabled=true
filter_remote = https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_quanx_part02.list, tag=Adblock-2, force-policy=reject, enabled=true
```

加入 `[filter_remote]` 段。`force-policy=reject` 是 Quantumult X 官方参数（可选 `tag` / `force-policy` / `enabled`），使远端规则统一按 `reject` 处理；不存在 `force-remote-filter` 参数。规则集超 jsDelivr 上限（20MB）时必须逐行加入 `_partNN` 分片——完整文件的镜像 URL 会返回 403，只有 GitHub raw 的完整单文件可直连引用，且二者不要同时加入以免重复匹配。

### 5.5 `adguardhome.yaml`

```yaml
filters:
  - enabled: true
    url: https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_domains.txt
    name: Adblock Collection (DNS domains)
```

并入 `AdGuardHome.yaml` 的 `filters` 段后重启。只含拦截列表，**不含放行规则**；放行由用户按需单独处理。

### 5.6 `pihole.txt`

逐行一个列表 URL 的 `adlists` 内容，追加到 `adlists.list` 或用 Web 界面 Adlists 添加。

### 5.7 `dnsmasq.conf`

```ini
addn-hosts=/etc/dnsmasq.d/adblock_collection_full_dns.txt
```

dnsmasq 不能直接拉取远程 URL；文件头已给出先下载 hosts 到本地路径的 `curl` 命令。

### 5.8 `hosts.md` / `browsers.md`

指引型产物，给出下载地址与各平台安装路径/导入步骤，不复制数十万行域名。hosts 提供 Windows / macOS / Linux / Android 路径与写入命令；浏览器提供 uBO / AdGuard / ABP 的订阅地址与导入路径。

### 5.9 基址配置

`config/sources.yaml` 顶层 `publish` 段是唯一来源：

```yaml
publish:
  repository: wansheng8/GZ
  branch: main
  raw_base: ""      # 留空则由 repository/branch 派生
  mirror_base: ""   # 留空则由 repository/branch 派生
```

`raw_base` = `https://raw.githubusercontent.com/{repository}/{branch}/dist/`，`mirror_base` = `https://cdn.jsdelivr.net/gh/{repository}@{branch}/dist/`；仓库迁移或改分支只需改这里。

### 5.10 各客户端订阅地址清单

按客户端汇总「填进软件里」的引用地址（`raw` = 规范源，`jsDelivr` = 镜像；同一设备二选一）。适配文件本身在 `adapters/` 下，见 5.1–5.8；完整可复制清单见 `README.md`「各客户端订阅地址清单」。

| 客户端 | 引用的规范产物 | 适配文件 |
| :--- | :--- | :--- |
| mihomo / Clash Meta | `rulesets/adblock_clash.yaml` | `adapters/mihomo.yaml` |
| sing-box | `rulesets/adblock_singbox.json` | `adapters/singbox.json` |
| Surge | `rulesets/adblock_surge_domain_set.txt` | `adapters/surge.conf` |
| Quantumult X | `rulesets/adblock_quanx_partNN.list`（镜像）或 `rulesets/adblock_quanx.list`（raw） | `adapters/quanx.conf` |
| AdGuard Home | `adblock_collection_full_domains.txt` | `adapters/adguardhome.yaml` |
| Pi-hole | `adblock_collection_full_dns.txt` | `adapters/pihole.txt` |
| dnsmasq | 本地 `adblock_collection_full_dns.txt`（不能远程订阅） | `adapters/dnsmasq.conf` |
| 系统 hosts | `adblock_collection_full_dns.txt` / `_dns_ipv6.txt` | `adapters/hosts.md` |
| 浏览器扩展 | `adblock_collection_full.txt` / `_jsdelivr.txt` / `ubo_enhance.txt` | `adapters/browsers.md` |

## 6. 统计与审计产物

### 6.1 统计 `*.stats.txt` / `*.stats.json`

```json
{
  "name": "adblock_collection_full",
  "total": 793579,
  "by_category": {"network": 480123, "css": 143222, "...": 0},
  "by_kind": {"network": 629423, "css": 146131, "scriptlet": 17516, "html": 508, "js": 1},
  "by_source": {"上游名单名": 0}
}
```

`.stats.txt` 为同内容的纯文本版。

### 6.2 DNS 分级审计 `*.dns_safety.json`

```json
{
  "policy_level": "safe",
  "min_confidence": 0.8,
  "allow_modifier": true,
  "include_navigation_domains": true,
  "dns_eligible_network_rules": 541581,
  "dns_rejected_network_rules": 251998,
  "navigation_eligible_rules": 235,
  "by_eligibility": {"SAFE": 541581, "REJECT": 251998},
  "by_reason": {"pure_domain": 539817, "path_rule": 51309, "untranslatable": 12651},
  "by_reason_labels": {"pure_domain": "纯域名规则，整域拦截语义等价（confidence=1.0）"},
  "unknown_modifiers": {"upstream-new-token": 12}
}
```

- 计数对象只列出非零项（`by_eligibility` 的零值档位、`by_reason` 的零计数原因、`unknown_modifiers` 为空时均为空对象）。

- `dns_eligible_*` / `dns_rejected_*`：本次构建中满足 / 不满足 DNS 分级的网络规则条数。
- `navigation_eligible_rules`：其中因 `$popup`/`$document` 等导航修饰被放大为整域拦截的条数（受 `include_navigation_domains` 控制）。
- `by_reason`：拒绝原因计数；`by_reason_labels` 是同一批原因的人类可读说明（见 `dns_policy.REASON_DESCRIPTIONS`）。
- `unknown_modifiers`：上游出现的、未被 `dns_policy` 识别的修饰符及其条数。用于发现上游新增修饰符（U7 跟进信号）。

### 6.3 清单索引 `manifest.json`

```json
{
  "generator": "adblock-rule-collection",
  "versions": {"parser": "1.9.1", "normalizer": "1.4.0", "classifier": "1.13.0"},
  "generated_at": "2026-09-25T16:48:06Z",
  "sources_status": {"total_sources": 60, "failed_sources": [], "complete": true},
  "generated_files": [
    {"name": "adblock_collection_full", "file": "adblock_collection_full.txt", "format": "adblock", "rules": 793579, "bytes": 26173566, "sha256": "..."},
    {"name": "adblock_collection_full", "file": "adblock_collection_full_jsdelivr.txt", "format": "adblock_include", "rules": 793579, "parts": ["adblock_collection_full_jsdelivr_part01.txt"]}
  ]
}
```

- `file`：相对 `manifest.json` 的路径，`security/`、`rulesets/` 前缀已包含。
- `format`：文件语法（`adblock` / `adblock_include` / `hosts` / `hosts_ipv6` / `domains` / `adblock_domains` / `adblock_ubo` / `dns_allow` / `clash_ruleset` / `singbox_ruleset` / `surge_ruleset` / `surge_domain_set` / `quanx_ruleset` / `adapter` / `*_part`）。适配产物（`adapters/`）额外带 `target` 字段（客户端标识）。
- `bytes` / `sha256`：文件大小与内容校验，订阅端可据此判断是否更新、校验完整性。
- `empty: true`：该类无规则（空产物）。
- `versions`：解析/归一/分类三轴版本，任一轴变化意味着产物可能变化。

### 6.4 其它 JSON

| 文件 | 作用 |
| :--- | :--- |
| `sources_status.json` | 上游完整性：`total_sources` / `failed_sources` / `complete` / `generated_at` |
| `build_report.json` | 质量门禁：`passed` / `failures` / `warnings` / `metrics` / `diff` / `previous` / `enhancements` |
| `regression_report.json` | 误杀回归：`allow_violations` / `block_missing` / `block_missing_strict` |
| `arbitration.json` | 例外与阻断的仲裁明细（整域冲突裁决） |
| `domain_fold.json` | 域名折叠：`folded` / `before` / `after` / `domains` |
| `previous_metrics.json` | 上一轮指标基线，供门禁对比 |

以下文件在本地构建中生成但不入库（见 `.gitignore`），供 CI 门禁与人工审计：`provenance.json`（来源血缘）、`relation_graph.json`（父子域/跨源重复/冲突）、`build_diff.txt`（构建差异）、`new_domain_review.json`（新增整域阻断复核，按 allow 命中给出 critical/high/low）、`maintenance_report.json`（规则过期跟踪）。

## 7. 源语法到生成语法的映射（DNS 安全分级）

DNS 只能表达「整域拦截 / 放行」，因此把网络规则升级为 DNS 域名需要 fail-closed 判定。默认档 `all`（`README`/构建可切 `safe`、`strict-safe`）。判定顺序（`dns_policy.classify_dns`）：

| 源规则特征 | 判定 | 生成到 DNS / hosts |
| :--- | :--- | :--- |
| 元素隐藏 / 脚本注入（`##`、`##+js`…） | `css_rule` / `script_rule` | 否 |
| 非网络规则 | `non_network_rule` | 否 |
| 含 `$regexp`/`$redirect`/`$rewrite` | `regex_or_redirect_rule` | 否 |
| 含非阻断修饰（`$removeparam`/`$csp`/`$generichide`…） | `non_blocking_modifier` | 否 |
| 含作用域限定（`$domain`/`$from`/`$to`/`$top`/`$app`/`$client`…） | `scoped_modifier` | 否 |
| 含 `$cname` | `match_method_modifier` | 否 |
| 含资源类型（`$script`/`$image`/`$websocket`/`$fetch`…） | `resource_type_modifier` | 否 |
| 含第一/第三方（`$third-party`/`$strict1p`…） | `party_modifier` | 否 |
| 含路径（`||a.com/path`） | `path_rule` | 否 |
| 纯域名 `||a.com^` | `pure_domain`（conf=1.0） | 是 |
| 仅带整域语义 `$all`/`$important`/`$match-case` | `pure_domain_modifier`（conf=1.0） | 是 |
| 仅带导航语义 `$popup`/`$popunder`/`$doc`/`$document`（含与整域语义组合） | `navigation_domain_modifier`（conf=0.8） | 是（可退出） |
| 含未识别修饰符 | `unknown_modifier` | 否（fail-closed） |
| 选项全已知但无可表达域名（无域名 URL/正则模式） | `untranslatable` | 否 |

生成的域名形态：

- `||a.com^`（含子域语义）→ `0.0.0.0 a.com` / `a.com` / `||a.com^`；连接层 `DOMAIN-SUFFIX` / `domain_suffix` / `host-suffix` / `+.a.com` / `.a.com`。
- hosts 行或纯域名行（精确语义）→ 同样的文本域名，但连接层用 `DOMAIN` / `domain` / `host` / 裸域名 / 裸 `domain`。

放行抵消：只有自定义白名单（`config/lists/allowlist.txt`）中的**整域全局例外**会把域名从拦截集合剔除；上游例外、作用域/路径/导航/非阻断例外都不参与 DNS 放行。浏览器层例外不进入 DNS 集合，这是因为 DNS 没有页面上下文。

## 8. 用法

### 8.1 订阅

直接使用 `README.md`「订阅中心」中的长期链接（`raw.githubusercontent.com` 主链或 `cdn.jsdelivr.net` 镜像）。DNS 设备只导入一个文件，避免浏览器列表里的站点级例外在无上下文的 DNS 层被当成整域放行。

### 8.2 连接层

mihomo / sing-box / Surge / Quantumult X 的 `rule-providers` / `filter_remote` 配置示例见 `README.md`「连接层规则集用法」。sing-box 需先 `rule-set compile`，或直接使用第 5 节的 `singbox.json` 适配产物（`format: source` 免编译）。

### 8.3 客户端适配

不想自己拼配置时，直接取第 5 节 `adapters/` 下对应客户端的文件，粘贴或导入即可；适配产物只引用本节规范规则集，与手动配置拦截范围一致。

### 8.4 本地构建

```bash
pip install -r requirements.txt

# 完整版 + 类别拆分 + 三层产物 + DNS（规则增强默认开启）
python -m adblock_collection build --out dist --split-by-category
```

常用子命令：`sources`（列出上游）、`regression`（误杀回归）、`lint`（本地规则语法/冲突校验）、`stats --out dist`（仅刷新统计与 manifest）。构建选项见 `docs/OPS.md`。

### 8.5 程序化读取

订阅端只需拉取 `dist/manifest.json`：遍历 `generated_files`，按 `format` 选择载体，按 `bytes`/`sha256` 判断是否需要更新与校验完整性；用 `versions`/`generated_at`/`sources_status` 做溯源与完整性判断。

## 9. 相关文档

| 文档 | 内容 |
| :--- | :--- |
| `README.md` | 订阅地址、三层防护、常见问题、连接层配置 |
| `docs/SYNTAX.md` | 过滤规则语法知识库（`||`、`$` 修饰符、元素隐藏、优先级、自定义黑名单） |
| `docs/OPS.md` | 构建、配置源、白名单、门禁与源失效处置 |
| `docs/FLOW.md` | 构建流水线各阶段 |
| `docs/BLOCKING_AUDIT.md` | 拦截覆盖率审计与实施状态 |
| `docs/UPGRADE_PROPOSAL.md` | 版本轴与改进提案 |
