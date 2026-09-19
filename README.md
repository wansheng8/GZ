<div align="center">

<img src="assets/banner.svg" width="100%" alt="Adblock Rule Collection — 广告拦截 · DNS 过滤 · 安全防护"/>

<br/>

[![Build](https://github.com/wansheng8/GZ/actions/workflows/build.yml/badge.svg)](https://github.com/wansheng8/GZ/actions/workflows/build.yml)
[![Rules](https://img.shields.io/badge/Total_Rules-781%2C390-ff00e5?style=for-the-badge&labelColor=0d0d0d)](dist/adblock_collection_full.txt)
[![DNS](https://img.shields.io/badge/DNS_Domains-543%2C196-00f0ff?style=for-the-badge&labelColor=0d0d0d)](dist/adblock_collection_full_dns.txt)
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

## 三层防护总览

按“拦截发生在哪一层”分工，三层互补，任何一个都不完整：

| 层级 | 能力 | 适用规则类型 | 生效范围 | 局限 |
| :--- | :--- | :--- | :--- | :--- |
| **DNS 拦截** | 域名解析阶段直接阻断，广告域名拿不到 IP | hosts / 纯域名 / `\|\|domain^` | 局域网**全部设备**（电脑 / 手机 / TV） | 只能拦**整域**；无法匹配路径、资源类型、页面元素 |
| **扩展 · 网络拦截** | 浏览器**请求发起前**阻断，可限定路径 / 资源类型 / 第三方 | ABP `\|\|domain/path*$` 修饰符规则 | 仅**装了扩展的浏览器** | 仅浏览器内生效；无法隐藏已加载的 DOM |
| **扩展 · 元素隐藏** | 页面加载后用 CSS / 脚本隐藏、移除广告 DOM | `##` / `#?#` / `##+js(...)` | 仅**装了扩展的浏览器** | 资源已经下载，仍消耗流量；不能阻止请求 |

> 一句话分工：**DNS 全局减负 → 网络拦截精细阻断 → 元素隐藏清理第一方与动态广告。**
> DNS 层**只能**处理整域，浏览器层**才能**处理路径、脚本与页面元素。

> [!CAUTION]
> DNS 黑名单里**绝对不能**出现 `##`、`#?#`、`##+js`、`$xxx` 修饰符——DNS 系统不认识，轻则丢弃规则，重则整份清单失效。这类规则**只放进浏览器扩展**。
> 本仓库的 `_dns.txt` / `_dns_ipv6.txt` / `_domains.txt` 由构建流程保证只含纯域名，并有回归测试固定该不变量。
> `#?#` 与 `##+js(...)` 由 uBlock Origin / AdGuard 支持，Adblock Plus 支持有限；只使用 Adblock Plus 时优先选基础 `##` 规则。

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/subscribe.svg" width="100%" alt="订阅中心"/>

每日 `03:00 UTC` 自动构建 · **订阅一次，自动更新** · 链接长期有效

| 层 | 订阅包 | 适用工具 | 一键导入 |
| :--: | :--- | :--- | :--- |
| **DNS** | **`[IPv4 hosts]`** 设备级拦截 | AdGuard Home · Pi-hole · dnsmasq · 路由器 hosts | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-00f0ff?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt) |
| **DNS** | **`[IPv6 hosts]`** 双栈补订 | 同上（IPv6 环境） | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_ipv6.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-9d00ff?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_ipv6.txt) |
| **DNS** | **`[单行域名]`** 纯域名格式 | AdGuard DNS · AdGuard Home 自定义黑名单 | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_domains.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-ff9c39?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_domains.txt) |
| **DNS 等价** | **`[域名规则]`** `\|\|domain^` | 浏览器扩展 · AdGuard Home 自定义规则 | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_abp.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-39ff14?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_abp.txt) |
| **扩展网络** | **`[网络拦截层]`** 请求阻断 | uBlock Origin · AdGuard · AdBlock Plus | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_browser_network.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-c70f0f?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_browser_network.txt) |
| **扩展元素隐藏** | **`[元素隐藏层]`** CSS + 脚本 | uBlock Origin · AdGuard | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_cosmetic.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-9d00ff?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_cosmetic.txt) |
| **浏览器全量** | **`[浏览器专用]`** 网络 + 元素隐藏 | uBlock Origin · AdGuard · AdBlock Plus | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-ff00e5?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_jsdelivr.txt) |
| **安全** | **`[安全专项]`** 恶意 + 钓鱼 · 低误杀 | 只需安全拦截的设备 | [![订阅 GitHub](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/security/adblock_collection_security.txt) [![订阅 jsDelivr](https://img.shields.io/badge/%E8%AE%A2%E9%98%85-jsDelivr-39ff14?style=for-the-badge&logo=jsdelivr&logoColor=white)](https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/security/adblock_collection_security.txt) |

```console
>_ 按层选文件
  DNS 设备    -> 第 1~3 行选一（IPv4 / IPv6 / 单行域名，内容等价）
  浏览器扩展  -> 第 5~7 行：要分层就分别装「网络拦截层 + 元素隐藏层」，图省事就装「浏览器专用」
  只想不搭 DNS 又想要域名级全局 -> 第 4 行「域名规则」，浏览器可直接导入
```

> [!TIP]
> 仅需安全拦截：单独订阅「安全专项」行即可，绕过完整版的误杀风险。
> 国内直连 GitHub 慢时，统一改用 jsDelivr 列，订阅体验更稳。

> [!IMPORTANT]
> **DNS 端只导入一个文件**：AdGuard Home / Pi-hole 等 DNS 设备在「IPv4 hosts」「IPv6 hosts」「单行域名」「域名规则」中**选一个**并**只保留这一个**——不要同时导入「浏览器专用」「网络拦截层」「元素隐藏层」。
>
> 原因：浏览器列表里有约 2,500 条 `@@||ad-domain^$domain=...` 形式的站点级例外（`@@||ads.taboola.com^`、`@@||pagead2.googlesyndication.com^$domain=...`、`@@||doubleclick.net^$xhr,domain=...` 等）。DNS 层没有页面上下文，这些例外会被当作**域名级放行**，直接抵消对应广告域的封锁，于是出现「导得越多、拦得越少 / 以前能拦现在拦不了」。
>
> **浏览器版 jsDelivr 分片**：GitHub 链接始终是单文件完整版；jsDelivr 链接是 `!#include` 分片主链（完整版单文件约 24MB，超过 jsDelivr 单文件 20MB 上限会返回 403，故自动拆分，uBlock Origin / AdGuard 会跟随分片）。若「网络拦截层」日后增长超过 20MB，jsDelivr 链接会 403，此时改用 `adblock_collection_full_browser_network_jsdelivr.txt` 主链。
>
> **导入 DNS 列表后仍不拦截时**，先确认域名解析确实经过该 DNS：`nslookup doubleclick.net <你的 AdGuard Home/Pi-hole 地址>` 应返回 `0.0.0.0` 或 NXDOMAIN。若返回真实 IP，说明设备/浏览器走了 DoH（如 Chrome/系统「安全 DNS」），请关闭 DoH 后再测。

<details>
<summary><code>纯文本订阅链接</code></summary>

```text
[DNS · IPv4 hosts]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt

[DNS · IPv6 hosts]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_ipv6.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_ipv6.txt

[DNS · 单行域名]
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

[安全专项]
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/security/adblock_collection_security.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/security/adblock_collection_security.txt
```

</details>

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/scale.svg" width="100%" alt="当前规模"/>

<div align="center">

<img src="assets/stats.svg" width="100%" alt="781,390 rules · 543,196 domains · 60 sources · 33.8万+ deduplicated"/>

</div>

### ├─ 规则类型构成

| 类型 | 数量 | 说明 | 归属层 |
| :--- | :--- | :--- | :--- |
| ![network](https://img.shields.io/badge/network-627%2C294-00f0ff?style=flat-square&labelColor=0d0d0d) | 627,294 | 域名 / URL / 资源请求阻断 | 网络拦截（DNS 从中提取纯域名） |
| ![css](https://img.shields.io/badge/css-141%2C193-ff9c39?style=flat-square&labelColor=0d0d0d) | 141,193 | CSS 元素隐藏 | 元素隐藏 |
| ![scriptlet](https://img.shields.io/badge/scriptlet-10%2C802-ff00e5?style=flat-square&labelColor=0d0d0d) | 10,802 | 脚本注入 / 反绕过 | 元素隐藏 |
| ![html](https://img.shields.io/badge/html-187-9d00ff?style=flat-square&labelColor=0d0d0d) | 187 | HTML 过滤 | 元素隐藏 |
| ![js](https://img.shields.io/badge/js-1-39ff14?style=flat-square&labelColor=0d0d0d) | 1 | 脚本规则 | 元素隐藏 |

### ├─ 按类别拆分 · `--split-by-category`

| 类别 | 订阅文件 `dist/adblock_collection_full_<类别>.txt` |
| :--- | :--- |
| ![network](https://img.shields.io/badge/network-602%2C222-00f0ff?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_network.txt) |
| ![privacy](https://img.shields.io/badge/privacy-48%2C814-9d00ff?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_privacy.txt) |
| ![phishing](https://img.shields.io/badge/phishing-36%2C678-ff2e63?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_phishing.txt) |
| ![annoyance](https://img.shields.io/badge/annoyance-30%2C758-ff9c39?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_annoyance.txt) |
| ![cookie](https://img.shields.io/badge/cookie-24%2C194-b14dff?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_cookie.txt) |
| ![whitelist](https://img.shields.io/badge/whitelist-13%2C784-7a7a9a?style=flat-square&labelColor=0d0d0d) | 例外规则（仅供审计） |
| ![social](https://img.shields.io/badge/social-13%2C526-ff00e5?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_social.txt) |
| ![malware](https://img.shields.io/badge/malware-9%2C491-ff3b30?style=flat-square&labelColor=0d0d0d) | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_malware.txt) |
| ![css](https://img.shields.io/badge/css-10-7a7a9a?style=flat-square&labelColor=0d0d0d) | 本地增强元素隐藏规则 |

> [!NOTE]
> 每个类别均附带 `_dns.txt` / `_dns_ipv6.txt` / `_domains.txt` 版本。
> 按类别拆分（来源维度）与按规则类型分层（网络 / 元素隐藏维度）互补，可组合订阅。

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/features.svg" width="100%" alt="特性"/>

| | 能力 | 说明 |
| :--: | :--- | :--- |
| ![01](https://img.shields.io/badge/01-00f0ff?style=for-the-badge&labelColor=0d0d0d) | **三层分层发行** | DNS / 扩展网络拦截 / 扩展元素隐藏，按规则类型拆分，各层职责单一 |
| ![02](https://img.shields.io/badge/02-ff00e5?style=for-the-badge&labelColor=0d0d0d) | **多语法支持** | Adblock Plus / uBlock Origin / AdGuard / hosts / domains / `\|\|domain^` 全格式输出 |
| ![03](https://img.shields.io/badge/03-9d00ff?style=for-the-badge&labelColor=0d0d0d) | **分类发行** | 完整版 + 按类别拆分 + 安全类独立目录 |
| ![04](https://img.shields.io/badge/04-39ff14?style=for-the-badge&labelColor=0d0d0d) | **防误杀体系** | DNS 三档安全分级 + 误杀回归库 + 质量门禁 |
| ![05](https://img.shields.io/badge/05-ff9c39?style=for-the-badge&labelColor=0d0d0d) | **来源血缘审计** | `provenance.json` 记录每条规则来源与置信度 |
| ![06](https://img.shields.io/badge/06-00ffd0?style=for-the-badge&labelColor=0d0d0d) | **自动更新** | GitHub Actions 每日 03:00 UTC 自动重建推送 |

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/guide.svg" width="100%" alt="使用指南"/>

去上方「订阅中心」表格按层点选，常见软件入口：

- **AdGuard Home**：`过滤器 → DNS 拦截清单` 添加 DNS 层文件；`过滤器 → 自定义规则` 可加「域名规则」层。
- **Pi-hole / dnsmasq**：把 IPv4 hosts 列表加入自定义 adlist（`/etc/dnsmasq.d/` 或 Pi-hole 的 adlist 页面）。
- **双栈网络**：`_dns.txt` 与 `_dns_ipv6.txt` 同时订阅，避免 IPv6 绕过。
- **uBlock Origin**：`设置 → 过滤规则列表 → 用户自定义 → 导入`，分层装「网络拦截层 + 元素隐藏层」，或直接装「浏览器专用」。
- **AdGuard（App / 桌面版）**：`设置 → 内容拦截 → 过滤器 → 自定义过滤器 → 添加过滤器`，同上按层添加。
- **仅需安全拦截**：只订阅「安全专项」。

### ├─ 三层验证流程（tryblock / d3ward）

1. 浏览器开**无痕窗口**并清缓存，避免旧缓存干扰。
2. **验证 DNS 层**：`nslookup doubleclick.net <DNS地址>` 应返回 `0.0.0.0` / NXDOMAIN；AdGuard Home / Pi-hole 日志应出现被拦截记录。
3. **验证网络层**：看扩展日志，广告脚本、iframe、XHR 请求显示被 block。
4. **验证元素隐藏层**：页面上的动态广告块、反广告弹窗被隐藏或移除。

> [!NOTE]
> tryblock / d3ward 的测试项里，**元素隐藏、脚本、脚本注入占多数，DNS 层天然无法拦截**。用 DNS 列表去测这些站点得分偏低属预期；DNS 是否生效看广告网络域名（`googlesyndication.com`、`doubleclick.net`、`an.yandex.ru`）能否解析。

<img src="assets/divider.svg" width="100%" alt=""/>

<img src="assets/sections/build.svg" width="100%" alt="快速开始 · 本地构建"/>

```bash
pip install -r requirements.txt

# 完整版 + 类别拆分 + 三层产物 + DNS（规则增强默认开启）
python -m adblock_collection build --out dist --split-by-category

# 常用子命令
python -m adblock_collection sources               # 列出上游列表
python -m adblock_collection regression            # 误杀回归校验
python -m adblock_collection stats --out dist      # 仅刷新统计与 manifest
```

构建选项：`--no-dns`（不生成 DNS 与「域名规则」文件）· `--offline`（仅用缓存）· `--no-cache`（禁用下载缓存）· `--dns-policy safe`（DNS 安全分级）· `--no-alias-normalize` / `--no-resolve-conflicts` / `--no-per-rule-classify` / `--no-domain-fold`（分别关闭四项规则增强，默认开启）。

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

`config/false_positives.yaml` 内置主流站点（Google、百度、微信、支付宝、GitHub、银行电商）回归清单：
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
  writer.py       多格式输出（adblock / hosts / domains / ||domain^ / stats）
  dns_policy.py   DNS 安全分级
  regression.py   误杀回归校验
  quality_gate.py 质量门禁与基线
  pipeline.py     阶段缓存与算法版本常量
  provenance.py   来源血缘与语义关系图
  cli.py          命令行入口（含三层产物编排）
config/
  sources.yaml            上游配置（dns_policy / quality_gate / security_policy）
  false_positives.yaml    误杀回归清单
tests/
  test_collection.py      单元与端到端测试
  test_relation_graph.py
.github/workflows/build.yml   每日自动构建并推送
```

生成的产物：`dist/adblock_collection_full.txt`（浏览器全量）、`_browser_network.txt`（网络拦截层）、`_cosmetic.txt`（元素隐藏层）、`_dns_abp.txt`（DNS 等价域名规则）、`_dns.txt` / `_dns_ipv6.txt` / `_domains.txt`（DNS 层）。

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
