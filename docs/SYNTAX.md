# 过滤规则语法知识库

本文档整理本项目产出的三类订阅（扩展网络层、扩展元素隐藏层、DNS 层）涉及的语法边界、修饰符、资源类型、优先级与常见陷阱，既是使用说明，也是贡献规则时的对照表。

## 1. 三层防护与产物对应

| 层 | 生效位置 | 产物 | 能表达的语法 |
| :--- | :--- | :--- | :--- |
| 网络层 | 浏览器扩展 | `adblock_collection_full_browser_network.txt` | `\|\|` 域名/URL 匹配、`$` 资源类型与修饰符、`@@` 例外 |
| 元素层 | 浏览器扩展 | `adblock_collection_full_cosmetic.txt` | `##` 隐藏、`#@#` 取消隐藏、scriptlet、过程式选择器、HTML 过滤 |
| 增强层 | uBO / AdGuard | `adblock_collection_ubo_enhance.txt` | `$redirect`/`$csp`/`$removeparam` 等网络修饰符，以及 `##+js`/`#?#`/`:remove()`/`#$#`/`##^` |
| DNS 层 | AdGuard Home / Pi-hole / hosts | `_dns.txt`、`_domains.txt`、`dns_allow.txt` | 只能表达整域拦截/放行，单行一个域名 |

浏览器扩展兼容性：`full` 与 `_browser_network` / `_cosmetic` 以 ABP 通用子集为主，同时收录 uBO/AdGuard 扩展语法（ABP 会忽略无法识别的行）；增强层单独成文件，供支持高级能力的扩展订阅。

## 2. 基础语法（ABP / uBO / AdGuard 通用）

| 语法 | 含义 |
| :--- | :--- |
| `\|\|domain.com^` | 匹配该域名开头的请求，`^` 是域名边界 |
| `\|\|domain.com/path/*` | 匹配 URL 前缀与路径通配 |
| `domain.com##selector` | CSS 隐藏元素，请求照常发出 |
| `@@\|\|domain.com^` | 例外（放行），优先级高于阻断 |
| `@@\|\|domain.com^$document` | 整站放行（最高优先级） |
| `domain.com#@#selector` | 取消该站点的某条元素隐藏 |

`^` 是分隔符，匹配域名结束位置以及 `/`、`:`、`?`、`=` 等字符，也匹配字符串结尾。

`###id` 的准确含义是 `##` 分隔符加 `#id` 选择器，即隐藏 `id` 为该值的元素，三家引擎通用。DOM 层面的彻底移除由过程式选择器 `:remove()`、`:remove-attr()`、`:remove-class()` 或 scriptlet `##+js(ra.js,...)` 完成，这些属于增强层。

## 3. 资源类型（`$` 后的类型限定）

| 类型 | 说明 |
| :--- | :--- |
| `script` | JavaScript |
| `image` | 图片 |
| `stylesheet` / `css` | 样式表 |
| `font` | 字体 |
| `media` | 音视频 |
| `xmlhttprequest` / `xhr` | AJAX |
| `fetch` | Fetch API 请求 |
| `subdocument` / `frame` | iframe 内嵌文档 |
| `popup` | 弹出窗口 |
| `websocket` | WebSocket 长连接（直播、弹幕、实时统计常用） |
| `ping` / `beacon` | 埋点上报 |
| `object` / `object-subrequest` | 插件对象 |
| `other` | 其它 |

限定资源类型的规则只对该类请求生效。DNS 层无法区分请求类型，因此带资源类型限定的规则一律不升级为整域拦截。

## 4. 修饰符分组

阻断型（改变拦截范围或优先级）：

| 修饰符 | 引擎 | 说明 |
| :--- | :--- | :--- |
| `$third-party` / `$~third-party` | 通用 | 限定第一/第三方请求 |
| `$important` | 通用 | 提升优先级，可覆盖例外之外的规则 |
| `$match-case` | uBO/AdGuard | 路径区分大小写 |
| `$all` | AdGuard | 等价于不限类型的整域阻断 |
| `$popup` | uBO/AdGuard | 拦截弹窗 |
| `$badfilter` | uBO/AdGuard | 停用上游同名规则 |
| `$cname` | uBO/AdGuard | 按 CNAME 记录匹配 |

动作/内容型（改写请求或响应，不新增整域拦截）：

| 修饰符 | 引擎 | 说明 |
| :--- | :--- | :--- |
| `$removeparam` / `$queryprune` | uBO/AdGuard | 删除 URL 追踪参数 |
| `$replace` | uBO/AdGuard | 改写响应体 |
| `$csp` | uBO/AdGuard | 注入 Content-Security-Policy |
| `$permissions` | uBO/AdGuard | 注入 Permissions-Policy |
| `$removeheader` / `$addheader` / `$header` | uBO/AdGuard | 改写请求/响应头 |
| `$redirect` / `$redirect-rule` / `$rewrite` | uBO/AdGuard | 重定向到空资源或替换资源 |
| `$urltransform` / `$urlskip` | AdGuard | URL 改写 |
| `$cookie` / `$set-cookie` | uBO | 改写 Cookie |

作用域型（限定规则在哪些来源站点生效）：`$domain`、`$from`、`$to`、`$denyallow`、`$ipaddress`、`$method`。

## 5. 优先级

从高到低：

1. `@@||site^$document` 整站放行
2. 带资源类型/作用域的例外 `@@||site^$script`
3. 带修饰符的网络阻断 `||ads^$websocket`
4. 普通网络阻断 `||ads^`
5. 过程式/DOM 移除 `##.ad:remove()`
6. CSS 隐藏 `##.ad`

冲突时更具体的规则优先，例外优先于阻断。

## 6. 元素隐藏与脚本注入

| 语法 | 引擎 | 效果 |
| :--- | :--- | :--- |
| `site##.ad` | 通用 | CSS `display:none`，DOM 节点保留 |
| `site#?#.ad:has-text(Ad)` | uBO/AdGuard | 过程式选择器 |
| `site##.ad:remove()` | uBO/AdGuard | 从 DOM 移除节点 |
| `site##+js(name, arg)` | uBO/AdGuard | 注入 scriptlet |
| `site#%#//scriptlet(name)` | AdGuard | 注入 scriptlet |
| `site##^script:has-text(ad)` | uBO/AdGuard | HTML 过滤 |
| `site#@#.ad` | 通用 | 取消隐藏 |
| `site#$#.ad{display:none}` | AdGuard | CSS 注入 |

反广告检测对抗常用 scriptlet，例如 `##+js(abort-on-property-read, canRunAd)`、`##+js(set-constant, ...)`、`##+js(nano-setTimeout-booster, ...)`。

## 7. 空资源重定向

`$redirect=noopjs`、`noopcss`、`noopmp4`、`noopimage`、`noopframe`、`nooptext` 等把命中的请求替换为无害空资源。这类规则只进入增强层。

## 8. DNS 层语法

| 载体 | 写法 | 泛域名 | 正则 |
| :--- | :--- | :---: | :---: |
| hosts | `0.0.0.0 example.com` | 不支持 | 不支持 |
| Pi-hole domains | `example.com` 或 `*.example.com` | 支持 | 不支持 |
| AdGuard Home domains | `example.com`、`*.example.com`、`/.+\.example\.com$/` | 支持 | 支持 |

hosts 行只接受完整域名，不支持路径、修饰符与通配；本项目统一输出 `0.0.0.0` 形式。本项目 `_domains.txt` 逐主机输出，天然兼容三家 DNS 端。

## 9. 常见陷阱

- `###` 是 `##` 加 `#id` 选择器，属于通用语法；DOM 移除用 `:remove()` 系列。
- 取消隐藏写作 `#@#`。
- 域名不区分大小写，URL 路径区分大小写。
- `?`、`*`、`|`、`^`、`$` 是元字符；作为字面量使用时需按引擎规则转义。
- 全局规则 `||*$image` 匹配面过宽，性能开销大，避免使用。
- 全局元素隐藏 `##.ad` 会在每个站点持续扫描 DOM；限定域名 `site##.ad` 性能更好。
- 全局 `$removeparam=utm_source` 会改写所有站点 URL，属于高影响规则；本项目不产出该类无作用域规则。
- DNS 黑名单混入大量失效域名会抬高内存占用。

## 10. 调试

- uBO 日志面板可看到每条请求命中的规则与来源。
- `$important` 可临时提升优先级定位冲突，测试后移除。
- `#@#` 可临时取消某条元素隐藏。
- 本项目提供 `python -m adblock_collection lint`：校验语法与冲突，并列出可进 DNS 的域名与仅浏览器可用的规则。

## 11. 自定义黑白名单语法

`config/lists/blocklist.txt`（来源 `LocalBlocklist`）与 `config/lists/allowlist.txt`（来源 `LocalAllowlist`）在去重前并入，语法与上游一致，并额外支持**裸域名简写**：

| 写法 | 实际规则 | 说明 |
| :--- | :--- | :--- |
| `example.com`（blocklist） | `\|\|example.com^` | 自定义阻断 |
| `example.com`（allowlist） | `@@\|\|example.com^` | 自定义整域放行 |
| `\|\|ads.example.com^$script` | 原样 | 阻断，不支持裸域名以外的简写扩展 |
| `@@\|\|cdn.example.com^` | 原样 | 例外 |
| `! 注释` / `# 注释` | 忽略 | `##`/`#?#`/`#$#`/`#%#`/`#@#` 开头的元素规则不视为注释 |

同行内可使用标准资源类型与作用域修饰符。只有**整域全局例外**（`@@||域名^`，不含路径/作用域/资源类型）会进入 `dist/dns_allow.txt`；带修饰符的局部放行仅作用于浏览器层。

优先级（从高到低）：自定义白名单 > 自定义黑名单 > 上游例外 > 上游 `$important` > 上游普通阻断。
