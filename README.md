<div align="center">

<img src="assets/banner.svg" width="100%" alt="Adblock Rule Collection — 广告拦截 · DNS 过滤 · 安全防护"/>

<br/>

[![Build](https://github.com/wansheng8/GZ/actions/workflows/build.yml/badge.svg)](https://github.com/wansheng8/GZ/actions/workflows/build.yml)
[![Rules](https://img.shields.io/badge/Total_Rules-800%2C813-ff00e5?style=for-the-badge&labelColor=0d0d0d)](dist/adblock_collection_full.txt)
[![DNS](https://img.shields.io/badge/DNS_Domains-547%2C046-00f0ff?style=for-the-badge&labelColor=0d0d0d)](dist/adblock_collection_full_dns.txt)
[![Sources](https://img.shields.io/badge/Upstream-60_sources-9d00ff?style=for-the-badge&labelColor=0d0d0d)](config/sources.yaml)
[![License](https://img.shields.io/badge/License-MIT-39ff14?style=for-the-badge&labelColor=0d0d0d)](LICENSE)
[![Update](https://img.shields.io/badge/Update-Daily-ff9c39?style=for-the-badge&labelColor=0d0d0d)]()

**60+ 上游列表 → 去重 · 合并 → 百万级广告拦截与 DNS 过滤规则**

`URL` · `域名` · `CSS` · `脚本` · `隐私` · `Cookie` · `恶意` · `钓鱼` · `挖矿`

<br/>

[![Adblock Plus](https://img.shields.io/badge/Adblock_Plus-c70f0f?style=for-the-badge&labelColor=0d0d0d)]()
[![uBlock Origin](https://img.shields.io/badge/uBlock_Origin-8b0000?style=for-the-badge&labelColor=0d0d0d)]()
[![AdGuard](https://img.shields.io/badge/AdGuard-68bc71?style=for-the-badge&labelColor=0d0d0d)]()
[![Pi-hole](https://img.shields.io/badge/Pi--hole-f60d1a?style=for-the-badge&labelColor=0d0d0d)]()
[![dnsmasq](https://img.shields.io/badge/dnsmasq-00f0ff?style=for-the-badge&labelColor=0d0d0d)]()
[![hosts](https://img.shields.io/badge/hosts-9d00ff?style=for-the-badge&labelColor=0d0d0d)]()
[![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=for-the-badge&logo=python&logoColor=white&labelColor=0d0d0d)]()

<br/>

> **「 宁愿少拦截，不要误拦截 」**
> `DNS 安全分级` ▸ `误杀回归库` ▸ `质量门禁`，构建失败 **自动中止发布**

<br/>

[订阅中心](#subscribe) &nbsp;·&nbsp; [三层防护](#layers) &nbsp;·&nbsp; [当前规模](#scale) &nbsp;·&nbsp; [常见问题](#faq) &nbsp;·&nbsp; [进阶与构建](#advanced)

</div>

<img src="assets/divider.svg" width="100%" alt=""/>

<a name="subscribe"></a>

<img src="assets/sections/subscribe.svg" width="100%" alt="订阅中心"/>

## 订阅中心

每日 `03:00 UTC` 自动构建 · **订阅一次，自动更新** · 链接长期有效

### 我该订阅哪个？

| 你的场景 | 一键订阅 |
| :--- | :--- |
| **AdGuard Home · Pi-hole · dnsmasq · 路由器** | **[DNS 规则](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt)** · [jsDelivr](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt) |
| **uBlock Origin · AdGuard（浏览器扩展）** | **[浏览器全量](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full.txt)** · [jsDelivr](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_jsdelivr.txt) |
| **mihomo · sing-box · Surge · Quantumult X** | **代理规则集**（拦 App 内广告，订阅链接与用法见下方「连接层规则集用法」） |
| **只想要安全拦截（低误杀）** | **[安全专项](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/security/adblock_collection_security.txt)** · [jsDelivr](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/security/adblock_collection_security.txt) |

> [!IMPORTANT]
> **DNS 设备只导入一个文件**：AdGuard Home / Pi-hole 在上面的 DNS 链接里选一个并只保留它，不要同时导入浏览器列表——浏览器列表含约 2,500 条站点级例外（`@@||ad-domain^$domain=...`），DNS 层没有页面上下文，会把它当成整域放行，导致「导得越多、拦得越少」。

> [!TIP]
> 国内直连 GitHub 慢时用 **jsDelivr** 列。仅需安全拦截时，单独订阅「安全专项」即可绕过完整版的误杀风险。

<details>
<summary><code>全部订阅链接（纯文本，可直接复制）</code></summary>

```text
[DNS · 设备级拦截（IPv4 hosts，推荐）]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt

[DNS · IPv6 双栈补订]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_ipv6.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_ipv6.txt

[DNS · 单行域名（AdGuard DNS / 自定义黑名单）]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_domains.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_domains.txt

[DNS 等价 · ||domain^ 域名规则]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_abp.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_abp.txt

[扩展 · 网络拦截层]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_browser_network.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_browser_network.txt

[扩展 · 元素隐藏层]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_cosmetic.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_cosmetic.txt

[浏览器专用 · 全量]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_jsdelivr.txt

[安全专项 · 恶意 / 钓鱼 / 挖矿]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/security/adblock_collection_security.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/security/adblock_collection_security.txt

[DNS 白名单 · 整域放行]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/dns_allow.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/dns_allow.txt

[uBO 增强 · redirect / csp / removeparam / scriptlet]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_ubo_enhance.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_ubo_enhance.txt

[连接层 · mihomo / Clash Meta]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/rulesets/adblock_clash.yaml
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_clash.yaml

[连接层 · sing-box]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/rulesets/adblock_singbox.json
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_singbox.json

[连接层 · Surge]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/rulesets/adblock_surge_domain_set.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_surge_domain_set.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_surge_part01.list
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_surge_part02.list

[连接层 · Quantumult X]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/rulesets/adblock_quanx.list
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_quanx_part01.list
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_quanx_part02.list
```

> 浏览器全量单文件约 24MB，超 jsDelivr 单文件 20MB 上限，故 jsDelivr 用 `!#include` 分片主链（扩展会自动跟随分片），GitHub 则是完整单文件。
> Surge 推荐 `DOMAIN-SET` 单文件（无需分片）；逐行 `RULE-SET` 版本超 20MB，jsDelivr 拆为 `_part01` / `_part02`。Quantumult X 规则集超 20MB，jsDelivr 拆为 `_part01` / `_part02`，需把两份都加入；GitHub 上是完整单文件。

</details>

<details>
<summary><code>连接层规则集用法（穿透 HTTPDNS，拦 App 内广告）</code></summary>

各格式内容一致（与 DNS 域名集合同源），并同样尊重 `config/lists/allowlist.txt` 的自定义放行。来源为 `||domain^` 的域名按「域名 + 其所有子域」拒绝（`DOMAIN-SUFFIX` / `domain_suffix` / `host-suffix` / `DOMAIN-SET` 前导点）；来源为 hosts 行 / 纯域名行的域名按 AdGuard 语义仅拒绝域名本体（`DOMAIN` / `domain` / `host` / `DOMAIN-SET` 裸域名），不误伤其子域。TUN 模式下由内核读取 TLS/QUIC SNI 匹配，App 用 HTTPDNS 或 IP 直连也无法绕过。

**mihomo / Clash Meta**

```yaml
rule-providers:
  adblock:
    type: http
    behavior: domain
    format: yaml
    url: "https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_clash.yaml"
    path: ./ruleset/adblock.yaml
    interval: 86400
rules:
  - RULE-SET,adblock,REJECT
```

**sing-box**（先编译为二进制规则集）

```bash
sing-box rule-set compile adblock_singbox.json -o adblock.srs
```

```json
{
  "route": {
    "rule_set": [
      { "type": "local", "tag": "adblock", "format": "binary", "path": "./adblock.srs" }
    ],
    "rules": [{ "rule_set": "adblock", "action": "reject" }]
  }
}
```

**Surge**（推荐 `DOMAIN-SET` 单文件，无需分片）

```ini
DOMAIN-SET,https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_surge_domain_set.txt,REJECT
```

逐行规则包 `RULE-SET` 亦可（jsDelivr 分片需两条）：

```ini
RULE-SET,https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_surge_part01.list,REJECT
RULE-SET,https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_surge_part02.list,REJECT
```

**Quantumult X**（jsDelivr 分片需两条）

```ini
filter_remote = https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_quanx_part01.list, tag=Adblock-1, force-remote-filter=1
filter_remote = https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_quanx_part02.list, tag=Adblock-2, force-remote-filter=1
```

</details>

<img src="assets/divider.svg" width="100%" alt=""/>

<a name="layers"></a>

<img src="assets/sections/layers.svg" width="100%" alt="三层防护"/>

## 三层防护

### 按需选一层，或叠加使用

| 层级 | 拦什么 | 适合谁 |
| :--- | :--- | :--- |
| **DNS 拦截** | 广告域名拿不到 IP（只能整域） | 全家设备一次搞定：电脑 / 手机 / TV |
| **扩展 · 网络拦截** | 请求发起前阻断，可限定路径 / 资源类型 | 浏览器内更精细、更准 |
| **扩展 · 元素隐藏** | 隐藏页面广告位与弹窗 | 清理第一方与动态广告 |

> 一句话：**DNS 全局减负 → 网络拦截精细阻断 → 元素隐藏清理页面。**
> DNS 层只能处理整域；`##`、`$xxx` 这类语法只放浏览器扩展，放进 DNS 会导致整份清单失效（构建流程已用回归测试保证 DNS 文件只含纯域名）。

<img src="assets/divider.svg" width="100%" alt=""/>

<a name="scale"></a>

<img src="assets/sections/scale.svg" width="100%" alt="当前规模"/>

## 当前规模

<div align="center">

<img src="assets/stats.svg" width="100%" alt="800,813 rules · 547,046 domains · 60 sources · 33.8万+ deduplicated"/>

</div>

### 规则类型构成

| 类型 | 数量 | 归属层 |
| :--- | ---: | :--- |
| network | 626,227 | 网络拦截（DNS 从中提取纯域名） |
| css | 141,193 | 元素隐藏 |
| scriptlet | 10,802 | 元素隐藏 |
| html / js | 188 | 元素隐藏 |

### 按类别订阅

按类别拆分（`dist/adblock_collection_full_<类别>.txt`，均附 `_dns.txt` / `_domains.txt` 版本）：

| 类别 | 订阅 |
| :--- | :--- |
| network | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_network.txt) |
| privacy | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_privacy.txt) |
| phishing | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_phishing.txt) |
| annoyance | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_annoyance.txt) |
| cookie | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_cookie.txt) |
| social | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_social.txt) |
| malware | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_malware.txt) |
| whitelist | 例外规则（仅供审计） |

<img src="assets/divider.svg" width="100%" alt=""/>

<a name="faq"></a>

<img src="assets/sections/faq.svg" width="100%" alt="常见问题"/>

## 常见问题

### 导入了却不拦截？

先确认域名解析确实经过该 DNS：

```bash
nslookup doubleclick.net <你的 AdGuard Home / Pi-hole 地址>
```

应返回 `0.0.0.0` 或 NXDOMAIN。若返回真实 IP，说明设备 / 浏览器走了 DoH（Chrome 或系统「安全 DNS」），关闭 DoH 后再测。

### App 开屏 / 信息流广告拦不住？

这类广告由 App 内嵌广告 SDK 拉取，常经 App 自身接口、共享核心域（`pstatp.com`、`kuaishou.com`、`gifshow.com`）或 HTTPDNS / IP 直连下发。DNS 层只能按独立广告域拦截整域，无法区分同一接口返回里的广告与正常内容；封掉共享核心域会直接弄坏对应 App。

对策：订阅上方**连接层规则集**，代理内核开 TUN 后按 SNI 拒绝广告域，可穿透 HTTPDNS；接口级广告再配合 iOS 圈X MITM rewrite、Android AdGuard HTTPS 过滤或 LSPosed 去广告模块。

### 怎么验证三层是否生效？

1. 无痕窗口并清缓存，避免旧缓存干扰。
2. **DNS 层**：`nslookup doubleclick.net <DNS地址>` 返回 `0.0.0.0` / NXDOMAIN，DNS 日志有拦截记录。
3. **网络层**：扩展日志里广告脚本、iframe、XHR 显示被 block。
4. **元素隐藏层**：页面广告块、反广告弹窗被隐藏或移除。

> tryblock / d3ward 的测试项多是元素隐藏、脚本注入，**DNS 层天然拦不到**，得分偏低属预期；DNS 是否生效看广告网络域名（`googlesyndication.com`、`doubleclick.net`、`an.yandex.ru`）能否解析。

<img src="assets/divider.svg" width="100%" alt=""/>

<a name="advanced"></a>

<img src="assets/sections/advanced.svg" width="100%" alt="进阶与构建"/>

## 进阶与构建

### 本地构建

```bash
pip install -r requirements.txt

# 完整版 + 类别拆分 + 三层产物 + DNS（规则增强默认开启）
python -m adblock_collection build --out dist --split-by-category

# 常用子命令
python -m adblock_collection sources               # 列出上游列表
python -m adblock_collection regression            # 误杀回归校验
python -m adblock_collection lint                  # 校验本地规则语法/冲突
python -m adblock_collection stats --out dist      # 仅刷新统计与 manifest
```

构建选项：`--no-dns` · `--offline` · `--no-cache` · `--dns-policy safe` · `--no-alias-normalize` / `--no-resolve-conflicts` / `--no-per-rule-classify` / `--no-domain-fold`。缓存位于 `.cache/sources/` 与 `.cache/parsed/`，首次下载后离线可重建。

### 防误杀体系

- **DNS 安全分级**：`all`（默认，中风险）/ `safe`（低）/ `strict-safe`（最低）。资源类型、第一 / 第三方与作用域限定在 DNS 层无法表达，一律拒绝升级为整域拦截。
- **误杀回归库**：`config/false_positives.yaml` 覆盖主流站点（Google、百度、微信、支付宝、GitHub、银行电商），命中即 **构建失败（exit 1）**。
- **质量门禁**：对比上一轮 `previous_metrics.json`，单源规则骤降 `>50%`、总量骤增 `>20%`、DNS 域名骤增 `>15%` 直接失败；报告写入 `dist/build_report.json`。
- **来源血缘**：`provenance.json` 记录每条规则来源与置信度，`relation_graph.json` 识别父子域冗余 / 跨源重复 / 阻断与例外冲突。
- `dns_allow.txt` 只收录 `config/lists/allowlist.txt` 的整域全局例外，白名单内容完全由维护者掌控。

### 自定义上游与黑名单

编辑 `config/sources.yaml` 添加上游：

```yaml
sources:
  - name: My Custom List
    url: https://example.com/my-filter.txt
    category: network      # network / privacy / cookie / social / malware / phishing / mining / annoyance
    compatible: [adguard, abp, ubo]
    dns_policy:
      level: strict-safe   # all / safe / strict-safe
```

自定义黑 / 白名单放在固定目录 `config/lists/`，在去重前作为独立来源并入，与上游同权：

```text
config/lists/blocklist.txt   自定义阻断（LocalBlocklist），示例 example.com 或 ||ads.example.com^
config/lists/allowlist.txt   自定义放行（LocalAllowlist），示例 example.com 或 @@||example.com^
```

优先级：自定义白名单 > 自定义黑名单 > 上游例外 > 上游 `$important` > 上游普通阻断。裸域名按方向补全；`allowlist.txt` 的整域全局例外同时输出到 `dist/dns_allow.txt`。

### 项目结构

```text
adblock_collection/
  rules.py        规则解析 · 规范化 · 分类 · 类型识别
  merge.py        上游下载 · 合并 · 去重 · badfilter · 冗余消除
  writer.py       多格式输出（adblock / hosts / domains / rulesets / stats）
  dns_policy.py   DNS 安全分级
  regression.py   误杀回归校验
  lint.py         规则语法/冲突校验
  quality_gate.py 质量门禁与基线
  pipeline.py     阶段缓存与算法版本常量
  provenance.py   来源血缘与语义关系图
  cli.py          命令行入口
config/
  sources.yaml            上游配置
  false_positives.yaml    误杀回归清单
  local_rules.txt         本地增强规则
  lists/                  自定义黑名单 / 白名单
tests/                    单元与端到端测试
.github/workflows/build.yml   每日自动构建并推送
```

<img src="assets/divider.svg" width="100%" alt=""/>

<a name="warning"></a>

<img src="assets/sections/warning.svg" width="100%" alt="使用须知"/>

## 使用须知

> [!CAUTION]
> 本过滤器 **可能破坏某些网站功能**，或 **阻断部分成人 / 赌博站点**。
> 如有误杀，请向上游列表反馈；本仓库仅提供去重、转化、合并，不参与内容判定。

<img src="assets/divider.svg" width="100%" alt=""/>

<div align="center">

<img src="assets/sections/license.svg" width="100%" alt="许可证"/>

[![MIT](https://img.shields.io/badge/LICENSE-MIT-39ff14?style=for-the-badge&labelColor=0d0d0d)](LICENSE)

```diff
- [ CONNECTION TERMINATED ]  system.exit(0)  ::  stay clean, stay unblocked
```

</div>
