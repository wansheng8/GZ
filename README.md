# Adblock Rule Collection

一个将众多广告过滤规则**转化、去重、合并汇总**生成的广告拦截器与 DNS 过滤器生成工具。
规则总数可达百万级，覆盖 URL 过滤、资源过滤、域名过滤、CSS 选择器、脚本注入、隐私保护、
Cookie 过滤、白名单例外、关键字过滤、WebRTC 拦截、正则表达式、字体与样式、重定向拦截、
反指纹跟踪、欺诈/恶意/钓鱼/滥用拦截、挖矿拦截、僵尸网络屏蔽、地理位置追踪屏蔽、视音频广告、
社交媒体插件、点击劫持保护、弹窗/下载劫持保护等类型。

## 支持的语法与目标

- Adblock Plus 语法
- uBlock Origin 语法
- AdGuard 语法
- DNS / hosts 格式（供 AdGuard Home、Pi-hole、dnsmasq 等使用）

适用于 ADguard、Adblock Plus、uBlock Origin、Brave Browser 等符合上述语法的浏览器插件或广告拦截程序，以及 DNS 服务器。

## 警告

本过滤器订阅**有可能破坏某些网站的功能**，也有可能**封禁部分色情、赌博网站**。
使用前请斟酌考虑。如有误杀请积极向上游 issue 反馈，本仓库仅提供去重、转化、合并功能。

完整版会有较多误杀，建议使用**精简版**（只含 AdGuard 官方列表）。
本仓库仅收集中英文广告拦截相关、网络安全相关、隐私保护相关列表。

## 快速开始

```bash
pip install -r requirements.txt
python -m adblock_collection build --out dist
```

生成的文件位于 `dist/`：

- `adblock_collection_full.txt` — 完整版（Adblock Plus / AdGuard / uBO 语法）
- `adblock_collection_lite.txt` — 精简版（仅 AdGuard 官方列表，误杀风险低）
- `adblock_collection_full_dns.txt` / `adblock_collection_lite_dns.txt` — hosts 格式（`0.0.0.0 domain`），供 Pi-hole / dnsmasq
- `adblock_collection_full_domains.txt` / `adblock_collection_lite_domains.txt` — 单行域名格式，供 AdGuard Home / AdGuard DNS
- `*.stats.txt` — 人类可读分类统计
- `*.stats.json` — 机器可读统计（含 by_category 与 by_kind）

### 构建选项

```bash
python -m adblock_collection build --out dist        # 完整 + 精简 + DNS
python -m adblock_collection build --no-lite         # 不生成精简版
python -m adblock_collection build --no-dns          # 不生成 DNS/hosts/domains
python -m adblock_collection build --no-cache        # 禁用下载缓存
python -m adblock_collection build --offline         # 离线模式，仅使用缓存
python -m adblock_collection build --redundant       # 启用冗余域名规则消除
python -m adblock_collection sources                 # 列出当前配置的上游列表
```

缓存位于 `.cache/sources/`，首次下载后再次构建无需联网。

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
