# 操作规程（RUNBOOK / OPS）

本文档定义 GZ 广告规则合集日常操作的**标准流程**。每个操作给出：适用场景 → 标准命令序列 → 自检清单 → 完成判定。遵循「宁愿少拦截，不要误拦截」原则。

配套阅读：`docs/FLOW.md`（流程各阶段细节与失败处置矩阵）。

---

## 1. 日常自动流程（无需人工）

**触发**：GitHub Actions 每日 03:00 UTC 定时运行（`.github/workflows/build.yml`），main 分支 push 时若涉及代码也会触发。

**CI 自动做的事**：
1. 拉取仓库 → 安装开发依赖 → 运行 `python -m pytest -q`（含 M2/M3 字节基线夹具比对）→ 用缓存下载源
2. 清理 dist 前先保留上一批 `previous_metrics.json`，使质量门禁与构建差异报告有基线可比
3. 执行构建命令 `python3 -m adblock_collection build --out dist --split-by-category`（四项增强默认开启；CI 镜像中 `python` 与本地 `python3` 等价）；门禁、误杀回归或 P9 往返校验失败会以退出码 1/3 阻断本次推送
4. 上传 `.cache/build/rules.jsonl` 为 artifact（名 `rules-jsonl`，保留 7 天），便于复现与离线重建
5. 再以「增强全关 + 旧 --redundant」构建到 `/tmp/dist-legacy`，校验退出开关路径与重构前字节基线（`--no-alias-normalize --no-resolve-conflicts --no-per-rule-classify --no-domain-fold --redundant`），不产出正式 dist
6. 健康检查（规则数 < 30 万 或 失败源 ≥ 5 时输出 WARNING，不阻断）
7. dist 有变化则自动提交 `chore: auto update filter lists [skip ci]` 并推送

**人工介入条件**（任一出现才需处理）：
- Actions 运行显示失败（红色）
- dist 长期未更新（超过 2 天无 auto update 提交）
- 订阅者反馈规则异常

**完成判定**：Actions 全绿，且每日有 auto update 提交。

---

## 2. 手动构建

**适用场景**：本地验证代码改动、排查问题、需要在 CI 前预演。

**标准命令序列**：

```bash
cd /workspace
# 1) 配置校验
python3 -m adblock_collection sources

# 2) 本地规则校验（构建会自动做，这里可提前看）
python3 - <<'PY'
from pathlib import Path
from adblock_collection.merge import validate_local_rules
for x in validate_local_rules(Path("config/sources.yaml")):
    print("违规:", x)
PY

# 3) 完整构建（CI 同款参数，四项增强默认开启）
python3 -m adblock_collection build --out dist --split-by-category
echo "exit=$?"   # 0=成功; 1=门禁/回归失败; 2=本地规则违规; 3=内部一致性失败

# 4) 可选：增强全关验证（产物写临时目录，不影响 dist）
python3 -m adblock_collection build --out /tmp/dist-legacy --split-by-category \
  --no-alias-normalize --no-resolve-conflicts --no-per-rule-classify --no-domain-fold --redundant
python3 -c "import json;print(json.load(open('/tmp/dist-legacy/build_report.json')).get('enhancements', {}))"

# 5) 可选：dry-run 与字节基线（dry-run 不写任何产物，含 rules.jsonl/指纹/维护历史；baseline 逐字节比对）
python3 -m adblock_collection build --out /tmp/dry --dry-run
python3 -m adblock_collection build --out /tmp/dist-new --split-by-category --baseline dist

# 6) 可选：规则过期跟踪（本地连续构建；复用 .cache/build/rule_history.tsv）
# --stale-days 只接受正整数；仅当门禁与回归通过时才推进指纹与维护历史
python3 -m adblock_collection build --out /tmp/dist-history --split-by-category --history --stale-days 30
```

**构建后自检清单**（7 项）：

```bash
# ① 本地增强规则已入库（应 = config/local_rules.txt 非注释行数，当前 10）
awk '!/^#/ && NF' config/local_rules.txt | wc -l
# 且每条都出现在产物中（逐条精确匹配，应全部 =1）
while IFS= read -r r; do [ -z "$r" ] && continue; case "$r" in \#*) continue;; esac; grep -qF -- "$r" dist/adblock_collection_full.txt || echo "缺失: $r"; done < config/local_rules.txt

# ② 误杀回归 0 违规
python3 -c "import json;d=json.load(open('dist/regression_report.json'));print('allow_violations:',len(d['allow_violations']))"

# ③ 失败源清单（<5 正常）
python3 -c "import json;d=json.load(open('dist/sources_status.json'));print('failed:',d['failed_sources'])"

# ④ 门禁结果
python3 -c "import json;d=json.load(open('dist/build_report.json'));print('gate_passed:',d.get('passed'),'failures:',d.get('failures'))"

# ⑤ 产物与 git 一致（避免提交遗漏）
git status --short dist/ | head

# ⑥ 三层产物完整性（网络 + 元素隐藏 == 完整版；DNS 等价 == 单行域名）
python3 - <<'PY'
import json

e = {x["file"]: x["rules"] for x in json.load(open("dist/manifest.json"))["generated_files"]}
net = e.get("adblock_collection_full_browser_network.txt", 0)
cos = e.get("adblock_collection_full_cosmetic.txt", 0)
abp = e.get("adblock_collection_full_dns_abp.txt", 0)
full = e.get("adblock_collection_full.txt", 0)
dom = e.get("adblock_collection_full_domains.txt", 0)
print("三层并集 == 完整版:", net + cos == full, f"({net} + {cos} vs {full})")
print("DNS 等价 == 单行域名:", abp == dom, f"({abp} vs {dom})")
PY

# ⑦ 增量产物已生成（DNS 白名单 / uBO 增强子集 / 连接层规则集）
test -s dist/dns_allow.txt && echo "dns_allow.txt OK"
test -s dist/adblock_collection_ubo_enhance.txt && echo "ubo_enhance.txt OK"
test -s dist/rulesets/adblock_clash.yaml && echo "rulesets OK"

# ⑧ 本地规则语法/冲突校验（改动 local_rules.txt 后执行）
python -m adblock_collection lint --config config/sources.yaml
```

**完成判定**：①≥规则数、②=0、③<5 源、④passed=True、⑤已提交全部 dist 变更、⑥两个等式均为 True、⑦增量产物非空（DNS 白名单 / uBO 增强 / 连接层规则集）、⑧lint 无 error。

---

## 3. 修改上游源（sources.yaml）

**适用场景**：新增/删除/替换某个上游列表。

**前置检查**：新源 URL 必须可访问（本环境 jsdelivr 被黑洞，避开）：

```bash
curl -s -o /dev/null -w "%{http_code}\n" --max-time 25 "新源URL"   # 期望 200
```

**标准命令序列**：

```bash
# 1) 编辑 config/sources.yaml 添加/修改源条目（注意 category / compatible / dns_policy）
# 2) 校验无重复
python3 -m adblock_collection sources | awk '{print $4}' | sort | uniq -d   # 应无输出

# 3) 手动构建（见第 2 节）
python3 -m adblock_collection build --out dist --split-by-category
echo "exit=$?"
```

**自检**：
- 新增源出现在 `source_stats` 输出中（构建日志）
- 质量门禁通过（规则增长在阈值内；大源可能触发增长告警，按第 5 节判定）
- 误杀回归 0 违规

**注意**：
- 新增「加速类 hosts 源」会破坏访问，禁止（历史教训：加速 hosts 源导致站点无法打开）。
- 已知持续失败的源（GOODBYEADS / HalfLife ad）可容忍，不阻断。
- **不要**随意改构建参数覆盖 dist（本地构建须与 CI 同款：`--split-by-category`，四项增强默认开启），否则 dist 与 CI 不一致（历史教训）。

**完成判定**：门禁通过、回归 0 违规、dist 产物正确，提交 `config/sources.yaml` + dist。

---

## 4. 修改白名单（false_positives.yaml）

**适用场景**：用户反馈某大站被整域误封，需加入 `allow` 保护。

> 说明：本节维护的是**误杀回归保护清单**（命中即构建失败），防止误拦关键站点。
> 若要在产物中**真正放行**某个域名（含 DNS 允许清单），请改 `config/lists/allowlist.txt`，见第 8 节。

**标准命令序列**：

```bash
# 1) 编辑 config/false_positives.yaml，向 allow 追加域名（裸域即可，如 tencent.com）
# 2) 构建验证
python3 -m adblock_collection build --out dist --split-by-category
# 3) 确认回归通过（allow_violations 应 = 0）
python3 -c "import json;d=json.load(open('dist/regression_report.json'));print(d['allow_violations'])"
```

**自检**：被加入的域名不再被整域阻断（精确匹配，子域广告仍拦截）：

```bash
python3 - <<'PY'
import re
allow=["tencent.com"]  # 换成你加的域名
bad=[]
for line in open("dist/adblock_collection_full.txt",encoding="utf-8"):
    l=line.rstrip("\n")
    if l.startswith("||") and l.endswith("^") and "$" not in l:
        d=l[2:-1].lower()
        if d in allow: bad.append(d)
print("仍被整域阻断的 allow 域名(应为空):", bad)
PY
```

**完成判定**：回归 `allow_violations=0`，且 allow 域名本体不被整封、子域广告规则仍在。

**`block` 清单（防漏拦回归）**：向 `config/false_positives.yaml` 的 `block` 追加域名，可断言这些域名应保持整域阻断，防止 C1/C7 之类例外收紧后出现回退（CI 首次纳入时已补齐 33 个非阻断型例外域与 108 个导航放大域）。`block_missing` **默认只告警**，不计入失败；如需在缺失时阻断构建，在 `config/sources.yaml` 增加：

```yaml
regression:
  block_missing_strict: true
```

回归结果见 `dist/regression_report.json` 的 `block_missing` 与 `block_missing_strict` 字段。

---

## 5. 质量门禁失败处置

**判定逻辑**：先判断是「正常增长」还是「回归」：

| 场景 | 判定 | 处置 |
|------|------|------|
| 新增了较大的上游源 | 正常增长 | 无操作，接受本次失败记录；或调整阈值 |
| 规则数突然骤降 | 回归/异常 | 检查源是否大面积失败、是否误用参数 |
| 基线被污染（previous_metrics 异常小） | 基线错误 | 从 git 恢复 `dist/previous_metrics.json`（历史教训） |
| 类别增长异常（如 phishing 1→16） | 单类新规则涌入 | 确认来源可信后接受 WARNING |

**恢复基线**（仅当确认是基线错误）：

```bash
git checkout -- dist/previous_metrics.json
```

**完成判定**：确认增长原因，基线正确，重新构建通过。

---

## 6. 源失效处置

**适用场景**：`sources_status.json` 显示失败源。

**标准排查**：

```bash
# 1) 看哪些源失败
python3 -c "import json;d=json.load(open('dist/sources_status.json'));print(d['failed_sources'])"

# 2) 手动测试源可达性
curl -s -o /dev/null -w "%{http_code}\n" --max-time 25 "失败源的url"

# 3) 检查是否有镜像可用（源可配 mirror 字段）
```

**处置矩阵**：

| 情况 | 处置 |
|------|------|
| 临时网络抖动 | 不处理，等下次构建自动恢复 |
| 源已 404 / 仓库删除 | 从 sources.yaml 删除该源，或替换可用镜像 |
| 源持续超时 | 加 mirror，或标记容忍 |
| 失败源 ≥ 5 | 视为整体异常，检查网络/代理，暂缓发布 |

**完成判定**：失败源恢复或已清理，`sources_status.json` 失败数 < 5。

---

## 7. 修改本地增强规则（local_rules.txt）

**适用场景**：补充上游未覆盖的广告（如网页版直播广告）。

**标准命令序列**：

```bash
# 1) 编辑 config/local_rules.txt，追加精确选择器
#    规则格式：域名##选择器（元素隐藏） 或 ||域名^（网络阻断）
# 2) 构建自动校验并纳入
python3 -m adblock_collection build --out dist --split-by-category
echo "exit=$?"   # =2 说明有通配误伤，需修正
```

**铁律**：
- **禁止**通配误伤：`##*`、`##body`、`*##`、`##.a *`（构建会拦截，返回码 2）。
- 元素隐藏规则必须基于真实页面 DOM（F12 定位广告容器），不要猜类名。
- 优先用属性包含匹配 `[class*="ad"]`（允许）而非裸 `*`。

**完成判定**：exit=0，规则进入 dist 产物，回归 0 违规。

---

## 8. 修改自定义黑白名单（config/lists/）

**适用场景**：在上游规则之外稳定维护自己的阻断或放行，或覆盖上游的错误判定。

**文件与来源**：

| 文件 | 来源名 | 作用 |
|------|--------|------|
| `config/lists/blocklist.txt` | `LocalBlocklist` | 自定义阻断 |
| `config/lists/allowlist.txt` | `LocalAllowlist` | 自定义放行（含 DNS 允许清单） |

**标准命令序列**：

```bash
# 1) 编辑名单文件，支持标准 Adblock 语法与裸域名简写
#    blocklist.txt: example.com        -> ||example.com^
#    allowlist.txt: example.com        -> @@||example.com^
# 2) 校验语法与通配误伤（默认即校验 config/lists/ 两文件与 local_rules.txt）
python3 -m adblock_collection lint --config config/sources.yaml
# 3) 构建
python3 -m adblock_collection build --out dist --split-by-category
echo "exit=$?"   # =2 说明名单含通配误伤，需修正
```

**优先级**：自定义白名单 > 自定义黑名单 > 上游例外 > 上游 `$important` > 上游普通阻断。

**产物**：`config/lists/allowlist.txt` 的整域全局例外会写入 `dist/dns_allow.txt`，`manifest.json` 标记其 `source` 为 `custom_allowlist`；上游例外不再派生 DNS 白名单。

**铁律**：与 `local_rules.txt` 相同——**禁止**通配误伤（`##*`、`##body`、`*##`、`##.a *`），否则构建返回码 2。

**完成判定**：lint 无 error，exit=0，自定义阻断进入产物、自定义放行生效且出现在 `dns_allow.txt`。

---

## 9. CI 自动提交冲突处置

**适用场景**：本地 push 被拒（远程有 auto update 提交）。

**标准处置**：

```bash
git fetch origin main
git pull --rebase --autostash
# 若 dist 冲突：
#   用本地（含代码改动）版本解决 dist，或按 FLOW.md 重建后提交
git push
```

**注意**：
- 不要 force push。
- 如果 rebase 后 dist 与远程 CI 版本有差异，以「用 CI 同款参数本地重建的 dist」为准。

**完成判定**：push 成功，`git rev-list --left-right --count HEAD...origin/main` 为 `0 0`。

---

## 10. 连接层规则集与 manifest 字段

**产物**（`dist/rulesets/`，与 DNS 域名集合同源，均尊重 `config/lists/allowlist.txt`）：

| 文件 | 格式 | 算子语义 |
|------|------|----------|
| `adblock_clash.yaml` | mihomo `behavior: domain` | `+.domain` 含子域；裸域名精确 |
| `adblock_singbox.json` | sing-box 源规则集（version 3） | `domain_suffix` / `domain` |
| `adblock_surge.list` | Surge 逐行 | `DOMAIN-SUFFIX` / `DOMAIN`；超 jsDelivr 上限拆 `_partNN` |
| `adblock_surge_domain_set.txt` | Surge `DOMAIN-SET` | 前导点含子域；裸域名精确（单文件，体积更小） |
| `adblock_quanx.list` | Quantumult X | `host-suffix` / `host`；超限拆 `_partNN` |

**接入片段**：见 README「连接层规则集用法」。Surge 推荐 `DOMAIN-SET,<url>,REJECT` 单文件。

**manifest.json 字段**（`file` 是唯一键，`name` 仅为逻辑分组，同一 `name` 可对应多份产物）：

- 每条目：`file`（唯一，相对 manifest 的路径，含 `rulesets/`、`security/` 等目录前缀）、`name`（分组名，非唯一）、`format`、`rules`、`source`（本地名单来源，仅 build 生成）、`parts`（分片）、`bytes`（实际文件大小）、`sha256`（文件内容哈希，供订阅端校验）、`empty`（`rules == 0` 时标注，表示该类无可进 DNS 的规则）。
- 顶层：`generator`、`generated_files`、`versions`（parser / normalizer / classifier）、`generated_at`（UTC，基线比对时忽略）、`sources_status`（本次上游健康状态，含 `complete` / `failed_sources` / `total_sources`，便于订阅端判断数据完整性）。

**构建差异与误拦复核**（依赖上一批规则指纹，CI 全新 checkout 无此文件）：

- `dist/build_diff.txt`：本批 vs 上批的逐条新增/移除（`MAX_LINES_PER_SIDE` 截断）。
- `dist/new_domain_review.json`：本批**新出现的整域阻断**复核清单（C6-2），`risk` 分 `critical`（命中 `false_positives.yaml` 的 `allow`）/`high`（可注册域本体）/`low`（子域）；命中 allow 时构建日志 `warning`，不阻断。

**自检**：

```bash
python3 - <<'PY'
import json
d = json.load(open("dist/manifest.json"))
print("versions:", d["versions"])
print("empty 条目:", [e["file"] for e in d["generated_files"] if e.get("empty")])
print("唯一 file:", len({e["file"] for e in d["generated_files"]}), "条目:", len(d["generated_files"]))
PY
test -s dist/rulesets/adblock_surge_domain_set.txt && echo "DOMAIN-SET OK"
```

**注意**：`stats` 命令按既有 manifest 的 `file` 合并，仅重算 `.txt` 的 `rules`，保留规则集条目与 `source`/`format`/`parts`；manifest 缺失时回退为按 `*.txt` 重建，此路径无法恢复 `source`。

---

## 快速索引

| 想做什么 | 看哪节 |
|----------|--------|
| 本地完整构建 | 第 2 节 |
| 验证增强开关 | 第 2 节 |
| 加/换一个广告源 | 第 3 节 |
| 某大站被误封 | 第 4 节 |
| 构建报门禁失败 | 第 5 节 |
| 某个源挂了 | 第 6 节 |
| 补一条直播广告规则 | 第 7 节 |
| 自定义黑/白名单、覆盖上游 | 第 8 节 |
| push 被拒 / rebase 冲突 | 第 9 节 |
| 连接层规则集 / manifest 字段 | 第 10 节 |
