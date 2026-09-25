# 需求文档 — 客户端适配产物

## 引言

本需求定义「客户端适配产物」：在现有原始规则清单之外，为每个受支持客户端生成**一对一**的适配文件，让用户以最少的配置步骤接入。适配文件按客户端各自最佳形态产出（可直接引用的配置片段或完整可导入结构），随每日 CI 构建生成，作为 `dist/` 的正式产物发布，并由 `manifest.json` 索引。目标是把「用户自己拼配置」变成「下载/引用即用」，同时不新增任何拦截判定，保持「宁愿少拦截，不要误拦截」的项目原则。

## 术语表

- **适配产物（Adapter）**：面向单个客户端、包含可粘贴或可导入配置的生成文件。
- **规范规则集**：现有已发布的规则产物（`dist/rulesets/adblock_clash.yaml`、`adblock_singbox.json`、`adblock_surge_domain_set.txt`、`adblock_quanx.list`、`*_dns.txt`、`*_domains.txt`、`dns_allow.txt`）。
- **规范基址**：适配产物中引用规范规则集的公开 URL 前缀，例如 `https://raw.githubusercontent.com/wansheng8/GZ/main/dist/`。
- **镜像基址**：与规范基址等价的 jsDelivr 前缀，例如 `https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/`。
- **受支持客户端**：mihomo/Clash Meta、sing-box、Surge、Quantumult X、AdGuard Home、Pi-hole、dnsmasq、系统 hosts、浏览器扩展（uBO/AdGuard/ABP）。
- **指引型适配产物**：面向没有独立配置文件的客户端（系统 hosts、浏览器扩展），以安装与导入步骤为主的适配文件。
- **配置片段**：需要用户粘贴进现有配置、不整份替换用户配置的适配内容。
- **构建系统**：`adblock_collection` 包及其 `build` 子命令。

## 需求

### 需求 1：一对一适配产物

**用户故事：** AS 订阅者，I want 每个客户端都有一个专属适配文件，so that 我不必自己研究配置写法。

#### 验收标准

1. 构建系统 SHALL 为每个受支持客户端生成且仅生成一个专属适配产物。
2. 构建系统 SHALL 将适配产物写入 `dist/adapters/` 目录。
3. 构建系统 SHALL 按客户端使用稳定的适配文件名与扩展名（如 `mihomo.yaml`、`singbox.json`、`surge.conf`、`quanx.conf`、`adguardhome.yaml`、`pihole.txt`、`dnsmasq.conf`、`hosts.md`、`browsers.md`）。
4. 构建系统 SHALL 在每个适配产物中写入说明用途与接入方式的首部注释。

### 需求 2：按客户端最佳形态

**用户故事：** AS 订阅者，I want 适配文件采用该客户端最省事的形式，so that 接入成本最低。

#### 验收标准

1. WHEN 生成 mihomo/Clash Meta 适配产物，构建系统 SHALL 输出可直接粘贴的 `rule-providers` 与 `rules` 配置片段。
2. WHEN 生成 sing-box 适配产物，构建系统 SHALL 输出引用远端源格式规则集（`format: source`、URL 以 `.json` 结尾）的路由配置片段。
3. WHEN 生成 Surge 适配产物，构建系统 SHALL 输出 `DOMAIN-SET` 引用行。
4. WHEN 生成 Quantumult X 适配产物，构建系统 SHALL 输出 `filter_remote` 引用行。
5. WHEN 生成 AdGuard Home 适配产物，构建系统 SHALL 输出可粘贴的过滤列表配置片段，且该片段不包含放行规则。
6. WHEN 生成 Pi-hole 适配产物，构建系统 SHALL 输出逐行一个列表 URL 的 `adlists` 内容。
7. WHEN 生成 dnsmasq 适配产物，构建系统 SHALL 输出 `addn-hosts` 配置片段与本地文件路径占位。
8. WHEN 生成系统 hosts 适配产物，构建系统 SHALL 输出各主流操作系统的安装路径与下载地址指引。
9. WHEN 生成浏览器扩展适配产物，构建系统 SHALL 输出受支持扩展的订阅地址与导入步骤指引。

### 需求 3：引用规范规则集

**用户故事：** AS 订阅者，I want 适配文件引用同一套已发布规则，so that 各客户端拦截范围一致且随每日构建更新。

#### 验收标准

1. 构建系统 SHALL 让每个适配产物引用对应客户端的规范规则集产物。
2. 构建系统 SHALL 让适配产物与 DNS/连接层使用同一「应拦截纯域名」集合，不引入独立规则来源。
3. 构建系统 SHALL 在适配产物中使用规范基址构造引用 URL。
4. WHERE 生成环境中提供了镜像基址，构建系统 SHALL 在首部注释中同时给出镜像基址的等价引用。

### 需求 4：确定性与幂等

**用户故事：** AS 维护者，I want 相同输入产生相同适配文件，so that 构建可复现、diff 可审查。

#### 验收标准

1. 构建系统 SHALL 在适配产物中省略生成时间戳与随机标识。
2. 构建系统 SHALL 让相同规则集合与相同基址在多次构建中产生逐字节一致的适配产物。
3. 构建系统 SHALL 让适配产物的行序在相同输入下稳定。

### 需求 5：安全边界

**用户故事：** AS 维护者，I want 适配产物只做引用与配置，so that 不因适配层引入误杀或破坏用户现有配置。

#### 验收标准

1. 构建系统 SHALL 让适配产物中的拦截范围完全来自被引用的规范规则集。
2. 构建系统 SHALL 让 AdGuard Home 适配产物仅提供配置片段，不整份替换用户的 `AdGuardHome.yaml`。
3. IF 规范规则集不满足 DNS 安全分级，构建系统 SHALL 继续按现有 fail-closed 策略将其排除出 DNS 产物，且在适配产物中不体现该规则。
4. 构建系统 SHALL 让 dnsmasq 适配产物引用本地文件路径，不声称 dnsmasq 能直接拉取远程 URL。

### 需求 6：发布与索引

**用户故事：** AS 订阅者，I want 适配产物有长期有效地址，so that 我可以直接订阅或引用。

#### 验收标准

1. 构建系统 SHALL 将每个适配产物登记进 `dist/manifest.json` 的 `generated_files`。
2. 构建系统 SHALL 为适配产物的 manifest 条目记录文件路径、格式标识、`bytes` 与 `sha256`。
3. 构建系统 SHALL 让适配产物的发布路径在每日 CI 构建后保持不变。
4. 构建系统 SHALL 在 `README` 或 `docs/GENERATED_RULES.md` 中给出适配产物的获取地址与接入说明。

### 需求 7：基址可配置

**用户故事：** AS 维护者，I want 仓库所有者与分支可配置，so that 仓库迁移或改名时适配产物仍然正确。

#### 验收标准

1. 构建系统 SHALL 从单一配置来源派生规范基址与镜像基址。
2. IF 仓库所有者、仓库名或分支发生变化，构建系统 SHALL 在仅修改该配置来源后生成正确 URL。
3. 构建系统 SHALL 在适配产物 URL 中使用与现有 `README` 订阅链接一致的主机与路径风格。

### 需求 8：质量保障

**用户故事：** AS 维护者，I want 适配产物有测试与门禁，so that 语法错误或 URL 漂移会被拦截。

#### 验收标准

1. 构建系统 SHALL 为每个适配产物提供单元测试，断言其语法结构与引用 URL。
2. IF 适配产物生成失败，构建系统 SHALL 以非零退出码终止构建。
3. 构建系统 SHALL 让适配产物的字节基线纳入现有测试基线或显式忽略清单。
4. 构建系统 SHALL 在既有 lint 与测试步骤中一并校验适配产物。

### 需求 9：确定性来源与不变量

**用户故事：** AS 维护者，I want 适配产物受现有不变量保护，so that 它不破坏既有产物与门禁。

#### 验收标准

1. 构建系统 SHALL 保持现有三层产物、DNS 产物与连接层产物的内容与语义不变。
2. 构建系统 SHALL 保持适配产物不参与「类别并集等于完整版」等规则计数不变量。
3. WHILE 生成适配产物，构建系统 SHALL 保持 `manifest.json` 既有字段与既有条目的含义不变。

## 已确认事项

1. 受支持客户端为术语表所列 9 个：mihomo/Clash Meta、sing-box、Surge、Quantumult X、AdGuard Home、Pi-hole、dnsmasq、系统 hosts、浏览器扩展指引。
2. AdGuard Home 适配产物不内嵌放行规则；放行由用户按需单独处理。
3. 规范基址与 jsDelivr 镜像基址两套都提供：适配产物首部注释给出两套引用，`README`/`docs/GENERATED_RULES.md` 也列出。
