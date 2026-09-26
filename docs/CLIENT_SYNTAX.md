# 各客户端拦截规则语法

本文按客户端逐个说明**原生拦截语法**与**命中范围**，并给出本项目为每个客户端生成的产物写法。

相关文档分工：

- 过滤规则本身的语法语义（`||`、`^`、`$` 修饰符、元素隐藏、HTML 过滤、DNS 子集、优先级等）：见 `docs/SYNTAX.md`。
- 本项目每个产物的逐字语法与用法：见 `docs/GENERATED_RULES.md`。
- 客户端原生语法与算子差异（本文）。

本文覆盖 9 个客户端：浏览器扩展（ABP / uBO / AdGuard）、系统 hosts、dnsmasq、Pi-hole、AdGuard Home、mihomo / Clash Meta、sing-box、Surge、Quantumult X。

## 0. 一条主线：精确 vs 含子域

每个客户端都有两种算子，分别表达「只匹配域名本体」与「匹配域名及其所有子域」。本项目按域名来源选择算子：

| 来源语义 | 文本形态 | 命中范围 |
| :--- | :--- | :--- |
| 含子域 | `\|\|example.com^` | `example.com` 与 `*.example.com` |
| 精确 | hosts 行 / 纯域名行 | 仅 `example.com` 本体 |

同一域名同时存在两类来源时，按更宽的含子域语义处理。连接层规则集据此分别输出含子域算子与精确算子。

## 1. 跨客户端算子总表

| 客户端 | 精确（仅本体） | 含子域（本体 + 子域） | 仅子域（不含本体） |
| :--- | :--- | :--- | :--- |
| 浏览器扩展 | 无原生精确算子 | `\|\|example.com^` | 借助正则 `$` 限定 |
| 系统 hosts | `0.0.0.0 example.com` | 无（需逐条列出） | 无 |
| dnsmasq `addn-hosts` | `0.0.0.0 example.com` | 无（需逐条列出） | 无 |
| dnsmasq `address=` | 无 | `address=/example.com/0.0.0.0` | 无 |
| Pi-hole 域名条目 | `example.com` | 无（用 `*.example.com` 覆盖子域） | `*.example.com` |
| AdGuard Home | `example.com` / `0.0.0.0 example.com` | `\|\|example.com^` | `/regex/` |
| mihomo 规则 | `DOMAIN,example.com` | `DOMAIN-SUFFIX,example.com` | `DOMAIN-WILDCARD,*.example.com` |
| mihomo rule-provider | `example.com` | `+.example.com` | `.example.com` |
| sing-box | `{"domain": [...]}` | `{"domain_suffix": [...]}` | `domain_regex` |
| Surge 规则 | `DOMAIN,example.com` | `DOMAIN-SUFFIX,example.com` | `DOMAIN-WILDCARD,*.example.com` |
| Surge `DOMAIN-SET` | `example.com` | `.example.com` | 无 |
| Quantumult X | `host, example.com` | `host-suffix, example.com` | `host-wildcard, *.example.com` |

## 2. 浏览器扩展（ABP / uBO / AdGuard）

### 2.1 配置位置

自定义过滤列表 / 订阅。列表首行需要 `[Adblock Plus 2.0]`，uBO 与 AdGuard 同样接受。`!` 开头为注释。uBO / AdGuard 支持 `!#include` 递归引入分片。

### 2.2 拦截语法

| 写法 | 命中范围 |
| :--- | :--- |
| `\|\|example.com^` | `example.com` 与其所有子域 |
| `\|\|example.com/path/*` | 指定路径前缀 |
| `@@\|\|example.com^` | 例外（放行），优先于阻断 |
| `@@\|\|example.com^$document` | 整站放行（最高优先级） |
| `/regex/` | 与正则匹配的请求 |
| `example.com##selector` | CSS 隐藏元素（请求照常发出） |
| `example.com#@#selector` | 取消该站点的元素隐藏 |
| `example.com##+js(name, arg)` | 注入 scriptlet |
| `example.com#?#.ad:has-text(Ad)` | 过程式选择器 |
| `example.com##.ad:remove()` | 从 DOM 移除节点 |
| `example.com##^script:has-text(ad)` | HTML 过滤 |

`$` 后接资源类型与修饰符：`$script`、`$image`、`$third-party`、`$important`、`$removeparam`、`$redirect`、`$csp` 等，完整清单见 `docs/SYNTAX.md` §3、§4。

### 2.3 本项目产物

| 产物 | 内容 |
| :--- | :--- |
| `adblock_collection_full.txt` | 完整版（网络拦截 + 元素隐藏） |
| `adblock_collection_full_jsdelivr.txt` | 超出 jsDelivr 单文件上限时的 `!#include` 分片主链 |
| `adblock_collection_full_browser_network.txt` | 三层产物的扩展网络层 |
| `adblock_collection_full_cosmetic.txt` | 三层产物的扩展元素隐藏层 |
| `adblock_collection_ubo_enhance.txt` | uBO / AdGuard 高级增强层（`$redirect` / `$csp` / scriptlet 等） |

| 客户端 | 适配文件 |
| :--- | :--- |
| uBO / AdGuard（浏览器扩展）/ ABP | `adapters/browsers.md`（订阅地址与导入步骤） |

### 2.4 注意

- `\|\|example.com^` 会命中子域，是本层唯一的含子域形态。
- 全局元素隐藏 `##.ad` 会在每个站点持续扫描 DOM，限定域名 `site##.ad` 性能更好。
- 站点级例外（如 `@@\|\|ad-domain^$domain=...`）在 DNS 层没有页面上下文，导入 DNS 客户端前应改用 `full_dns.txt` 这类纯域名产物。

## 3. 系统 hosts

### 3.1 配置位置

- Windows：`C:\Windows\System32\drivers\etc\hosts`
- macOS / Linux：`/etc/hosts`
- Android：`/system/etc/hosts`（需 root）

### 3.2 拦截语法

| 写法 | 命中范围 |
| :--- | :--- |
| `0.0.0.0 example.com` | 仅 `example.com` 本体（IPv4 黑洞） |
| `:: example.com` | 仅 `example.com` 本体（IPv6 黑洞） |
| `127.0.0.1 example.com example.info` | 回环地址 + 可选别名 |

hosts 行只接受完整域名，不支持路径、修饰符与通配；`#` 起至行尾为注释。

### 3.3 本项目产物

| 产物 | 内容 |
| :--- | :--- |
| `adblock_collection_full_dns.txt` | `0.0.0.0 <domain>`，IPv4 |
| `adblock_collection_full_dns_ipv6.txt` | `:: <domain>`，IPv6 兜底 |
| `adapters/hosts.md` | 各系统路径与写入 / 刷新命令 |

### 3.4 注意

- hosts 行是**精确**语义，只命中域名本体，子域需要单独列出。
- 追加内容后需刷新 DNS 缓存（macOS：`sudo dscacheutil -flushcache`；Windows：`ipconfig /flushdns`）。
- 移除时删除追加段落即可。

## 4. dnsmasq

### 4.1 配置位置

`/etc/dnsmasq.d/*.conf` 或主配置文件。

### 4.2 拦截语法

| 写法 | 命中范围 |
| :--- | :--- |
| `addn-hosts=/path/hosts.txt` | 引用 hosts 文件，逐主机名**精确**命中 |
| `address=/example.com/0.0.0.0` | `example.com` 与其所有子域（返回 0.0.0.0） |
| `address=/example.com/#` | `example.com` 与其所有子域（返回 NXDOMAIN） |
| `local=/example.com/` | 该域及其子域不由上游解析 |
| `server=/example.com/1.1.1.1` | 该域及其子域改用指定上游 |

`address=` / `local=` / `server=` 的域名匹配是**后缀**语义，一次覆盖本体与全部子域；`addn-hosts` 是**精确**语义。

### 4.3 本项目产物

```ini
# adapters/dnsmasq.conf
addn-hosts=/etc/dnsmasq.d/adblock_collection_full_dns.txt
```

dnsmasq 不能直接拉取远程 URL，适配文件头部已给出先把 hosts 文件下载到本地路径的 `curl` 命令。拦截集合来自 `adblock_collection_full_dns.txt`。

### 4.4 注意

- 本项目用 `addn-hosts` 保留精确语义；改用 `address=/domain/0.0.0.0` 会扩大到全部子域，可能超出规则来源原本的拦截范围。
- 修改后重启 dnsmasq 生效。

## 5. Pi-hole

### 5.1 配置位置

- 本地允许 / 拒绝清单：Web 界面 Domains，或 `pihole allow` / `pihole deny`。
- 订阅列表：Web 界面 Adlists，或 `adlists.list`，每条一行列表 URL，由 `pihole -g`（gravity）下载并构建。

### 5.2 拦截语法

| 写法 | 类型 | 命中范围 |
| :--- | :--- | :--- |
| `example.com` | exact denylist | 仅 `example.com` 本体 |
| `*.example.com` | 通配 | 覆盖子域；需要主域时另加精确条目 |
| `^ads?[0-9]*\.example\.com$` | regex denylist | 按正则匹配 |
| `@@` 对应 allowlist | exact / regex allow | 放行 |

匹配优先级（从高到低）：exact allowlist > regex allowlist > exact denylist > 订阅 allowlist > 订阅 denylist > regex denylist。

### 5.3 本项目产物

| 产物 | 用法 |
| :--- | :--- |
| `adapters/pihole.txt` | 一行列表 URL，指向 `adblock_collection_full_dns.txt`（hosts，精确语义） |
| `dns_allow.txt` | 整域放行的纯域名清单，供 AdGuard Home / Pi-hole 的允许清单分组导入 |

### 5.4 注意

- 精确条目只匹配域名本体；需要覆盖子域时在 Pi-hole 侧自行使用 `*.example.com` 或正则。
- 大量失效域名会抬高内存占用，构建产物已在 `pihole -g` 前清理失效名。
- 修改后执行 `pihole -g` 重建数据库生效。

## 6. AdGuard Home

### 6.1 配置位置

`AdGuardHome.yaml` 的 `filters` 段（订阅列表），或 Web 界面的自定义过滤规则（Custom filtering rules）。AdGuard Home 同时接受 Adblock-style、`/etc/hosts`-style、Domains-only 三种写法。

### 6.2 拦截语法

Adblock-style（`filters` 与自定义规则均可用）：

| 写法 | 命中范围 |
| :--- | :--- |
| `\|\|example.org^` | `example.org` 与其所有子域 |
| `@@\|\|example.org^` | 放行该域及其子域 |
| `/REGEX/` | 与正则匹配的域名 |
| `*` | 通配任意字符集合 |
| `\|example` / `ample.org\|` | 主机名前缀 / 后缀锚点 |

`/etc/hosts`-style 与 Domains-only：

| 写法 | 命中范围 |
| :--- | :--- |
| `1.2.3.4 example.org` | 仅 `example.org` 本体；`0.0.0.0` / `127.0.0.1` 等同阻断 |
| `example.org` | 仅 `example.org` 本体；子域仍被放行 |
| `*.example.org` | 不是合法域名，AdGuard Home 会按 Adblock-style 规则处理 |

支持的 `$` 修饰符（DNS 语境）：`$important`、`$badfilter`、`$client`、`$denyallow`、`$dnstype`、`$dnsrewrite`、`$ctag`（仅 AdGuard Home）。出现未登记修饰符时，**整条规则被忽略**，这是为了隔离浏览器规则中的未知修饰符。

### 6.3 本项目产物

```yaml
# adapters/adguardhome.yaml（片段，合并进 AdGuardHome.yaml 的 filters 段）
filters:
  - enabled: true
    url: https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_domains.txt
    name: Adblock Collection (DNS domains)
```

该片段只含拦截列表，不含放行规则；需要放行时另行导入 `dns_allow.txt`。

### 6.4 注意

- Domains-only 产物（`adblock_collection_full_domains.txt`）与 hosts 行的命中都是**精确**（仅本体）。想获得含子域覆盖，用 Adblock-style 的 `\|\|domain^` 产物 `adblock_collection_full_dns_abp.txt`。
- `$dnsrewrite` 规则的优先级高于其余规则。
- 合并 `filters` 片段后重启 AdGuard Home 生效。

## 7. mihomo / Clash Meta

### 7.1 配置位置

`config.yaml` 的 `rules:` 段与 `rule-providers:` 段。

### 7.2 拦截语法

规则类型（`rules:` 内逐行）：

| 写法 | 命中范围 |
| :--- | :--- |
| `DOMAIN,example.com,REJECT` | 完整域名，精确 |
| `DOMAIN-SUFFIX,example.com,REJECT` | `example.com` 与其所有子域 |
| `DOMAIN-KEYWORD,ad,REJECT` | 域名包含关键字 |
| `DOMAIN-WILDCARD,*.example.com,REJECT` | 仅支持 `*`（零或多字符）与 `?`（恰好一字符） |
| `DOMAIN-REGEX,^abc.*com,REJECT` | 正则 |
| `GEOSITE,youtube,PROXY` | 引用 Geosite |
| `RULE-SET,adblock,REJECT` | 引用 rule-provider |
| `MATCH,PROXY` | 兜底 |

策略：`REJECT`（拒绝）、`REJECT-DROP`、`DIRECT`、`PROXY`、策略组名等。

rule-provider `behavior: domain` 的条目使用 Clash 通配符（与 `DOMAIN-WILDCARD` 的语义不同）：

| 条目 | 命中范围 |
| :--- | :--- |
| `example.com` | 精确，仅 `example.com` 本体 |
| `+.example.com` | `example.com` 与其所有子域（类似 `DOMAIN-SUFFIX`） |
| `.example.com` | 仅子域，不含 `example.com` 本体 |
| `*.example.com` | 仅一级子域，不含本体、不含更深层级 |
| `*` | 仅不含 `.` 的主机名（如 `localhost`） |

### 7.3 本项目产物

```yaml
# rulesets/adblock_clash.yaml（节选）
# rule-providers: { type: http, behavior: domain, format: yaml }
# Total Domains: 539586
payload:
  - '+.example.com'      # 含子域来源
  - 'exact.example.com'  # 精确来源
```

```yaml
# adapters/mihomo.yaml
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

### 7.4 注意

- `+.example.com` 覆盖本体与全部子域；裸 `example.com` 只覆盖本体。
- rule-provider 需配 `behavior: domain` 与 `format: yaml`。
- 把 `rule-providers` 与 `rules` 两段合并进 `config.yaml`，`path` 指向本地缓存位置。

## 8. sing-box

### 8.1 配置位置

`config.json` 的 `route.rules` 段与 `route.rule_set` 段。

### 8.2 拦截语法

| 字段 | 命中范围 |
| :--- | :--- |
| `domain` | 精确，仅该域名本体 |
| `domain_suffix` | 该域与其所有子域 |
| `domain_keyword` | 域名包含关键字 |
| `domain_regex` | 正则 |
| `geosite` | 引用 Geosite |
| `rule_set` | 引用规则集 |

规则集（rule-set）源格式为 JSON，`{"version": 3, "rules": [...]}` 需要 sing-box 1.11+；也可先用 `sing-box rule-set compile` 编译为 `.srs` 二进制，再用 `format: binary` 引用。

动作：`action: reject`（拒绝）、`route`、`hijack-dns` 等。

### 8.3 本项目产物

```json
// rulesets/adblock_singbox.json（源格式，version 3）
{"version": 3, "rules": [{"domain_suffix": ["example.com"]}, {"domain": ["exact.example.com"]}]}
```

```json
// adapters/singbox.json
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

### 8.4 注意

- `format: source` 免编译，需要 sing-box 1.11+。
- 远端规则集缓存依赖 `experimental.cache_file.enabled=true`；未开启时每次启动重新下载。
- `domain_suffix` 覆盖本体与子域；`domain` 只覆盖本体。

## 9. Surge

### 9.1 配置位置

`[Rule]` 段。

### 9.2 拦截语法

| 写法 | 命中范围 |
| :--- | :--- |
| `DOMAIN,example.com,REJECT` | 精确 |
| `DOMAIN-SUFFIX,example.com,REJECT` | 本体与其所有子域 |
| `DOMAIN-KEYWORD,ad,REJECT` | 域名包含关键字 |
| `DOMAIN-WILDCARD,*.example.com,REJECT` | 通配 |
| `DOMAIN-SET,<url或path>,REJECT,update-interval=86400` | 引用外部域名集 |
| `RULE-SET,<url或path>,REJECT` | 引用外部逐行规则集 |
| `IP-CIDR` / `GEOIP` / `FINAL` | IP 段 / 国家 / 兜底 |

`DOMAIN-SET` 文件（一行一个域名）：

| 条目 | 命中范围 |
| :--- | :--- |
| `example.com` | 精确，仅本体（等价 `DOMAIN`） |
| `.example.com` | 本体与其所有子域（等价 `DOMAIN-SUFFIX`） |

`DOMAIN-SET` 文件内 `#` 或 `//` 起为注释，空行忽略，非法行跳过；单集上限 1,000,000 条。`DOMAIN-SET` 与 `RULE-SET` 支持 `update-interval=<秒>`（默认 86400，负值关闭自动更新）。域名类规则支持 `extended-matching`（按 TLS SNI / HTTP Host 匹配）与 `pre-matching`（在 DNS 与 TCP 握手阶段即拒绝，需 `REJECT` 系策略）。

### 9.3 本项目产物

```ini
# adapters/surge.conf
DOMAIN-SET,https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_surge_domain_set.txt,REJECT,update-interval=86400
```

```text
# rulesets/adblock_surge_domain_set.txt（节选）
# Format: Surge DOMAIN-SET (.domain = domain + subdomains, bare = exact), total 539586
.example.com
exact.example.com
```

逐行规则集形态 `rulesets/adblock_surge.list` 为 `DOMAIN-SUFFIX,example.com,REJECT` / `DOMAIN,example.com,REJECT`，对应 `RULE-SET`，超限时拆分为 `adblock_surge_partNN.list`。

### 9.4 注意

- 推荐直接用 `DOMAIN-SET` 单文件：由 Surge 预建索引，单集上限 1,000,000 条，体积与匹配效率优于逐行 `RULE-SET`，且无需分片。
- 前导点表示本体加子域；裸域名表示精确。
- 同一个 URL 或文件不能同时作为 `RULE-SET` 与 `DOMAIN-SET` 引用。

## 10. Quantumult X

### 10.1 配置位置

`[filter_local]`（本地规则）与 `[filter_remote]`（远端规则集）。注释行以 `;`、`#` 或 `//` 开头。

### 10.2 拦截语法

本地过滤规则（`[filter_local]`）：

| 写法 | 命中范围 |
| :--- | :--- |
| `host, example.com, reject` | 精确，仅本体 |
| `host-suffix, example.com, reject` | 本体与其所有子域 |
| `host-keyword, adsite, reject` | 域名包含关键字 |
| `host-wildcard, *.example.com, reject` | 通配（`*`、`?`） |
| `user-agent, ?abc*, proxy` | 按 UA 匹配 |
| `ip-cidr` / `ip6-cidr` / `geoip` / `ip-asn` | IP 段 / 国家 / ASN |
| `final, proxy` | 兜底 |

策略：`reject`、`direct`、`proxy` 或策略组名；可加 `force-cellular`、`multi-interface`、`via-interface=...` 等网络限定。

远端过滤规则（`[filter_remote]`）：

```ini
filter_remote = <url>, tag=Adblock, force-policy=reject, enabled=true
```

参数 `tag`、`force-policy`、`enabled` 均可选。`force-policy` 使 Quantumult X 忽略远端资源内的策略，统一按指定策略处理。所有远端资源默认每 86400 秒同步一次，可用 `update-interval=<秒>` 调整（负值关闭自动同步）。

### 10.3 本项目产物

```ini
# rulesets/adblock_quanx.list（节选）
# Total Rules: 539586
host-suffix, example.com, reject
host, exact.example.com, reject
```

```ini
# adapters/quanx.conf
filter_remote = https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_quanx_part01.list, tag=Adblock-1, force-policy=reject, enabled=true
filter_remote = https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/rulesets/adblock_quanx_part02.list, tag=Adblock-2, force-policy=reject, enabled=true
```

### 10.4 注意

- `host-suffix` 覆盖本体与子域；`host` 只覆盖本体。
- Quantumult X 无 `!#include` 机制。远端规则集超出 jsDelivr 单文件上限时，镜像须逐一加入全部 `_partNN` 分片；完整文件的镜像 URL 会返回 403。可直连 GitHub raw 时，也可只引用完整单文件 `rulesets/adblock_quanx.list`。
- 分片与完整文件不要同时加入，避免重复匹配。

## 11. 陷阱与常见误用

- **精确 vs 含子域**：hosts 行、Domains-only 行、Pi-hole 精确条目都只命中域名本体；覆盖子域需要含子域算子或逐条列出。连接层规则集按来源分别输出，避免把精确来源放大为后缀。
- **AdGuard Home Domains-only**：`example.com` 只阻断本体，子域仍放行；需要子域覆盖时改用 `\|\|example.com^`（产物 `adblock_collection_full_dns_abp.txt`）。
- **mihomo 两套通配符**：rule-provider 的 Clash 通配符中 `*` 只匹配一级、`.` 不含本体、`+` 含本体；`DOMAIN-WILDCARD` 规则类型是另一套语义，二者不可混用。
- **dnsmasq 两种载体**：`addn-hosts` 精确，`address=/domain/` 后缀；选错会把精确来源放大为整域拦截。
- **Surge `DOMAIN-SET` 注释**：`#` 与 `//` 都算注释；前置点 `.domain` 表示含子域。
- **Quantumult X 分片**：镜像必须加入全部分片；`force-policy=reject` 使远端策略统一为 `reject`。
- **AdGuard Home 未知修饰符**：规则中出现未登记修饰符时整条被忽略，属于隔离机制。
- **浏览器站点级例外**：带 `$domain=` 等页面上下午的例外导入 DNS 客户端会变成整域放行；DNS 设备只导入纯域名产物。
- **DNS 缓存**：改动 hosts / dnsmasq / 各 DNS 服务后刷新缓存或重启服务再验证。

## 12. 相关文档

| 文档 | 内容 |
| :--- | :--- |
| `docs/SYNTAX.md` | 自定义过滤规则语法大全（ABP/uBO/AdGuard 通用与扩展语法、网络/内容/例外/行为修饰符、元素隐藏、HTML 过滤、DNS 子集、Pi-hole 正则、兼容性差异、优先级、自定义黑名单） |
| `docs/GENERATED_RULES.md` | 本项目生成产物的逐字语法与用法（含 `adapters/` 与订阅地址清单） |
| `docs/OPS.md` | 构建、配置源、白名单、门禁与源失效处置 |
| `docs/FLOW.md` | 构建流水线各阶段 |
