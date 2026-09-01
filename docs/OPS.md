# 操作规程（RUNBOOK / OPS）

本文档定义 GZ 广告规则合集日常操作的**标准流程**。每个操作给出：适用场景 → 标准命令序列 → 自检清单 → 完成判定。遵循「宁愿少拦截，不要误拦截」原则。

配套阅读：`docs/FLOW.md`（流程各阶段细节与失败处置矩阵）。

---

## 1. 日常自动流程（无需人工）

**触发**：GitHub Actions 每日 03:00 UTC 定时运行（`.github/workflows/build.yml`），main 分支 push 时若涉及代码也会触发。

**CI 自动做的事**：
1. 拉取仓库 → 安装依赖 → 用缓存下载源
2. 执行构建命令 `python3 -m adblock_collection build --out dist --split-by-category --redundant`（CI 镜像中 `python` 与本地 `python3` 等价）
3. 健康检查（规则数 < 30 万 或 失败源 ≥ 5 时输出 WARNING，不阻断）
4. dist 有变化则自动提交 `chore: auto update filter lists [skip ci]` 并推送

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

# 3) 完整构建（CI 同款参数）
python3 -m adblock_collection build --out dist --split-by-category --redundant
echo "exit=$?"   # 0=成功; 1=门禁/回归失败; 2=本地规则违规
```

**构建后自检清单**（5 项）：

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
```

**完成判定**：①≥规则数、②=0、③<5 源、④passed=True、⑤已提交全部 dist 变更。

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
python3 -m adblock_collection build --out dist --split-by-category --redundant
echo "exit=$?"
```

**自检**：
- 新增源出现在 `source_stats` 输出中（构建日志）
- 质量门禁通过（规则增长在阈值内；大源可能触发增长告警，按第 5 节判定）
- 误杀回归 0 违规

**注意**：
- 新增「加速类 hosts 源」会破坏访问，禁止（历史教训：加速 hosts 源导致站点无法打开）。
- 已知持续失败的源（GOODBYEADS / HalfLife ad）可容忍，不阻断。
- **不要**随意用不同参数构建覆盖 dist（如不带 `--redundant`），否则 dist 与 CI 不一致（历史教训）。

**完成判定**：门禁通过、回归 0 违规、dist 产物正确，提交 `config/sources.yaml` + dist。

---

## 4. 修改白名单（false_positives.yaml）

**适用场景**：用户反馈某大站被整域误封，需加入 `allow` 保护。

**标准命令序列**：

```bash
# 1) 编辑 config/false_positives.yaml，向 allow 追加域名（裸域即可，如 tencent.com）
# 2) 构建验证
python3 -m adblock_collection build --out dist --split-by-category --redundant
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
python3 -m adblock_collection build --out dist --split-by-category --redundant
echo "exit=$?"   # =2 说明有通配误伤，需修正
```

**铁律**：
- **禁止**通配误伤：`##*`、`##body`、`*##`、`##.a *`（构建会拦截，返回码 2）。
- 元素隐藏规则必须基于真实页面 DOM（F12 定位广告容器），不要猜类名。
- 优先用属性包含匹配 `[class*="ad"]`（允许）而非裸 `*`。

**完成判定**：exit=0，规则进入 dist 产物，回归 0 违规。

---

## 8. CI 自动提交冲突处置

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

## 快速索引

| 想做什么 | 看哪节 |
|----------|--------|
| 本地完整构建 | 第 2 节 |
| 加/换一个广告源 | 第 3 节 |
| 某大站被误封 | 第 4 节 |
| 构建报门禁失败 | 第 5 节 |
| 某个源挂了 | 第 6 节 |
| 补一条直播广告规则 | 第 7 节 |
| push 被拒 / rebase 冲突 | 第 8 节 |
