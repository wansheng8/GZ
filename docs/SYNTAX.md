# 自定义过滤规则语法大全

本文是各广告拦截软件**自定义过滤规则语法**的综合参考，覆盖通用基础语法、网络/内容/例外/行为修饰符、元素隐藏、HTML 过滤与脚本注入、DNS 子集与 Pi-hole 正则，以及三家引擎（ABP / uBO / AdGuard）的兼容性差异。它既是使用说明，也是贡献规则时的对照表。

文档分工：

- 本项目每个生成产物（adblock / hosts / domains / rulesets / manifest 等）的逐字语法与用法：见 `docs/GENERATED_RULES.md`。
- 各客户端原生拦截语法与命中范围（精确 / 含子域算子差异）：见 `docs/CLIENT_SYNTAX.md`。
- 构建、配置、排障流程：见 `docs/OPS.md`；流水线阶段：见 `docs/FLOW.md`。

## 1. 总览：各软件使用的语法体系

| 软件 | 语法体系 | 特点 |
| :--- | :--- | :--- |
| Adblock Plus (ABP) | EasyList 语法（源头标准） | 网络规则 + 元素隐藏 + 片段过滤器 |
| uBlock Origin (uBO) | 兼容 EasyList 大部分，另有大量扩展 | 性能导向，独有 scriptlet、HTML 过滤、预解析指令、`$to` / `$top` / `$ipaddress` |
| AdGuard（扩展 / 桌面 / 移动） | 基于 ABP 语法，扩展最多 | 独有 `$app`、`$stealth`、HTML/JS 规则、扩展 CSS 库 |
| AdGuard Home / AdGuard DNS | Adblock 语法的 DNS 子集 | `$dnsrewrite`、`$client`、`$dnstype`、`$ctag` |
| Pi-hole | 精确域名 + POSIX ERE 正则（带扩展关键字） | `;querytype=`、`;reply=`、`;invert` |
| mihomo / sing-box / Surge / Quantumult X | 各客户端自有的路由规则语法 | 见 `docs/CLIENT_SYNTAX.md` |

## 2. 三层防护与产物对应

| 层 | 生效位置 | 产物 | 能表达的语法 |
| :--- | :--- | :--- | :--- |
| 网络层 | 浏览器扩展 | `adblock_collection_full_browser_network.txt` | `\|\|` 域名/URL 匹配、`$` 资源类型与修饰符、`@@` 例外 |
| 元素层 | 浏览器扩展 | `adblock_collection_full_cosmetic.txt` | `##` 隐藏、`#@#` 取消隐藏、scriptlet、过程式选择器、HTML 过滤 |
| 增强层 | uBO / AdGuard | `adblock_collection_ubo_enhance.txt` | `$redirect`/`$csp`/`$removeparam` 等网络修饰符，以及 `##+js`/`#?#`/`:remove()`/`#$#`/`##^` |
| DNS 层 | AdGuard Home / Pi-hole / hosts | `_dns.txt`、`_domains.txt`、`dns_allow.txt` | 只能表达整域拦截/放行，单行一个域名 |
| 连接层 | mihomo / sing-box / Surge / Quantumult X | `rulesets/adblock_clash.yaml`、`adblock_singbox.json`、`adblock_surge.list`、`adblock_quanx.list` | 与 DNS 域名集合同源；按来源分别用含子域算子（`DOMAIN-SUFFIX`/`domain_suffix`/`host-suffix`）与精确算子（`DOMAIN`/`domain`/`host`）；TUN 模式按 TLS/QUIC SNI 匹配域名拒绝，可穿透 App 的 HTTPDNS / IP 直连 |

浏览器扩展兼容性：`full` 与 `_browser_network` / `_cosmetic` 以 ABP 通用子集为主，同时收录 uBO/AdGuard 扩展语法（ABP 会忽略无法识别的行）；增强层单独成文件，供支持高级能力的扩展订阅。

## 3. 通用基础语法（ABP / uBO / AdGuard 共享）

```text
rule = ["@@"] pattern ["$" modifiers]
```

| 符号 | 含义 | 示例 |
| :--- | :--- | :--- |
| `\|\|` | 域名锚点：匹配域名开头（含子域、任意协议），`testexample.org` 不命中 | `\|\|example.org^` |
| `^` | 分隔符：域名结束位置或除字母/数字/`_`/`-`/`.`/`%` 外的任意字符，也匹配 URL 结尾 | `\|\|ads.example.com^` |
| `\|` | 地址开头/结尾锚点 | `\|http://example.com/\|`、`swf\|` |
| `*` | 通配符，任意字符（含空串） | `/banner/*/img` |
| `@@` | 例外规则前缀 | `@@\|\|example.com^` |
| `!` 或 `#` | 注释行 | `! 这是注释` |
| `/regex/` | 正则表达式模式 | `/banner\d+/$third-party` |

要点：

- 默认网络规则只作用于子请求，不拦主文档，除非加 `$document`。
- AdGuard：短于 4 字符的规则无效；URL 匹配前截断到 4096 字符。
- uBO 对纯主机名规则按 HOSTS 语义解释：`example.com` ≡ `\|\|example.com^`（含子域并触发严格拦截，且包含主文档）；想按 ABP「任意位置匹配」须写成 `example.com*`；文件名要加前导斜杠 `/example.js`。uBO 的 `document` 整页例外与 `genericblock` 均不支持。
- `^` 是分隔符，匹配域名结束位置以及 `/`、`:`、`?`、`=` 等字符，也匹配字符串结尾。

本项目在解析阶段为 hosts 行 / domains-only 行打上「精确」标记（`Rule.exact`）。`_dns.txt` / `_domains.txt` / `_dns_abp.txt` 文本产物本身就是单域名形态，天然只匹配域名本体；连接层规则集则按来源分别输出——精确来源用 `DOMAIN` / `domain` / `host`，含子域来源用 `DOMAIN-SUFFIX` / `domain_suffix` / `host-suffix`。同一域名同时存在两种来源时按更宽的含子域语义处理。

AdGuard / uBO 的三种基础写法语义不同，尤其是**子域是否命中**：

| 写法 | 命中范围 |
| :--- | :--- |
| `\|\|example.com^` | `example.com` 及其**所有子域**（如 `www.example.com`） |
| `0.0.0.0 example.com`（hosts 行） | 仅 `example.com` 本体，**不含**子域 |
| `example.com`（domains-only 行） | 仅 `example.com` 本体，**不含**子域 |
| `/REGEX/` | 与正则匹配的域名 |

## 4. 网络修饰符（`$` 后，逗号分隔）

### 4.1 基础网络修饰符

| 修饰符 | 引擎 | 作用 |
| :--- | :--- | :--- |
| `$domain=` / `$from=` | 通用（`$from` 为 uBO 别名） | 限定发起页（Referer）域；支持 `\|` 多值、`~` 排除、`example.*` 通配 TLD、`/regex/` |
| `$third-party` / `$~third-party`（别名 `$3p` / `$1p`） | 通用 | 第三方 / 第一方限制 |
| `$strict1p` / `$strict3p` | uBO | 严格判断：主机名（而非注册域）必须完全一致（MV2-only） |
| `$to=` | uBO | 限定目标域，支持取反与正则，是 `$denyallow` 的超集 |
| `$denyallow=` | uBO/AdGuard | 「全拦 + 例外放行」。uBO 必须搭配 `$domain=`；AdGuard 中模式不能以 `\|\|` 开头、值不可取反/通配/正则 |
| `$important` | 通用 | 提升优先级，无视所有普通例外规则（例外也带 `important` 则例外赢） |
| `$badfilter` | uBO/AdGuard | 使文本相同的另一条规则失效 |
| `$match-case` | uBO/AdGuard | 大小写敏感匹配（uBO 仅用于正则规则） |
| `$method=` | uBO | HTTP 方法过滤，小写、`\|` 分隔、可取反 |
| `$popup` / `$popunder` | uBO/AdGuard | 拦截弹窗 / 弹后窗 |
| `$header=` | uBO | 按响应头匹配；值可用 `/regex/`、`~` 取反，可省略值只测存在性 |
| `$app=` | AdGuard | 桌面/移动独有：按应用过滤（Android 包名 / Windows 进程名 / Mac bundle ID） |
| `$ipaddress=` | uBO | 按请求 IP 过滤（1.60+，Firefox MV2-only）：精确 / 尾缀通配 / `/regex/` / `lan` / `loopback` |
| `$cname` | uBO | 例外规则中放行 CNAME 去遮蔽的请求（Firefox MV2-only） |
| `$top=` | uBO | 限定顶层上下文域（地址栏页面），1.70.1b5+ |
| `$all` | uBO | 全部网络类型 + popup + document + inline-font + inline-script |
| `_`（noop） | uBO | 占位符，用于消歧 |

uBO 的 HOSTS 语义、`$domain` 的 entity 通配 `google.*` 与正则域 `/regex/`、`$match-case` 仅正则、`$ipaddress` 仅 Firefox MV2 等细节，均以官方 wiki 为准。

按引擎的独有项：

- ABP：`$sitekey=`（公钥签名验证）、`$addheader=response:x-some-header:some text`（仅自定义列表 / 官方审核列表）。
- AdGuard：`$app=`、`$stealth`、`$network=`（CoreLibs）、`$cookie=`、`$hls`、`$jsonprune`、`$xmlprune`、`$removeheader=`、`$replace=`、`$urltransform` 等。

### 4.2 内容类型修饰符（可组合、可用 `~` 反选）

`document`(`doc`)、`font`、`image`、`media`、`object`、`other`、`ping`、`script`、`stylesheet`(`css`)、`subdocument`(`frame`)、`websocket`、`xmlhttprequest`(`xhr`)、`popup`。

示例：`\|\|ads.example.com^$script,image,domain=example.com`。带类型限定的规则只对该类请求生效。

引擎差异：

- `$webrtc`：AdGuard 已移除（改用 `nowebrtc` scriptlet）；uBO 用 `example.com##+js(nowebrtc)` 替代；ABP 速查表仍列出 `~webrtc`。
- `$object-subrequest`：AdGuard 已移除。
- uBO 独有 `$inline-script`、`$inline-font`（通过 CSP 禁用内联脚本/字体）。

### 4.3 例外规则专用修饰符（`@@` 规则）

| 修饰符 | 作用 |
| :--- | :--- |
| `$document`(`doc`) | 整页禁用过滤。AdGuard 中 ≡ `elemhide`+`content`+`urlblock`+`jsinject`+`extension` 同时生效；uBO 不支持用外部列表的 `document` 例外禁用自身 |
| `$elemhide`(`ehide`) | 禁用该页所有元素隐藏规则 |
| `$generichide`(`ghide`) | 只禁用通用（无域名限定）元素隐藏规则 |
| `$specifichide`(`shide`) | 只禁用特定（有域名限定）元素隐藏规则 |
| `$genericblock` | 禁用通用网络规则。uBO 不支持（会连带废掉 hosts 类列表） |
| `$urlblock` / `$jsinject` / `$content` / `$extension` / `$stealth` | AdGuard 系独有：禁用 URL 拦截 / JS 注入 / 内容修改类规则 / 用户脚本 / 隐身模块 |

`$elemhide` 关闭**全部**外观过滤，`$generichide` 只关闭**通用**外观过滤，`$specifichide` 只关闭**特定**外观过滤，三者语义不同，不可互相折叠。它们用作例外时只关外观过滤，不构成整站放行。

### 4.4 规则行为修饰符（不拦截，而是修改请求/响应）

| 修饰符 | 语法与示例 |
| :--- | :--- |
| `$csp=` | 注入 CSP 头：`\|\|example.com^$csp=script-src 'none'`；例外须含相同值，`@@...$csp`（空值）禁用全部 CSP 注入 |
| `$permissions=` | 注入 Permissions-Policy：`\|\|example.com^$permissions=autoplay=()`；uBO 用 `\|` 分隔多项，AdGuard 用 `,` |
| `$redirect=` | 拦截并重定向到本地中性资源（`noopjs`、`noopmp4-1s`、`nooptext`、`empty`、`1x1-transparent-gif` 等），可加 `:优先级` |
| `$redirect-rule=` | 只建重定向指令，不隐式建立拦截规则 |
| `$removeparam=` | 删 URL 查询参数：`*$removeparam=utm_source`、`*$removeparam=/^utm_/`；AdGuard 支持 `~/regex/` 反选与 `i` 标志 |
| `$replace=` | 替换响应内容：`$replace=/regex/replacement/flags`，仅信任来源 |
| `$cookie=` | AdGuard 独有：`$cookie=NAME;maxAge=3600;sameSite=lax`、`$cookie=/__utm[a-z]/`；例外 `@@\|\|example.org^$cookie` |
| `$removeheader=` | AdGuard 独有：`\|\|example.org^$removeheader=refresh`；`request:` 前缀针对请求头；安全头（CSP、HSTS 等）禁止删除 |
| `$network=` | AdGuard CoreLibs 独有：`174.129.166.49$network`、`/.+:3[0-9]{4}/$network` |
| `$urlskip=` | uBO 独有（1.60+，信任列表）：跳过跳转链接直达目标 |
| `$uritransform` / `$urltransform` | 改写 URL 的 path/query/hash，信任来源（uBO 中为弃用候选） |
| `$hls`、`$jsonprune`、`$xmlprune` | AdGuard 独有（信任来源）：m3u8 剪辑、JSON/XML 响应修剪 |
| `$empty`、`$mp4` | 已弃用：分别等价 `$redirect=nooptext`、`$redirect=noopmp4-1s,media` |

### 4.5 uBO 预解析指令

```text
!#include 子列表.txt     # 引入同目录子列表（其他软件视为注释）
!#if env_firefox         # 条件编译，! 可取反，&& 组合
!#else
!#endif
```

可用条件（uBO 未列出的 token 一律忽略，`adguard_app_*` 恒为 false）：`ext_abp`、`ext_ublock`、`ext_ubol`、`ext_devbuild`、`env_chromium`、`env_edge`、`env_firefox`、`env_mobile`、`env_safari`、`env_mv3`、`false`、`cap_html_filtering`、`cap_user_stylesheet`、`adguard_ext_chromium` 等。

本项目在下载阶段解析并内联 `!#include` / `!#if`，条件 token 见 `adblock_collection/preprocess.py` 的 `TARGET_TOKENS`（通用桌面 + HTML 过滤，不纳入移动端/特定内核分支），未知 token 视为 False。

## 5. 元素隐藏与 CSS 类规则（cosmetic）

### 5.1 分隔符

| 分隔符 | 含义 | 归属 |
| :--- | :--- | :--- |
| `##` | 元素隐藏（CSS 选择器） | 通用 |
| `#@#` | 元素隐藏例外 | 通用 |
| `#?#` | 扩展选择器隐藏 | ABP / AdGuard |
| `#$#` | CSS 样式注入 | AdGuard |
| `#$?#` | 扩展选择器 + 样式注入；例外 `#@$?#` | AdGuard |
| `#@?#` | 扩展选择器例外 | AdGuard |
| `#$#`（ABP 语境） | 片段过滤器（snippet） | ABP |
| `#%#` | 内联脚本注入；例外 `#@%#` | AdGuard |

`###id` 的准确含义是 `##` 分隔符加 `#id` 选择器，即隐藏 `id` 为该值的元素，三家引擎通用。DOM 层面的彻底移除由过程式选择器 `:remove()`、`:remove-attr()`、`:remove-class()` 或 scriptlet `##+js(ra.js,...)` 完成，这些属于增强层。

### 5.2 域名前缀与作用域

域名用逗号分隔多个域，`~` 排除某域：`example.com##.sponsor` 为特定规则，`##.sponsor` 与 `~example.com##.sponsor` 为通用规则。

uBO 特有目标域写法：实体通配 `google.*###tads`（匹配所有公共后缀）；主机名正则 `/^example\.org$/##h1`；`*##.selector`（无条件注入的 specific-generic）。

AdGuard CSS 注入：`example.com#$#body { background-color: #333!important; }`，例外把 `#$#` 改为 `#@$#`；样式值禁止 `url(...)` / `image-set(...)`。ABP 兼容写法 `example.org##body { remove: true; }`。

### 5.3 uBO 动作操作符（只能置于选择器链末尾）

| 操作符 | 示例 |
| :--- | :--- |
| `:style(...)` | `example.com##h1:style(background-color: blue !important)` |
| `:remove()` | `site.com###ad:remove()`（从 DOM 移除而非隐藏） |
| `:remove-attr(...)` / `:remove-class(...)` | `site.com##[onclick]:remove-attr(onclick)`，参数可为字符串或 `/regex/` |

### 5.4 扩展 CSS 伪类

ABP（必须用 `#?#` 且指定域名）：`:-abp-has()`、`:-abp-contains()`（别名 `:has-text()`）、`:-abp-properties()`、`:xpath()`；`:not()` 自 3.13 起可用。

AdGuard ExtendedCss：`:has()`、`:contains()`（= `:-abp-contains()` = `:has-text()`）、`:matches-css()` / `:matches-css-before()` / `:matches-css-after()`、`:matches-attr()`、`:matches-property()`、`:xpath()`、`:nth-ancestor(n)`、`:upward(n)`、`:remove()`、`:is()`、`:not()`、`:empty-trimmed`（`:if-not()` 已移除）。伪类名大小写不敏感。

uBO 过程式选择器：`:has-text()`、`:matches-attr()`、`:matches-css()`（`-before`/`-after`）、`:matches-media()`、`:matches-path()`、`:matches-prop()`、`:min-text-length(n)`、`:not()`、`:others()`、`:upward()`、`:watch-attr()`、`:xpath()`。

`:has()` 现代浏览器已原生支持，uBO/AdGuard 优先走原生实现，`#?#` / `#$?#` 标记强制走 ExtendedCss。

### 5.5 AdGuard 非基本规则的 `[$...]` 修饰符

| 写法 | 含义 |
| :--- | :--- |
| `[$domain=example.com]##.textad` | 按域限定 |
| `[$path=/page*.html]example.com##.textad` | 按路径限定；`$path` 省略值 = 仅首页；匹配查询串 |
| `[$url=\|\|example.com/content/*]##div.textad` | 按 URL 限定 |
| `[$app=org.example.app]example.com##.textad` | 按应用限定 |
| `example.org/checkout##.promo-banner` | 路径并入域名的简写（CoreLibs v1.20+） |

经典前缀式与 `[$...]` 式不可混用（如 `[$domain=example.org]example.com##.x` 无效）。

## 6. HTML 过滤与脚本注入

| 规则类型 | 语法 | 归属 |
| :--- | :--- | :--- |
| HTML 过滤（响应数据中删除元素，浏览器解析前） | `example.com##^script:has-text(x)`、`example.com##^.badstuff` | uBO（仅 Firefox）；AdGuard 用 `example.org$$script[data-src="banner"]`，特有属性 `tag-content`、`wildcard`、`max-length`、`min-length`（旧版遗留，推荐 `:contains()`），例外把 `$$` 改 `$@$` |
| 响应头删除 | `example.com##^responseheader(refresh)`（仅限 `location`/`refresh`/`report-to`/`set-cookie`） | uBO |
| 内联脚本注入 | `example.org#%#window.__gaq = undefined;`，例外 `#@%#` | AdGuard（仅信任过滤器） |
| Scriptlet 注入 | `example.com##+js(nobab)`；例外 `example.com#@#+js()`（禁用该站全部 scriptlet） | uBO（通用 `+js` 被忽略，必须限定域） |
| Scriptlet（AdGuard 形式） | `example.org#%#//scriptlet('abort-on-property-read', 'alert')`；例外 `#@%#//scriptlet()`；`trusted-` 前缀为增强版，仅信任过滤器可用 | AdGuard |
| 片段过滤器 | `example.com#$#log Hello world!` | ABP（仅自定义列表 / 官方审核列表） |

ABP 内置重定向资源名（`$redirect` 值）：`blank-text`、`blank-css`、`blank-js`、`blank-html`、`blank-mp3`、`blank-mp4`、`1x1-transparent-gif`。

Scriptlet / JS 片段规则出于安全仅允许出现在用户自定义列表或官方审核列表中；AdGuard 的 `trusted-*` scriptlet、`$replace`、`$hls`、`$jsonprune`、`$urltransform` 仅信任过滤器可用；uBO 的 `$replace` / `$urlskip` 仅信任来源。

## 7. DNS 层语法

### 7.1 三种风格（AdGuard Home / AdGuard DNS）

```text
||example.org^            # 拦截 example.org 及全部子域
@@||example.org^          # 解除拦截
example.org               # 只拦精确域名，子域放行
1.2.3.4 example.org       # hosts 式：对该域返回 1.2.3.4
0.0.0.0 example.com       # 等同拦截
/example.*/               # 正则拦截
@@/example.*/$important   # 正则解除（自动含 important）
```

| 载体 | 写法 | 泛域名 | 正则 |
| :--- | :--- | :---: | :---: |
| hosts | `0.0.0.0 example.com` | 不支持 | 不支持 |
| Pi-hole domains | `example.com` 或 `*.example.com` | 支持 | 不支持 |
| AdGuard Home domains | `example.com`、`*.example.com`、`/.+\.example\.com$/` | 支持 | 支持 |

hosts 行只接受完整域名，不支持路径、修饰符与通配；本项目统一输出 `0.0.0.0` 形式。本项目 `_domains.txt` 逐主机输出，天然兼容三家 DNS 端。hosts 行与 domains-only 行的语义都是**仅匹配域名本体、不含子域**，本项目据此在连接层用精确算子输出；`\|\|domain^` 来源才按含子域算子输出。

### 7.2 AdGuard Home / AdGuard DNS 修饰符

hosts 式规则不支持修饰符；含未列出修饰符的规则整体忽略。

| 修饰符 | 语法与示例 |
| :--- | :--- |
| `$client=` | 按客户端：IP、CIDR（`$client=192.168.0.0/24`）、持久客户端名（`$client='Frank\'s laptop'`，引号内 `'`、`,`、`\|` 须 `\` 转义，`~` 排除须在引号外）；只认名称不认 ClientID。`$client=~Mom\|~Dad\|Kids` |
| `$dnstype=` | DNS 记录类型：`$dnstype=A\|AAAA`、`$dnstype=~A\|~CNAME`（只允许 A 和 CNAME）；混用 `~值1\|值2` ≡ `值2` |
| `$dnsrewrite=` | 改写应答，优先级最高。简写 `$dnsrewrite=1.2.3.4` / `abcd::1234` / `example.net` / `REFUSED`；全式 `RCODE;RRTYPE;VALUE`：`NOERROR;A;1.2.3.4`、`NOERROR;CNAME;example.net`、`NOERROR;MX;32 example.mail`、`NOERROR;PTR;example.net.`（IP 须反序）、`NOERROR;SRV;10 60 8080 example.com`、`NOERROR;TXT;hello_world`、`NXDOMAIN;;`。多条 A 记录可叠加。例外 `@@\|\|example.com^$dnsrewrite`（清全部）或 `@@...$dnsrewrite=1.2.3.4`（清指定） |
| `$denyallow=` | `*$denyallow=com\|net` = 拦截一切但放行 `.com` / `.net` |
| `$important` | 与 AdGuard 同义：无视普通例外 |
| `$badfilter` | 停用文本相同的另一条规则 |
| `$ctag=` | 仅 AdGuard 服务端：按客户端标签 `device_pc\|device_phone\|os_android\|os_ios\|os_linux\|os_macos\|os_windows\|user_admin\|user_regular\|user_child` 等，`~` 取反 |

### 7.3 Pi-hole 自定义规则

精确域名：直接一行一个域名（或 `pihole -b example.com`）；允许列表 `pihole -w example.com`（allow）。

正则拦截（POSIX ERE 扩展，FTL 默认大小写不敏感），尾部可追加关键字：

| 关键字 | 作用 |
| :--- | :--- |
| `;querytype=AAAA` | 只匹配指定查询类型；逗号多选 `;querytype=A,AAAA`；`!` 反选 `;querytype=!A`；`OTHER` 匹配未列类型 |
| `;invert` | 整个正则反转 |
| `;reply=nodata` / `nxdomain` / `refused` / `none` / `ip` / `1.2.3.4` / `fe80::1234` | 指定应答方式；IPv4 与 IPv6 可同时指定（`myregex;reply=1.2.3.4;reply=fe80::1234`） |

示例：`(^|\.)doubleclick\.net$`、`.*;querytype=!A`（「反 A」策略）、`^abc$;querytype=AAAA;invert`。

- 正则内注释 `(?#说明文字)`；支持 BRE 风格反向引用 `\1`；字符类 `[:alnum:]` 及 `\d`、`\D`。
- 测试：`pihole-FTL regex-test "域名" "正则"`。
- 更多用法见 `docs/CLIENT_SYNTAX.md`。

### 7.4 本项目 DNS 分级（fail-closed）

DNS 分级采用 fail-closed：只有纯域名规则，或仅带整域语义（`$all`/`$important`/`$match-case`）与导航语义（`$popup`/`$popunder`/`$doc`/`$document`）修饰的规则，才允许升级为整域拦截；任何其它修饰符（含全部内容类型、作用域、动作型）以及**未识别/新增修饰符**一律按不可翻译拒绝，避免漏判导致整域误杀。带资源类型/取反/第三方限定的规则一律不升级为整域拦截。

## 8. 关键兼容性差异速查

| 能力 / 修饰符 | ABP | uBO | AdGuard |
| :--- | :--- | :--- | :--- |
| `$genericblock` | 支持 | **不支持** | 支持 |
| `$document` 整页例外禁用整站 | 支持 | **刻意不支持**（须用户手动信任站点） | 支持 |
| `$webrtc` | 速查表仍列 `~webrtc` | 已弃用，用 `nowebrtc` scriptlet | 已移除 |
| HTML 过滤（`##^` / `$$`） | 不支持 | 仅 Firefox | CoreLibs / 扩展-Firefox |
| `$ipaddress`、`$cname`、`$redirect-rule` | — | Firefox MV2-only | — |
| `$replace`、`$urlskip` | — | 仅信任来源 | — |
| `trusted-*` scriptlet、`$hls`、`$jsonprune`、`$urltransform` | — | — | 仅信任过滤器 |

MV3（Chromium Manifest V3）环境会限制 uBO / AdGuard 的部分能力：uBO 的 `$ipaddress`、`$cname`、`$redirect-rule` 标注为 Firefox MV2-only；AdGuard MV3 中 `$popup`、`$jsinject` 等不可用。

## 9. 优先级

从高到低：

1. `@@||site^$document` 整站放行
2. 带资源类型/作用域的例外 `@@||site^$script`
3. 带修饰符的网络阻断 `||ads^$websocket`
4. 普通网络阻断 `||ads^`
5. 过程式/DOM 移除 `##.ad:remove()`
6. CSS 隐藏 `##.ad`

冲突时更具体的规则优先，例外优先于阻断。`$important` 整域例外只被带 `$important` 的整域例外抵消。

## 10. 空资源重定向

`$redirect=noopjs`、`noopcss`、`noopmp4`、`noopimage`、`noopframe`、`nooptext` 等把命中的请求替换为无害空资源。这类规则只进入增强层。

## 11. 常见陷阱

- `###` 是 `##` 加 `#id` 选择器，属于通用语法；DOM 移除用 `:remove()` 系列。
- 取消隐藏写作 `#@#`。
- 域名不区分大小写，URL 路径区分大小写。
- `?`、`*`、`|`、`^`、`$` 是元字符；作为字面量使用时需按引擎规则转义。
- uBO 中纯主机名规则按 HOSTS 语义解释（含子域、含主文档）；要按 ABP 子串语义须加尾随 `*`。
- 全局规则 `||*$image` 匹配面过宽，性能开销大，避免使用。
- 全局元素隐藏 `##.ad` 会在每个站点持续扫描 DOM；限定域名 `site##.ad` 性能更好。
- 全局 `$removeparam=utm_source` 会改写所有站点 URL，属于高影响规则；本项目不产出该类无作用域规则。
- `$elemhide` / `$generichide` / `$specifichide` 语义不同，不可互相折叠；用作例外时只关外观过滤。
- 整站放行例外只认 `@@||域名^` 或仅带 `$all`/`$document`/`$doc`/`$important`/`$match-case` 的写法；`@@||域名^$generichide`、`@@||域名^$removeparam=…`、`@@||域名^$csp=…`、`@@||域名^$popup` 都不会抵消同域整域阻断。
- 预处理器指令 `!#include` 会就地引入同目录子列表，`!#if` / `!#else` / `!#endif` 按目标环境 token 条件编译。
- DNS 黑名单混入大量失效域名会抬高内存占用。

## 12. 调试

- uBO 日志面板可看到每条请求命中的规则与来源。
- `$important` 可临时提升优先级定位冲突，测试后移除。
- `#@#` 可临时取消某条元素隐藏。
- `pihole-FTL regex-test "域名" "正则"` 可在 Pi-hole 上单测正则。
- 本项目提供 `python -m adblock_collection lint`：校验语法与冲突，并列出可进 DNS 的域名与仅浏览器可用的规则。

## 13. 自定义黑白名单语法

`config/lists/blocklist.txt`（来源 `LocalBlocklist`）与 `config/lists/allowlist.txt`（来源 `LocalAllowlist`）在去重前并入，语法与上游一致，并额外支持**裸域名简写**：

| 写法 | 实际规则 | 说明 |
| :--- | :--- | :--- |
| `example.com`（blocklist） | `\|\|example.com^` | 自定义阻断 |
| `example.com`（allowlist） | `@@\|\|example.com^` | 自定义整域放行 |
| `\|\|ads.example.com^$script` | 原样 | 阻断，不支持裸域名以外的简写扩展 |
| `@@\|\|cdn.example.com^` | 原样 | 例外 |
| `! 注释` / `# 注释` | 忽略 | `##`/`#?#`/`#$#`/`#%#`/`#@#` 开头的元素规则不视为注释 |

同行内可使用标准资源类型与作用域修饰符。只有**整域全局例外**会进入 `dist/dns_allow.txt` 并参与抵消同名整域阻断：写法为 `@@||域名^`，或仅带 `$all`/`$document`/`$doc`/`$important`/`$match-case`（`$reason=` 注解忽略）。带路径、作用域、资源类型、导航（`$popup`/`$popunder`）或非阻断修饰（`$generichide`/`$elemhide`/`$removeparam`/`$csp` 等）的局部放行只作用于浏览器层，不会把该域名从整域阻断集合移除。

网络规则的选项段内若出现行内注释（`!` 起至行尾），解析阶段会先行剥离。例如 `@@||ads.example.com^$generichide! url: https://…` 等价于 `@@||ads.example.com^$generichide`；引号或正则字面量（如 `$replace=/a!b/`）内的 `!` 不是注释，保留原样。这样可避免上游把来源注释接在规则尾部时污染选项键，进而把局部例外误判为无选项的整域放行。

优先级（从高到低）：自定义白名单 > 自定义黑名单 > `$important` 整域例外 > `$important` 整域阻断 > 普通整域例外 > 普通整域阻断。即普通 `@@||域名^` 能抵消普通整域阻断，但不足以抵消 `$important` 整域阻断，后者只被带 `$important` 的整域例外抵消。

## 14. 参考来源

| 编号 | 来源 |
| :--- | :--- |
| [1] | [Static filter syntax · gorhill/uBlock Wiki](https://github.com/gorhill/uBlock/wiki/Static-filter-syntax) |
| [2] | [Hosts Blocklists · AdguardTeam/AdGuardHome Wiki](https://github.com/AdguardTeam/AdGuardHome/wiki/Hosts-Blocklists) |
| [3] | [How to create your own ad filters · AdGuard Knowledge Base](https://adguard.com/kb/general/ad-filtering/create-own-filters/) |
| [4] | [DNS filtering rules syntax · AdGuard DNS Knowledge Base](https://adguard-dns.io/kb/general/dns-filtering-syntax/) |
| [5] | [How to write filters · Adblock Plus Help Center](https://help.adblockplus.org/adblock-plus-help-center/how-to-write-filters) |
| [6] | [Regex tutorial · Pi-hole documentation](https://docs.pi-hole.net/regex/tutorial/) |

## 15. 相关文档

| 文档 | 内容 |
| :--- | :--- |
| `docs/GENERATED_RULES.md` | 本项目生成产物的逐字语法与用法（含 `adapters/` 与订阅地址清单） |
| `docs/CLIENT_SYNTAX.md` | 各客户端原生拦截语法与命中范围（ABP/hosts/dnsmasq/Pi-hole/AdGuard Home/mihomo/sing-box/Surge/Quantumult X） |
| `docs/OPS.md` | 构建、配置源、白名单、门禁与源失效处置 |
| `docs/FLOW.md` | 构建流水线各阶段 |
