# Adblock Filter Aggregator

[![Update Filter List](https://github.com/wansheng8/GZ/actions/workflows/update.yml/badge.svg)](https://github.com/wansheng8/GZ/actions/workflows/update.yml)

汇集 21 个主流广告过滤规则源，自动转换、合并、去重，每 20 分钟更新，兼容 Adblock Plus / uBlock Origin / AdGuard。

## 快速使用

将以下链接订阅到你的广告过滤器中：

```
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/filter.txt
```

> 该链接依托 GitHub 的 Fastly 全球 CDN 分发，中国大陆也可正常访问。

| 参数 | 值 |
|------|-----|
| 规则数 | ~500,000 条 (去重后) |
| 文件大小 | ~18 MB |
| 更新频率 | 每 20 分钟 |
| 上游源 | 21 个 |
| 兼容 | Adblock Plus / uBlock Origin / AdGuard |
| 格式 | Adblock 语法 |

## 上游规则源

### 官方源 (Easylist / AdGuard)

| # | 源 | 说明 |
|---|-----|------|
| 1 | EasyList | 国际网页广告过滤 |
| 2 | EasyPrivacy | 跟踪器/隐私保护 |
| 3 | Fanboy's Annoyance List | 移除 Cookie 提示、弹窗、社交按钮 |
| 4 | AdGuard Base | 基础广告过滤 |
| 5 | AdGuard Tracking Protection | 跟踪器保护 |
| 6 | AdGuard Annoyances | 移除弹窗、Cookie 提示 |
| 7 | AdGuard Social Media | 屏蔽社交媒体小组件 |
| 8 | AdGuard DNS | DNS 层级域名过滤 |

### 社区维护源

| # | 源 | 说明 |
|---|-----|------|
| 9 | Peter Lowe's List | 知名广告/跟踪服务器域名 |
| 10 | Anti-AD | 中文广告过滤 |
| 11 | Cats-Team AdRules | 综合广告过滤 |
| 12 | 大萌主-接口广告规则 | 接口广告专用 |
| 13 | DD-AD 去广告规则 | 综合去广告 |
| 14 | 晴雅去广告规则 | 中文去广告 |
| 15 | 秋风广告规则 (AWAvenue) | 中文广告过滤 |
| 16 | 海哥广告规则 | 中文广告过滤 |
| 17 | 那个谁520广告规则 | 中文广告过滤 |
| 18 | 10007 自动规则 | 自动化广告过滤 |
| 19 | Anti-AD 通用规则 | Anti-AD 官方通用版 |
| 20 | SMAdHosts 规则 | Hosts 格式广告域名 |
| 21 | 茯苓拦截规则 (FuLing) | 中文拦截规则 |

## 处理流程

```
21 个上游源 → aiohttp 并发下载 → 格式解析 → 标准化 → 精确去重 → 子集去重 → filter.txt
```

- **并发下载**: `aiohttp` 同时拉取全部源，30 秒超时，失败自动重试
- **ETag 增量**: 带条件请求头，上游未变化时跳过更新，节省流量
- **格式兼容**: hosts 格式自动转 adblock 语法，异常格式跳过不中断
- **两级去重**: 精确匹配去重（同规则保留高优先级源版本）+ 子集去重（父域名覆盖子域名）
- **规则排序**: 例外/白名单规则 (`@@`) 前置，随后是拦截规则和元素隐藏规则

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
3. 并发下载 21 个上游源
4. 解析 → 标准化 → 合并 → 去重
5. 检测到变更后自动 `git commit` 并 `push`

也可手动触发：`Actions → Update Filter List → Run workflow`

## 项目结构

```
├── main.py                     # 主入口
├── sources.yaml                # 上游源配置 (21 个)
├── requirements.txt            # Python 依赖
├── src/
│   ├── config.py               # YAML 配置加载
│   ├── downloader.py           # aiohttp 并发下载 + ETag + 重试
│   ├── parser.py               # Adblock/Hosts 语法解析
│   ├── normalizer.py           # 规则标准化
│   ├── merger.py               # 精确去重 + 子集去重
│   └── generator.py            # filter.txt + changelog 生成
├── tests/                      # 26 个测试用例
├── dist/
│   ├── filter.txt              # 输出的聚合过滤列表
│   └── changelog.md            # 变更日志
├── cache/                      # ETag 缓存
└── .github/workflows/update.yml
```

## License

MIT
