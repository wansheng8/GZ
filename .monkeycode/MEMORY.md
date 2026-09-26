# User Instruction Memory

This file records user instructions, preferences, and teachings for reference in future interactions.

## Format

### User Instruction Entry
User instruction entries should follow this format:

[User Instruction Summary]
- Date: [YYYY-MM-DD]
- Context: [Mentioned scenario or time]
- Instructions:
  - [Content of user teaching or instruction, described line by line]

### Project Knowledge Entry
Entries discovered by the Agent during task execution should follow this format:

[Project Knowledge Summary]
- Date: [YYYY-MM-DD]
- Context: Discovered by Agent while performing [specific task description]
- Category: [Operations & Deployment|Build Methods|Testing Methods|Troubleshooting & Debugging|Workflow & Collaboration|Environment Configuration]
- Instructions:
  - [Specific knowledge points, described line by line]

## Deduplication Strategy
- Before adding a new entry, check for similar or identical instructions.
- If a duplicate is found, skip the new entry or merge it with the existing one.
- When merging, update the context or date information.
- This helps avoid redundant entries and keeps the memory file tidy.

## Entries

[User Instruction Summary]
- Date: 2026-09-01
- Context: 用户要求核对 GZ 广告规则集语法类别覆盖情况
- Instructions:
  - 上游 `!#include` 引用的子列表（如 fanboy_annoyance_specific_uBO.txt 等）内容已包含在官方主列表发布版中，无需在 sources.yaml 单独收录子列表源——加源后去重净增 0 规则，属于冗余配置。遇到 `!#include` 不要急于实现展开或加源，先验证主列表是否已覆盖。

[Project Knowledge Summary]
- Date: 2026-09-01
- Context: Discovered by Agent while performing 回退 sources.yaml 冗余源后的构建验证
- Category: Troubleshooting & Debugging
- Instructions:
  - 删除 sources.yaml 中某个源后，如果 dist/previous_metrics.json 的 source_counts 仍记录该源，质量门禁会误报「规则数骤降 100%」导致构建失败。处理方式：重新构建一次即可（构建失败也会写入新的 previous_metrics），或先手动从 previous_metrics.json 移除该源记录再构建。

[Project Knowledge Summary]
- Date: 2026-09-01
- Context: Discovered by Agent while performing 删除源后 rebase 解决 dist 冲突
- Category: Troubleshooting & Debugging
- Instructions:
   - git rebase 遇到 dist 产物冲突时，checkout --ours 取的是 rebase 前 HEAD（即远程 CI 版本），--theirs 才是正在重放的本地产物版本。用错方向会把 CI 产物混入，导致删除源等本地变更丢失。正确姿势：对 dist 冲突文件用 `git checkout --theirs`；或放弃冲突解决，直接基于当前 config 重新构建产物再提交（更可靠）。提交后必须用 `git rev-list HEAD...origin/main --count` 验证同步，并抽查产物 total/残留源确认内容正确。

[Project Knowledge Summary]
- Date: 2026-09-18
- Context: Discovered by Agent while performing 全量 dist 构建验证
- Category: Build Methods
- Instructions:
  - 本地执行全量 `python -m adblock_collection build --out <dir> --split-by-category --redundant` 峰值内存超过 2.72GiB；用 background terminal 且 memory_percent 设为 35（约 2.72GiB）会被 cgroup OOM 杀死（exit 137）。本地验证可去掉 `--split-by-category` 或给足内存上限，完整产物以 CI 构建为准。
  - hosts/纯域名类源（StevenBlack、Firebog、Peter Lowe、AdAway 等）经解析统一规范化为 `||domain^` 后与 adblock 源做全局去重，所以这些源的 by_source 计数会大幅下降甚至接近 0，属预期行为而非解析回归；同时 `dns/domains` 域数会上升。
  - CI 的 build workflow 先 `rm -rf dist` 再构建，因此质量门禁没有 previous_metrics 基线，不会因规则总量变化或删源而误报骤降。

[Project Knowledge Summary]
- Date: 2026-09-19
- Context: Discovered by Agent while investigating 用户反馈「导入列表后测试站整体 0 拦截」
- Category: Troubleshooting & Debugging
- Instructions:
  - DNS 客户端（AdGuard Home / Pi-hole）报「0 拦截」时，先确认解析流量是否真的经过该 DNS，而不是列表问题：`nslookup doubleclick.net <DNS地址>` 应返回 `0.0.0.0`/NXDOMAIN；返回真实 IP 说明设备或浏览器走了 DoH（Chrome/系统「安全 DNS」）绕过了本地 DNS。
  - 浏览器测试站（d3ward、AdBlock Tester、CanYouBlockIt 等）大量测试项是元素隐藏/脚本/脚本注入，DNS 层天然无法拦截；用 DNS 列表去测这些站点得分低属预期，不代表列表失效。验证 DNS 是否生效应看广告网络域名（googlesyndication.com、doubleclick.net、an.yandex.ru）是否被解析拦截。
  - 订阅链接按客户端区分：浏览器用 `adblock_collection_full.txt`；DNS 用 `_dns.txt`（hosts，Pi-hole/AdGuard Home/dnsmasq）或 `_domains.txt`（纯域名，AdGuard Home/AdGuard DNS），两者内容等价、只导一个即可。

[Project Knowledge Summary]
- Date: 2026-09-21
- Context: Discovered by Agent while performing 推送 DNS 判定修复并等待 CI 构建
- Category: Workflow & Collaboration
- Instructions:
  - CI workflow（`.github/workflows/build.yml`，Build Filters）推送后约 7-8 分钟完成，成功后由 bot 自动提交 dist 产物（commit message 带 `[skip ci]`）。校验 CI 结果用 `git fetch origin && git log --oneline -2 origin/main` 看是否出现新的 `auto update filter lists` 提交，比 GitHub API 可靠（未认证 API 易触发 403 rate limit）；构建是否通过看 `dist/build_report.json` 的 `passed` 与 `metrics`。
  - 解析/分类逻辑变更需递增 `adblock_collection/pipeline.py` 的 `PARSER_VERSION` / `CLASSIFIER_VERSION`，`.cache/parsed` 旧缓存才会失效重建。

[Project Knowledge Summary]
- Date: 2026-09-23
- Context: Discovered by Agent while performing 清理 Actions 历史运行（仅保留最新 3 条）
- Category: Workflow & Collaboration
- Instructions:
  - `.github/workflows/cleanup-runs.yml`（Cleanup Runs）每日 04:00 清理 Actions 历史 run，仅保留最新 3 条；`push` 本文件时也会立即执行一次。它调用 `gh api` 删除非进行中的 run，需 `permissions: actions: write`；删除 run 会连同其日志与产物一起移除。
  - 未认证访问 GitHub REST API（`api.github.com`）会 403 rate limit，但 `https://github.com/<owner>/<repo>/actions?query=branch%3Amain` 的 HTML 页面可正常读取：抓取后统计 `/actions/runs/<id>` 去重数量即可核实 run 条数，比 API 可靠。

[Project Knowledge Summary]
- Date: 2026-09-23
- Context: Discovered by Agent while performing 把每次构建的规则条数同步到 MEMORY.md
- Category: Workflow & Collaboration
- Instructions:
  - 文件末尾由 `build-metrics` HTML 注释标记包围的「构建指标快照」区块由 CI 自动维护：`build.yml` 在构建后运行 `python -m adblock_collection.memory_metrics`，把总规则数/DNS 域名/各层条数写入该区块（最新置顶、保留最近 10 次，`KEEP` 在 `adblock_collection/memory_metrics.py`），并随 dist 一起自动提交。
  - 手工编辑 MEMORY.md 时只在标记区块之外增删记忆条目，不要改动区块内容；否则下次构建会被覆盖。

[Project Knowledge Summary]
- Date: 2026-09-25
- Context: Discovered by Agent while performing C/U 单元落地与字节基线重生成
- Category: Build Methods
- Instructions:
  - 本环境无 `python`，只有 `python3`（3.11）。
  - 字节基线夹具重生成：调用 `tests/_baseline_fixture.py` 的 `build_fixture`（m2，增强全关）与 `build_default_fixture`（m3，增强全开）构建到临时目录，再把有变化的 `*.dns_safety.json` / `manifest.json` / `sources_status.json`（m3 含 `security/`）复制回 `tests/baseline/{m2,m3}`；`build_diff.txt`、`new_domain_review.json` 已 gitignore，且在 `tests/test_baseline.py` 的 `extra_ignores` 中。
  - `baseline._canonical` 会剔除不可复现字段：顶层 `generated_at`、manifest 内嵌 `sources_status.generated_at` 与逐条目 `sha256`；新增时间戳/哈希字段无需再改基线忽略列表。
  - 解析/分类/规范化版本常量在 `adblock_collection/pipeline.py`；一轮单元中每条版本轴最多递增一次，触碰基线的单元（域名集合、`$important` 语义等）单独提交。
  - manifest 消费点对 `rules` 键的处理：新增不含 `rules` 字段的产物条目（如 `adapters/*`，`format=adapter`）时，所有 `{x["file"]: x["rules"]}` 形式必须改为 `x.get("rules", 0)`，覆盖 `stats_badge.load_counts`、`memory_metrics` 与 CI `build.yml` 健康检查；`cli.stats_cmd` 亦需跳过 `adapters/` 路径，避免把 URL 行当规则计数或给适配条目补 `rules/empty`。

[User Instruction Summary]
- Date: 2026-09-26
- Context: 用户在客户端适配产物任务收尾时明确要求
- Instructions:
  - 所有回复、思考过程与面向用户的说明一律使用中文（Simplified Chinese），包括总结、进度说明与提问。

<!-- build-metrics:start -->
## 构建指标快照（CI 自动生成）

> 由 `python -m adblock_collection.memory_metrics` 在每次构建后更新，最新记录置顶、仅保留最近 10 次；数值取自 `dist/build_report.json` 与 `dist/manifest.json`。

| 生成时间(UTC) | 提交 | 结果 | 总规则数 | DNS 域名 | 网络拦截 | 元素隐藏 | uBO 增强 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-09-26 01:07 | `d3fb13d` | 通过 | 793,466 | 539,592 | 629,322 | 164,144 | 31,867 |
| 2026-09-26 00:38 | `8974a92` | 通过 | 793,460 | 539,586 | 629,316 | 164,144 | 31,867 |
| 2026-09-26 00:03 | `0c9ba1c` | 通过 | 793,292 | 539,422 | 629,152 | 164,140 | 31,867 |
| 2026-09-25 17:06 | `686d93a` | 通过 | 793,579 | 539,768 | 629,423 | 164,156 | 31,873 |
| 2026-09-25 16:51 | `14aadf0` | 通过 | 793,575 | 539,765 | 629,420 | 164,155 | 31,872 |
| 2026-09-25 16:36 | `ea804d0` | 通过 | 793,553 | 539,764 | 629,400 | 164,153 | 31,872 |
| 2026-09-25 08:28 | `df14ced` | 通过 | 800,370 | 546,621 | 636,201 | 164,169 | 31,877 |
| 2026-09-25 03:21 | `b734f70` | 通过 | 801,455 | 547,614 | 637,288 | 164,167 | 31,874 |
| 2026-09-24 08:00 | `c1f5714` | 通过 | 800,813 | 547,046 | 636,690 | 164,123 | 30,734 |
| 2026-09-23 08:09 | `576373a` | 通过 | 799,907 | 546,226 | 635,837 | 164,070 | 30,721 |
<!-- build-metrics:end -->