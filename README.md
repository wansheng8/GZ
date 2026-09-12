<div align="center">

<img src="assets/banner.svg" width="100%" alt="Adblock Rule Collection — 广告拦截 · DNS 过滤 · 安全防护"/>

<br/>

[![Build](https://github.com/wansheng8/GZ/actions/workflows/build.yml/badge.svg)](https://github.com/wansheng8/GZ/actions/workflows/build.yml)
[![Rules](https://img.shields.io/badge/Total_Rules-968%2C349-ff00e5?style=for-the-badge&labelColor=0d0d0d)](dist/adblock_collection_full.txt)
[![DNS](https://img.shields.io/badge/DNS_Domains-491%2C021-00f0ff?style=for-the-badge&labelColor=0d0d0d)](dist/adblock_collection_full_dns.txt)
[![Sources](https://img.shields.io/badge/Upstream-60_sources-9d00ff?style=for-the-badge&labelColor=0d0d0d)](config/sources.yaml)
[![License](https://img.shields.io/badge/License-MIT-39ff14?style=for-the-badge&labelColor=0d0d0d)](LICENSE)
[![Update](https://img.shields.io/badge/Update-Daily-ff9c39?style=for-the-badge&labelColor=0d0d0d)]()

**将 `60+` 上游列表转化 · 去重 · 合并为百万级广告拦截与 DNS 过滤规则**

`URL` · `域名` · `CSS` · `脚本` · `隐私` · `Cookie` · `恶意` · `钓鱼` · `挖矿`

<br/>

[![Adblock Plus](https://img.shields.io/badge/Adblock_Plus-c70f0f?style=for-the-badge&labelColor=0d0d0d)]()
[![uBlock Origin](https://img.shields.io/badge/uBlock_Origin-8b0000?style=for-the-badge&labelColor=0d0d0d)]()
[![AdGuard](https://img.shields.io/badge/AdGuard-68bc71?style=for-the-badge&labelColor=0d0d0d)]()
[![Pi-hole](https://img.shields.io/badge/Pi--hole-f60d1a?style=for-the-badge&labelColor=0d0d0d)]()
[![dnsmasq](https://img.shields.io/badge/dnsmasq-00f0ff?style=for-the-badge&labelColor=0d0d0d)]()
[![hosts](https://img.shields.io/badge/hosts-9d00ff?style=for-the-badge&labelColor=0d0d0d)]()
[![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=for-the-badge&logo=python&logoColor=white&labelColor=0d0d0d)]()

> **「 宁愿少拦截，不要误拦截 」**
> 内置 `DNS 安全分级` ▸ `误杀回归库` ▸ `质量门禁`，构建失败 **自动中止发布**

</div>

<img src="assets/divider.svg" width="100%" alt=""/>

```diff
+ [ SYSTEM ONLINE ]  daily build @ 03:00 UTC  ::  订阅一次 · 自动更新 · 链接长期有效
```

<img src="assets/sections/subscribe.svg" width="100%" alt="订阅中心"/>

每日 `03:00 UTC` 自动构建 · **订阅一次，自动更新** · 链接长期有效

| 订阅包 | 适用工具 | 一键导入 |
| :--- | :--- | :--- |
| **`[浏览器专用]`** 广告 + 隐私 + 安全 | uBlock Origin · AdGuard · AdBlock Plus | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-ff00e5?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full.txt) |
| **`[DNS · IPv4 hosts]`** 设备级拦截 | AdGuard Home · Pi-hole · dnsmasq | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-00f0ff?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt) |
| **`[DNS · IPv6 hosts]`** 双栈设备补订 | AdGuard Home · Pi-hole · dnsmasq | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_ipv6.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-9d00ff?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_ipv6.txt) |
| **`[单行域名列表]`** 纯域名格式 | AdGuard DNS · 各类域名过滤 | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_domains.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-ff9c39?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_domains.txt) |
| **`[安全专项]`** 恶意 + 钓鱼 · 低误杀 | 只需安全拦截的设备 | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/security/adblock_collection_security.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-39ff14?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/security/adblock_collection_security.txt) |

```console
>_ 三步上手
  1. 按设备选一行（浏览器选第 1 条，DNS 设备选第 2~4 条）
  2. 点「订阅 GitHub」，国内访问慢就点「订阅 jsDelivr」
  3. 在过滤工具里「添加自定义过滤列表」并粘贴
```

> [!TIP]
> 仅需安全拦截：单独订阅「安全专项」行即可，绕过完整版的误杀风险。

<details>
<summary><code>纯文本订阅链接</code></summary>

```text
[浏览器专用]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full.txt

[DNS · IPv4 hosts]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt

[DNS · IPv6 hosts]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_ipv6.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_ipv6.txt

[单行域名列表]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_domains.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_domains.txt

[安全专项]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/security/adblock_collection_security.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/security/adblock_collection_security.txt
```

</details>

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/scale.svg" width="100%" alt="当前规模"/>

<div align="center">

<img src="assets/stats.svg" width="100%" alt="968,349 rules · 491,021 domains · 60 sources · 33.8万+ deduplicated"/>

</div>

### ├─ 规则类型构成

| 类型 | 说明 |
| :--- | :--- |
| ![network](https://img.shields.io/badge/network-816%2C523-00f0ff?style=flat-square&labelColor=0d0d0d) | 域名 / URL / 资源请求阻断 |
| ![css](https://img.shields.io/badge/css-140%2C866-ff9c39?style=flat-square&labelColor=0d0d0d) | CSS 元素隐藏 |
| ![scriptlet](https://img.shields.io/badge/scriptlet-10%2C775-ff00e5?style=flat-square&labelColor=0d0d0d) | 脚本注入 / 反绕过 |
| ![html](https://img.shields.io/badge/html-184-9d00ff?style=flat-square&labelColor=0d0d0d) | HTML 过滤 |
| ![js](https://img.shields.io/badge/js-1-39ff14?style=flat-square&labelColor=0d0d0d) | 脚本规则 |

### ├─ 按类别拆分 · `--split-by-category`

| 类别 | 订阅文件 `dist/adblock_collection_full_<类别>.txt` |
| :--- | :--- |
| ![network](https://img.shields.io/badge/network-754%2C670-00f0ff?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_network.txt) |
| ![privacy](https://img.shields.io/badge/privacy-87%2C176-9d00ff?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_privacy.txt) |
| ![phishing](https://img.shields.io/badge/phishing-38%2C465-ff2e63?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_phishing.txt) |
| ![annoyance](https://img.shields.io/badge/annoyance-31%2C088-ff9c39?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_annoyance.txt) |
| ![cookie](https://img.shields.io/badge/cookie-24%2C189-b14dff?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_cookie.txt) |
| ![whitelist](https://img.shields.io/badge/whitelist-13%2C773-7a7a9a?style=flat-square&labelColor=0d0d0d) | 例外规则（仅供审计） |
| ![social](https://img.shields.io/badge/social-13%2C563-ff00e5?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_social.txt) |
| ![malware](https://img.shields.io/badge/malware-5%2C415-ff3b30?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_malware.txt) |
| ![mining](https://img.shields.io/badge/mining-none-7a7a9a?style=flat-square&labelColor=0d0d0d) | 当前无独立规则 |

> [!NOTE]
> 每个类别均附带 `_dns.txt` / `_dns_ipv6.txt` / `_domains.txt` 版本。
> 只想订阅安全类别（malware / phishing / mining）时，可绕过完整版的误杀风险。

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/features.svg" width="100%" alt="特性"/>

| | 能力 | 说明 |
| :--: | :--- | :--- |
| ![01](https://img.shields.io/badge/01-00f0ff?style=for-the-badge&labelColor=0d0d0d) | **多语法支持** | Adblock Plus / uBlock Origin / AdGuard / hosts / domains 全格式输出 |
| ![02](https://img.shields.io/badge/02-ff00e5?style=for-the-badge&labelColor=0d0d0d) | **分类发行** | 完整版 + 按类别拆分 + 安全类独立目录 |
| ![03](https://img.shields.io/badge/03-9d00ff?style=for-the-badge&labelColor=0d0d0d) | **防误杀体系** | DNS 三档安全分级 + 误杀回归库 + 质量门禁 |
| ![04](https://img.shields.io/badge/04-39ff14?style=for-the-badge&labelColor=0d0d0d) | **来源血缘审计** | `provenance.json` 记录每条规则来源与置信度 |
| ![05](https://img.shields.io/badge/05-ff9c39?style=for-the-badge&labelColor=0d0d0d) | **阶段缓存** | 源内容 sha256 + 算法版本，增量构建秒级完成 |
| ![06](https://img.shields.io/badge/06-00ffd0?style=for-the-badge&labelColor=0d0d0d) | **自动更新** | GitHub Actions 每日 03:00 UTC 自动重建推送 |

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/guide.svg" width="100%" alt="使用指南"/>

去上方「订阅中心」表格按设备点选，常见软件入口：

- **uBlock Origin**：`设置 → 过滤规则列表 → 用户自定义 → 导入`，粘贴浏览器专用链接。
- **AdGuard（App / 桌面版）**：`设置 → 内容拦截 → 过滤器 → 自定义过滤器 → 添加过滤器`，粘贴链接。
- **AdGuard Home**：`过滤器 → DNS 拦截清单 → 添加拦截清单`，粘贴 DNS hosts 或域名列表链接。
- **Pi-hole / dnsmasq**：把 IPv4 hosts 列表加入自定义 adlist（`/etc/dnsmasq.d/` 或 Pi-hole 的 adlist 页面）。
- **双栈网络**：`_dns.txt` 与 `_dns_ipv6.txt` 同时订阅，避免 IPv6 绕过。
- **仅需安全拦截**：只订阅「安全专项」。

> [!TIP]
> 国内直连 GitHub 慢时，统一改用 jsDelivr 列，订阅体验更稳。

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/build.svg" width="100%" alt="快速开始 · 本地构建"/>

```bash
pip install -r requirements.txt

# 完整版 + 类别拆分 + DNS + 冗余消除
python -m adblock_collection build --out dist --split-by-category --redundant

# 常用子命令
python -m adblock_collection sources               # 列出上游列表
python -m adblock_collection regression            # 误杀回归校验
python -m adblock_collection stats --out dist      # 仅刷新统计与 manifest
```

构建选项：`--no-dns`（不生成 DNS 文件）· `--offline`（仅用缓存）· `--no-cache`（禁用下载缓存）· `--dns-policy safe`（DNS 安全分级）。

缓存位于 `.cache/sources/` 与 `.cache/parsed/`，首次下载后离线可重建。

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/safety.svg" width="100%" alt="防误杀与审计体系"/>

### ├─ `[1]` DNS 安全分级 · dns_policy

DNS 规则在解析层生效、无法限定上下文，误杀代价最高，故分三档：

| 级别 | 行为 | 误杀风险 |
| :--- | :--- | :---: |
| ![all](https://img.shields.io/badge/all-default-ff9c39?style=flat-square&labelColor=0d0d0d) | 纳入所有纯域名网络规则 | 中 |
| ![safe](https://img.shields.io/badge/safe-00f0ff?style=flat-square&labelColor=0d0d0d) | 仅纯域名 + 带 `$third-party` 等修饰符规则 | 低 |
| ![strict-safe](https://img.shields.io/badge/strict--safe-39ff14?style=flat-square&labelColor=0d0d0d) | 仅最不易误杀的纯域名规则 | 最低 |

### ├─ `[2]` 误杀回归库 · regression

`config/false_positives.yaml` 内置 `40+` 主流站点（Google、百度、微信、支付宝、GitHub、银行电商）回归清单：
命中即 **构建失败（exit 1）**，防止误拦关键站点。

### ├─ `[3]` 质量门禁 · quality_gate

构建对比上一轮基线 `previous_metrics.json`，下列异常直接失败：
单源规则数骤降 `>50%` · 规则总量骤降 `>50%` · DNS 域名骤降 `>50%`。报告写入 `dist/build_report.json`。

### └─ `[4]` 来源血缘 · provenance

- `provenance.json`：每条规则记录来源、所属独立源组、置信度
  `conf = min(1.0, 0.5 + 0.1 × 独立源组数)`
- `relation_graph.json`：识别父子域冗余 / 跨源重复 / 阻断与例外冲突三类关系

> [!IMPORTANT]
> 三档分级与回归库共同构成发布闸门：任一校验失败，构建直接中止，不会产出有风险的新规则。

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/diy.svg" width="100%" alt="自定义上游 · DIY"/>

编辑 `config/sources.yaml`：

```yaml
sources:
  - name: My Custom List
    url: https://example.com/my-filter.txt
    category: network      # network / privacy / cookie / social / malware / phishing / mining / annoyance
    compatible: [adguard, abp, ubo]
    dns_policy:
      level: strict-safe   # all / safe / strict-safe
```

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/structure.svg" width="100%" alt="项目结构"/>

```
adblock_collection/
  rules.py        规则解析 · 规范化 · 分类 · 类型识别
  merge.py        上游下载 · 合并 · 去重 · badfilter · 冗余消除
  writer.py       多格式输出（adblock / hosts / domains / stats）
  dns_policy.py   DNS 安全分级
  regression.py   误杀回归校验
  quality_gate.py 质量门禁与基线
  pipeline.py     阶段缓存与算法版本常量
  provenance.py   来源血缘与语义关系图
  cli.py          命令行入口
config/
  sources.yaml            上游配置（dns_policy / quality_gate / security_policy）
  false_positives.yaml    误杀回归清单
tests/
  test_collection.py      单元与端到端测试
  test_relation_graph.py
.github/workflows/build.yml   每日自动构建并推送
```

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/warning.svg" width="100%" alt="警告"/>

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
