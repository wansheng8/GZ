"""Update README.md with current filter stats and source lists."""
import os
import sys
from datetime import datetime, timezone, timedelta

# 保证从任意工作目录运行时都能导入 src 包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import load_config


def load_sources(config_path="sources.yaml"):
    cfg = load_config(config_path)
    return cfg.sources, cfg


def get_file_stats(filepath):
    """Get rule count, file size, and basic stats for a filter file."""
    if not os.path.exists(filepath):
        return {"rules": 0, "size": 0, "exception": 0, "block": 0, "hide": 0}

    size = os.path.getsize(filepath)
    stats = {"rules": 0, "size": size, "exception": 0, "block": 0, "hide": 0}

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("!", "[")):
                continue
            stats["rules"] += 1
            if line.startswith("@@"):
                stats["exception"] += 1
            elif "##" in line or "#@#" in line or "#?#" in line or "#%#" in line:
                stats["hide"] += 1
            else:
                stats["block"] += 1

    return stats


def format_size(size_bytes):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def format_number(n):
    if n >= 1000000:
        return f"{n / 1000000:.1f}M"
    elif n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def generate_source_tables(sources):
    """Generate markdown tables for official and community sources."""
    official = [s for s in sources if s.lite]
    community = [s for s in sources if not s.lite]

    tables = []

    # Official sources
    tables.append("### 官方源 (Easylist / AdGuard)\n")
    tables.append("| # | 源 | 说明 |")
    tables.append("|---|-----|------|")
    descriptions = {
        "EasyList": "国际网页广告过滤",
        "EasyPrivacy": "跟踪器/隐私保护",
        "Fanboy's Annoyance List": "移除 Cookie 提示、弹窗、社交按钮",
        "AdGuard Base": "基础广告过滤",
        "AdGuard Tracking Protection": "跟踪器保护",
        "AdGuard Annoyances": "移除弹窗、Cookie 提示",
        "AdGuard Social Media": "屏蔽社交媒体小组件",
        "AdGuard DNS": "DNS 层级域名过滤",
    }
    for i, src in enumerate(official, 1):
        desc = descriptions.get(src.name, src.name)
        tables.append(f"| {i} | {src.name} | {desc} |")

    # Community sources
    tables.append(f"\n### 社区维护源\n")
    tables.append("| # | 源 | 说明 |")
    tables.append("|---|-----|------|")
    for i, src in enumerate(community, 1):
        tables.append(f"| {len(official) + i} | {src.name} | {src.name} |")

    return "\n".join(tables)


def build_readme(sources, settings, lite_stats, full_stats):
    """Build the full README content with current stats."""
    now = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M CST")
    total_sources = len([s for s in sources if s.enabled])
    lite_count = len([s for s in sources if s.enabled and s.lite])
    full_count = total_sources

    lite_size = format_size(lite_stats["size"])
    full_size = format_size(full_stats["size"])
    lite_rules = format_number(lite_stats["rules"])
    full_rules = format_number(full_stats["rules"])

    return f"""# Adblock Filter Aggregator

[![Update Filter List](https://github.com/wansheng8/GZ/actions/workflows/update.yml/badge.svg)](https://github.com/wansheng8/GZ/actions/workflows/update.yml)

汇集 {total_sources} 个主流广告过滤规则源，自动转换、合并、去重，每 20 分钟更新，兼容 Adblock Plus / uBlock Origin / AdGuard。

## 快速使用

将以下任一链接订阅到你的广告过滤器中：

**精简版（推荐 / {lite_count} 官方源 / ~{lite_size}）：**
```
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/filter-lite.txt
```

**完整版（{full_count} 源 / ~{full_size}）：**
```
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/filter.txt
```

**国内加速（精简版）：**
```
https://gh-proxy.com/https://raw.githubusercontent.com/wansheng8/GZ/main/dist/filter-lite.txt
```

**国内加速（完整版）：**
```
https://gh-proxy.com/https://raw.githubusercontent.com/wansheng8/GZ/main/dist/filter.txt
```

| 参数 | 值 |
|------|-----|
| 精简版规则数 | {lite_rules} 条 (去重后) |
| 完整版规则数 | {full_rules} 条 (去重后) |
| 精简版大小 | {lite_size} |
| 完整版大小 | {full_size} |
| 更新频率 | 每 20 分钟 |
| 上游源 | {total_sources} 个 |
| 兼容 | Adblock Plus / uBlock Origin / AdGuard |
| 格式 | Adblock 语法 |
| 最后更新 | {now} |

## 上游规则源

{generate_source_tables(sources)}

## 处理流程

```
{total_sources} 个上游源 → aiohttp 并发下载 → 格式解析 → 标准化 → 精确去重 → 子集去重 → filter.txt
```

- **并发下载**: `aiohttp` 同时拉取全部源，{settings.request_timeout} 秒超时，失败自动重试
- **ETag 增量**: 带条件请求头，上游未变化时跳过更新，节省流量
- **格式兼容**: hosts 格式自动转 adblock 语法，异常格式跳过不中断
- **两级去重**: 精确匹配去重（同规则保留高优先级源版本）+ 子集去重（父域名覆盖子域名）
- **规则排序**: 例外/白名单规则 (`@@`) 前置，随后是拦截规则和元素隐藏规则
- **仓库瘦身**: 连续 bot 提交用 amend 合并，历史只保留一份最新输出，避免大文件版本堆积
- **自动清理**: 每次运行后自动清理旧 Actions 记录，仅保留最近 3 条

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行聚合器
python3 main.py

# 运行测试 (26 个用例)
python3 -m pytest tests/ -v
```

## 自定义上游源

编辑 `sources.yaml`，增减源或调整优先级：

```yaml
sources:
  - name: 我的规则源
    url: https://example.com/filter.txt
    priority: 99       # 数值越小优先级越高，去重时优先保留
    enabled: true

settings:
  request_timeout: 30  # 下载超时 (秒)
  retry_delay: 5       # 失败重试间隔 (秒)
  max_rule_length: 4000 # 单条规则最大长度 (uBlock Origin 限制)
```

## 自动化

GitHub Actions 每 20 分钟 (`*/20 * * * *`) 自动触发：

1. 检出仓库
2. 安装 Python 依赖
3. 并发下载 {total_sources} 个上游源
4. 解析 → 标准化 → 合并 → 去重
5. 检测到变更后自动 `git commit` 并 `push`（连续 bot 提交自动 amend 合并，仓库只保留最新输出）
6. 自动更新 README.md 统计数据
7. 每天 00:30 生成版本快照（tag + GitHub Release 归档，保留最近 10 份）

也可手动触发：`Actions → Update Filter List → Run workflow`

历史版本快照可在 [Releases](https://github.com/wansheng8/GZ/releases) 页面下载。

## 项目结构

```
├── main.py                     # 主入口
├── sources.yaml                # 上游源配置 ({total_sources} 个)
├── requirements.txt            # Python 依赖
├── src/
│   ├── config.py               # YAML 配置加载
│   ├── downloader.py           # aiohttp 并发下载 + ETag + 重试
│   ├── parser.py               # Adblock/Hosts 语法解析
│   ├── normalizer.py           # 规则标准化
│   ├── merger.py               # 精确去重 + 子集去重
│   ├── generator.py            # filter.txt + changelog 生成
│   └── update_readme.py        # README.md 自动更新
├── tests/                      # 26 个测试用例
├── dist/
│   ├── filter.txt              # 输出的聚合过滤列表
│   ├── filter-lite.txt         # 精简版过滤列表
│   └── changelog.md            # 变更日志
├── cache/                      # ETag 缓存
└── .github/workflows/update.yml
```

## License

MIT
"""


def main():
    sources, settings = load_sources()
    lite_stats = get_file_stats(f"dist/{settings.lite_output_file}")
    full_stats = get_file_stats(f"dist/{settings.output_file}")

    readme = build_readme(sources, settings, lite_stats, full_stats)

    with open("README.md", "w") as f:
        f.write(readme)

    print(f"README.md updated: {lite_stats['rules']} lite / {full_stats['rules']} full rules")


if __name__ == "__main__":
    main()
