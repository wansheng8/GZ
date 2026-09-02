<div align="center">

# Adblock Rule Collection

**广告拦截 · DNS 过滤 · 安全防护** 一站式规则合集生成器

将 60+ 上游列表**转化 · 去重 · 合并**为百万级广告拦截与 DNS 过滤规则，
覆盖 URL / 域名 / CSS / 脚本 / 隐私 / Cookie / 恶意 / 钓鱼 / 挖矿等类型。

[![Build](https://github.com/wansheng8/GZ/actions/workflows/build.yml/badge.svg)](https://github.com/wansheng8/GZ/actions/workflows/build.yml)
[![Rules](https://img.shields.io/badge/Total_Rules-968,349-brightgreen)](dist/adblock_collection_full.txt)
[![DNS](https://img.shields.io/badge/DNS_Domains-491,021-blue)](dist/adblock_collection_full_dns.txt)
[![Sources](https://img.shields.io/badge/Upstream-60_sources-purple)](config/sources.yaml)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Update](https://img.shields.io/badge/Update-Daily-ff9c39)]()

---

**「宁愿少拦截，不要误拦截」** — 内置 DNS 安全分级、误杀回归库与质量门禁，构建失败自动中止发布。

</div>

---

## 订阅中心

仓库每日 `03:00 UTC` 自动构建并推送，**订阅一次、自动更新**，链接长期有效。
下面链接均可**直接点击跳转订阅地址**，在过滤工具里粘贴该地址即可（或用右键复制链接）。

| 订阅 | GitHub 源（点击即得） | jsDelivr CDN 加速 |
| --- | --- | --- |
| **浏览器专用**（uBO / AdGuard / ABP，一条覆盖广告+隐私+安全） | https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full.txt | https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full.txt |
| **DNS · IPv4 hosts**（AdGuard Home / Pi-hole / dnsmasq） | https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt | https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt |
| **DNS · IPv6 hosts**（双栈再补订阅这一条） | https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_ipv6.txt | https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_ipv6.txt |
| **单行域名列表**（AdGuard DNS 等域名格式） | https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_domains.txt | https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_domains.txt |
| **安全专项**（恶意 + 钓鱼，误杀风险低，可选） | https://raw.githubusercontent.com/wansheng8/GZ/main/dist/security/adblock_collection_security.txt | https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/security/adblock_collection_security.txt |

**三步上手**
1. 按你的设备选一行（浏览器选第 1 条，DNS 设备选第 2~4 条）。
2. 点击链接复制地址（国内访问慢换 CDN 列）。
3. 在你的过滤工具里「添加自定义过滤列表」并粘贴。

> 仅需安全拦截：单独订阅「安全专项」行即可，绕过完整版的误杀风险。

---

## 当前规模

| 指标 | 数值 | 说明 |
| --- | ---: | --- |
| 完整版规则 | **968,349** | 网络 / CSS / 脚本 / HTML 全部类型 |
| DNS 域名 | **491,021** | 从纯域名网络规则自动提取 |
| 上游源 | **60** | 全部在线健康（failed = 0） |
| 跨源重复消除 | **33.8 万+** | 去重合并后的唯一规则集 |

### 规则类型构成

| 类型 | 条数 | 说明 |
| --- | ---: | --- |
| `network` | 816,523 | 域名 / URL / 资源请求阻断 |
| `css` | 140,866 | CSS 元素隐藏 |
| `scriptlet` | 10,775 | 脚本注入 / 反绕过 |
| `html` | 184 | HTML 过滤 |
| `js` | 1 | 脚本规则 |

### 按类别拆分（构建 `--split-by-category` 产物）

| 类别 | 条数 | 订阅文件（`dist/adblock_collection_full_<类别>.txt`） |
| --- | ---: | --- |
| `network` | 754,670 | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_network.txt) |
| `privacy` | 87,176 | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_privacy.txt) |
| `phishing` | 38,465 | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_phishing.txt) |
| `annoyance` | 31,088 | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_annoyance.txt) |
| `cookie` | 24,189 | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_cookie.txt) |
| `whitelist` | 13,773 | 例外规则（仅供审计） |
| `social` | 13,563 | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_social.txt) |
| `malware` | 5,415 | [订阅](https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_malware.txt) |
| `mining` | — | 当前无独立规则 |

> 每个类别均附带 `_dns.txt` / `_dns_ipv6.txt` / `_domains.txt` 版本。
> 只想订阅安全类别（malware / phishing / mining）时，可绕过完整版的误杀风险。

---

## 特性

| | 能力 | 说明 |
| --- | --- | --- |
| **01** | 多语法支持 | Adblock Plus / uBlock Origin / AdGuard / hosts / domains 全格式输出 |
| **02** | 分类发行 | 完整版 + 按类别拆分 + 安全类独立目录 |
| **03** | 防误杀体系 | DNS 三档安全分级 + 误杀回归库 + 质量门禁 |
| **04** | 来源血缘审计 | `provenance.json` 记录每条规则来源与置信度 |
| **05** | 阶段缓存 | 源内容 sha256 + 算法版本，增量构建秒级完成 |
| **06** | 自动更新 | GitHub Actions 每日 03:00 UTC 自动重建推送 |

---

## 使用指南

去上方 [订阅中心](#订阅中心) 表格按设备点选即可，常见软件入口：

- **uBlock Origin**：`设置 → 过滤规则列表 → 用户自定义 → 导入`，粘贴浏览器专用链接。
- **AdGuard（App / 桌面版）**：`设置 → 内容拦截 → 过滤器 → 自定义过滤器 → 添加过滤器`，粘贴链接。
- **AdGuard Home**：`过滤器 → DNS 拦截清单 → 添加拦截清单`，粘贴 DNS hosts 或域名列表链接。
- **Pi-hole / dnsmasq**：把 IPv4 hosts 列表加入自定义 adlist（`/etc/dnsmasq.d/` 或 Pi-hole 的 adlist 页面）。
- **双栈网络**：`_dns.txt` 与 `_dns_ipv6.txt` 同时订阅，避免 IPv6 绕过。
- **仅需安全拦截**：只订阅「安全专项」。

---

## 快速开始（本地构建）

```bash
pip install -r requirements.txt

# 完整版 + 类别拆分 + DNS + 冗余消除
python -m adblock_collection build --out dist --split-by-category --redundant

# 常用子命令
python -m adblock_collection sources               # 列出上游列表
python -m adblock_collection regression            # 误杀回归校验
python -m adblock_collection stats --out dist      # 仅刷新统计与 manifest
```

构建选项：`--no-dns`（不生成 DNS 文件）、`--offline`（仅用缓存）、`--no-cache`（禁用下载缓存）、`--dns-policy safe`（DNS 安全分级）。

缓存位于 `.cache/sources/` 与 `.cache/parsed/`，首次下载后离线可重建。

---

## 防误杀与审计体系

### DNS 安全分级（dns_policy）

DNS 规则在解析层生效、无法限定上下文，误杀代价最高，故分三档：

| 级别 | 行为 | 误杀风险 |
| --- | --- | --- |
| `all`（默认） | 纳入所有纯域名网络规则 | 中 |
| `safe` | 仅纯域名 + 带 `$third-party` 等修饰符规则 | 低 |
| `strict-safe` | 仅最不易误杀的纯域名规则 | 最低 |

### 误杀回归库（regression）

`config/false_positives.yaml` 内置 40+ 主流站点（Google、百度、微信、支付宝、GitHub、银行电商）回归清单：
命中即构建失败（exit 1），防止误拦关键站点。

### 质量门禁（quality_gate）

构建对比上一轮基线 `previous_metrics.json`，下列异常直接失败：
单源规则数骤降 >50%、规则总量骤降 >50%、DNS 域名骤降 >50%。报告写入 `dist/build_report.json`。

### 来源血缘（provenance）

- `provenance.json`：每条规则记录来源、所属独立源组、置信度
  `conf = min(1.0, 0.5 + 0.1 × 独立源组数)`
- `relation_graph.json`：识别父子域冗余 / 跨源重复 / 阻断与例外冲突三类关系

---

## 自定义上游（DIY）

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

---

## 项目结构

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

---

## 警告

> [!CAUTION]
> 本过滤器**可能破坏某些网站功能**，或**阻断部分成人 / 赌博站点**。
> 如有误杀，请向上游列表反馈；本仓库仅提供去重、转化、合并，不参与内容判定。

---

## 许可证

[MIT](LICENSE)
