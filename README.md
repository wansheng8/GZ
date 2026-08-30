# Adblock Rule Collection（广告规则合集）

> 一个将众多广告过滤规则**转化、去重、合并汇总**生成的广告拦截器与 DNS 过滤器生成工具。
> 规则总数可达百万级，覆盖 URL、资源、域名、CSS、脚本、隐私、Cookie、恶意/钓鱼/欺诈、挖矿等类型。

[![Build Filters](https://github.com/wansheng8/GZ/actions/workflows/build.yml/badge.svg)](https://github.com/wansheng8/GZ/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![GitHub repo](https://img.shields.io/badge/repo-wansheng8%2FGZ-lightgrey.svg)](https://github.com/wansheng8/GZ)

---

## 目录

- [支持的语法与目标](#支持的语法与目标)
- [规则类型](#规则类型)
- [警告](#警告)
- [快速开始](#快速开始)
- [订阅链接](#订阅链接)
- [自定义上游列表](#自定义上游列表-diy)
- [项目结构](#项目结构)
- [自动更新](#自动更新)
- [许可证](#许可证)

---

## 支持的语法与目标

| 语法 | 用途 |
| --- | --- |
| Adblock Plus 语法 | Adblock Plus、Brave 等浏览器插件 |
| uBlock Origin 语法 | uBlock Origin（uBO） |
| AdGuard 语法 | AdGuard 桌面/浏览器版 |
| DNS / hosts 格式 | AdGuard Home、Pi-hole、dnsmasq 等 DNS 服务 |

适用于 ADguard、Adblock Plus、uBlock Origin、Brave Browser 等符合上述语法的浏览器插件或广告拦截程序，以及 DNS 服务器。

## 规则类型

本工具汇总的规则覆盖以下类型（由上游列表共同提供，按类别自动统计）：

- URL 过滤、资源过滤、域名过滤
- CSS 选择器过滤、脚本注入、脚本过滤
- 隐私保护、Cookie 过滤、WebRTC 拦截、反指纹跟踪、地理位置追踪屏蔽
- 关键字过滤、正则表达式过滤、网络过滤、字体与样式过滤、重定向拦截
- 白名单例外、视音频广告过滤、社交媒体插件过滤、点击劫持保护、弹窗过滤、下载劫持保护
- 欺诈过滤、恶意网站过滤、网络钓鱼过滤、滥用过滤、挖矿过滤、垃圾邮件过滤、僵尸网络屏蔽

## 警告

本过滤器订阅**有可能破坏某些网站的功能**，也有可能**封禁部分色情、赌博网站**。
使用前请斟酌考虑。如有误杀请积极向上游 issue 反馈，本仓库仅提供去重、转化、合并功能。

完整版会有较多误杀，建议使用**精简版**（仅含 AdGuard 官方列表）。
本仓库仅收集中英文广告拦截相关、网络安全相关、隐私保护相关列表。

## 快速开始

```bash
pip install -r requirements.txt
python -m adblock_collection build --out dist
```

生成的文件位于 `dist/`：

| 文件 | 说明 |
| --- | --- |
| `adblock_collection_full.txt` | 完整版（Adblock Plus / AdGuard / uBO 语法） |
| `adblock_collection_lite.txt` | 精简版（仅 AdGuard 官方列表，误杀风险低） |
| `adblock_collection_full_dns.txt` / `_lite_dns.txt` | hosts 格式（`0.0.0.0 domain`），供 Pi-hole / dnsmasq |
| `adblock_collection_full_dns_ipv6.txt` / `_lite_dns_ipv6.txt` | Host IPv6 格式（`:: domain`） |
| `adblock_collection_full_domains.txt` / `_lite_domains.txt` | 单行域名格式，供 AdGuard Home / AdGuard DNS |
| `*.stats.txt` / `*.stats.json` | 分类统计（含 by_category / by_kind / by_source） |

DNS 类文件由网络规则自动提取主机名生成，覆盖 `||domain^` 与 `||domain/path^` 形式。

### 构建选项

```bash
python -m adblock_collection build --out dist        # 完整 + 精简 + DNS
python -m adblock_collection build --no-lite         # 不生成精简版
python -m adblock_collection build --no-dns          # 不生成 DNS/hosts/domains
python -m adblock_collection build --no-cache        # 禁用下载缓存
python -m adblock_collection build --offline         # 离线模式，仅使用缓存
python -m adblock_collection build --redundant       # 启用冗余域名规则消除
python -m adblock_collection build --split-by-category  # 按类型拆分生成子列表
python -m adblock_collection sources                 # 列出当前配置的上游列表（含 lite/full 标记）
```

缓存位于 `.cache/sources/`，首次下载后再次构建无需联网。

## 订阅链接

仓库每日 03:00 UTC 自动重新生成并推送 `dist/` 下的规则文件，以下链接长期有效。

- **Github 源**：`https://raw.githubusercontent.com/wansheng8/GZ/main/dist/<文件>`
- **CDN 加速（jsDelivr）**：`https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/<文件>`

### 完整版（规则多，有误杀风险）

| 过滤器类型 | Github | CDN 加速 |
| --- | --- | --- |
| 广告过滤器 | `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full.txt` | `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full.txt` |
| DNS 过滤器 | `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt` | `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt` |
| Host 列表 | `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt` | `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt` |
| Host IPv6 列表 | `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_ipv6.txt` | `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_ipv6.txt` |
| 拦截域名列表 | `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_domains.txt` | `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_domains.txt` |

### 精简版（仅 AdGuard 官方列表，推荐日常使用）

| 过滤器类型 | Github | CDN 加速 |
| --- | --- | --- |
| 广告过滤器 | `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_lite.txt` | `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_lite.txt` |
| DNS 过滤器 | `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_lite_dns.txt` | `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_lite_dns.txt` |
| Host 列表 | `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_lite_dns.txt` | `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_lite_dns.txt` |
| Host IPv6 列表 | `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_lite_dns_ipv6.txt` | `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_lite_dns_ipv6.txt` |
| 拦截域名列表 | `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_lite_domains.txt` | `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_lite_domains.txt` |

### 一键复制（Github 源，完整版）

```text
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full.txt
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_ipv6.txt
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_domains.txt
```

### 一键复制（Github 源，精简版）

```text
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_lite.txt
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_lite_dns.txt
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_lite_dns_ipv6.txt
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_lite_domains.txt
```

### 一键复制（CDN 加速，完整版）

```text
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_ipv6.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_domains.txt
```

### 一键复制（CDN 加速，精简版）

```text
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_lite.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_lite_dns.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_lite_dns_ipv6.txt
https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_lite_domains.txt
```

### 使用方式

- 浏览器插件（uBO / AdGuard / ABP）：设置 → 过滤器订阅 → 添加自定义列表，粘贴广告过滤器链接。
- AdGuard Home / Pi-hole：添加自定义规则列表，粘贴 DNS 过滤器 / Host 列表 / Host IPv6 列表 / 拦截域名列表链接。
- 国内访问缓慢时优先使用 CDN 加速（jsDelivr）链接。

## IPv4 / IPv6 拦截说明

本项目的 IPv4 / IPv6 拦截通过 **hosts 格式** 文件实现，而非 Adblock 语法规则。两类文件域名集合一致，区别仅在返回的记录类型（A 与 AAAA）。

### IPv4 拦截

文件：`adblock_collection_*_dns.txt`

```text
0.0.0.0 ads.example.com
0.0.0.0 tracker.example.com
```

原理：将广告/追踪域名指向 IPv4 黑洞地址 `0.0.0.0`，DNS 解析即返回该地址，连接被拒绝。供 Pi-hole、dnsmasq、AdGuard Home 等使用。

### IPv6 拦截

文件：`adblock_collection_*_dns_ipv6.txt`

```text
:: ads.example.com
:: tracker.example.com
```

原理：将域名指向 IPv6 黑洞地址 `::`（NXDOMAIN 效果），阻断 IPv6 环境下的解析。供支持 IPv6 的 DNS 服务使用。

### 覆盖范围与限制

- 两类文件仅从**纯域名网络阻断规则**（`||domain^`、`||domain/path^` 的主机名）提取，例外规则（`@@`）不进入列表。
- 覆盖域名过滤、DNS 过滤、Host 列表、恶意/钓鱼/挖矿/僵尸网络/欺诈/滥用等域名阻断类规则。
- 纯 CSS 隐藏、脚本注入、元素选择类规则**无法**转为 DNS 拦截（作用于页面内容而非域名解析层），仅出现在 `*.txt`（Adblock 语法）版本中。
- 双栈网络建议同时订阅 `_dns.txt` 与 `_dns_ipv6.txt`，避免仅拦截 IPv4 时域名通过 IPv6 绕过。

## 按类型拆分订阅

使用 `--split-by-category` 构建时，会在 `dist/` 下额外生成按类别拆分的子列表，文件名格式为 `adblock_collection_full_<类别>.txt`（及对应 `_dns.txt` / `_domains.txt` / `_dns_ipv6.txt`）。拆分基于**全局去重后的规则集**按 `category` 字段筛选，**不再二次去重**，因此拆分后的子列表并集仍等于完整版。

可用类别（由上游分类与关键字启发式得出）：`network`、`privacy`、`cookie`、`social`、`malware`、`phishing`、`mining`、`annoyance`、`whitelist`、`css`、`scriptlet`、`redirect`、`regexp`、`other`。

适用场景：只想订阅高置信度类别（如 `malware`、`phishing`、`mining`）的用户，可绕过完整版的误杀风险。

## 自定义上游列表（DIY）

编辑 `config/sources.yaml`，按如下结构添加或删除上游列表（兼容 Adblock Plus 语法的过滤器列表均可）：

```yaml
sources:
  - name: My Custom List
    url: https://example.com/my-filter.txt
    category: network      # 分类，用于统计与拆分
    compatible: [adguard, abp, ubo]
    lite: false            # true 表示纳入精简版
```

字段说明：

- `name`：列表名称
- `url`：原始过滤器列表地址
- `category`：类别（network / privacy / cookie / social / malware / phishing / mining / annoyance / whitelist / other）
- `compatible`：兼容的语法
- `lite`：`true` 时该列表会进入精简版生成

## 项目结构

```
adblock_collection/
  rules.py     # 规则解析、规范化、分类、类型识别
  merge.py     # 上游下载（带缓存/离线）、合并、去重、badfilter、冗余消除、统计
  writer.py    # 多格式输出（adblock / hosts / domains / stats / json）
  cli.py       # 命令行入口（build / sources）
config/
  sources.yaml # 上游列表配置
tests/
  test_collection.py  # 单元测试
.github/workflows/build.yml  # 每日自动构建并推送
```

> 注意：将 `config/sources.yaml` 中的 `name`/`url` 改为你自己的上游，
> 订阅主页已指向 `https://github.com/wansheng8/GZ`。

## 自动更新

仓库通过 GitHub Actions 每日 03:00 UTC 自动重新生成并推送 `dist/` 下的规则文件，
也可在 Actions 页面手动触发。

## 许可证

MIT
