# Adblock Filter Aggregator

[![Update Filter List](https://github.com/wansheng8/GZ/actions/workflows/update.yml/badge.svg)](https://github.com/wansheng8/GZ/actions/workflows/update.yml)

汇集 52 个主流广告过滤规则源，自动转换、合并、去重，每 20 分钟更新，兼容 Adblock Plus / uBlock Origin / AdGuard。

## 快速使用

将以下任一链接订阅到你的广告过滤器中：

**精简版（推荐 / 8 官方源 / ~17.6 MB）：**
```
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/filter-lite.txt
```

**完整版（52 源 / ~40.0 MB）：**
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
| 精简版规则数 | 483.7K 条 (去重后) |
| 完整版规则数 | 1.5M 条 (去重后) |
| 精简版大小 | 17.6 MB |
| 完整版大小 | 40.0 MB |
| 更新频率 | 每 20 分钟 |
| 上游源 | 52 个 |
| 兼容 | Adblock Plus / uBlock Origin / AdGuard |
| 格式 | Adblock 语法 |
| 最后更新 | 2026-08-07 08:17 CST |

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
| 9 | Peter Lowe's List | Peter Lowe's List |
| 10 | Anti-AD | Anti-AD |
| 11 | Cats-Team AdRules | Cats-Team AdRules |
| 12 | 大萌主-接口广告规则 | 大萌主-接口广告规则 |
| 13 | DD-AD 去广告规则 | DD-AD 去广告规则 |
| 14 | 晴雅去广告规则 | 晴雅去广告规则 |
| 15 | 秋风广告规则 | 秋风广告规则 |
| 16 | 海哥广告规则 | 海哥广告规则 |
| 17 | 那个谁520广告规则 | 那个谁520广告规则 |
| 18 | 10007 自动规则 | 10007 自动规则 |
| 19 | Anti-AD 通用规则 | Anti-AD 通用规则 |
| 20 | SMAdHosts 规则 | SMAdHosts 规则 |
| 21 | 茯苓拦截规则 | 茯苓拦截规则 |
| 22 | uniartisan 基础规则 | uniartisan 基础规则 |
| 23 | uniartisan 增强规则 | uniartisan 增强规则 |
| 24 | HaGeZi Pro mini (移动优化) | HaGeZi Pro mini (移动优化) |
| 25 | X浏览器移动端规则 | X浏览器移动端规则 |
| 26 | 1Hosts (Lite) | 1Hosts (Lite) |
| 27 | HaGeZi Normal (轻量) | HaGeZi Normal (轻量) |
| 28 | HaGeZi Pro++ | HaGeZi Pro++ |
| 29 | HaGeZi Ultimate | HaGeZi Ultimate |
| 30 | OISD Small | OISD Small |
| 31 | OISD Big | OISD Big |
| 32 | HaGeZi 反盗版 | HaGeZi 反盗版 |
| 33 | HaGeZi 赌博拦截 | HaGeZi 赌博拦截 |
| 34 | HaGeZi Samsung 追踪拦截 | HaGeZi Samsung 追踪拦截 |
| 35 | HaGeZi Windows/Office 追踪拦截 | HaGeZi Windows/Office 追踪拦截 |
| 36 | HaGeZi Xiaomi 追踪拦截 | HaGeZi Xiaomi 追踪拦截 |
| 37 | HaGeZi 推荐白名单 | HaGeZi 推荐白名单 |
| 38 | Game Console 广告拦截 | Game Console 广告拦截 |
| 39 | No Google | No Google |
| 40 | Smart-TV 拦截 | Smart-TV 拦截 |
| 41 | ABPindo (印尼) | ABPindo (印尼) |
| 42 | EasyList Hebrew (以色列) | EasyList Hebrew (以色列) |
| 43 | YousList (韩国) | YousList (韩国) |
| 44 | Dandelion Sprout 北欧过滤 | Dandelion Sprout 北欧过滤 |
| 45 | Frellwit's 瑞典过滤 | Frellwit's 瑞典过滤 |
| 46 | AdGuard 土耳其广告服务器 | AdGuard 土耳其广告服务器 |
| 47 | ABPVN (越南) | ABPVN (越南) |
| 48 | uBlock filters - Ads | uBlock filters - Ads |
| 49 | uBlock filters - Badware risks | uBlock filters - Badware risks |
| 50 | uBlock filters - Privacy | uBlock filters - Privacy |
| 51 | uBlock filters - Quick fixes | uBlock filters - Quick fixes |
| 52 | uBlock filters - Unbreak | uBlock filters - Unbreak |

## 处理流程

```
52 个上游源 → aiohttp 并发下载 → 格式解析 → 标准化 → 精确去重 → 子集去重 → filter.txt
```

- **并发下载**: `aiohttp` 同时拉取全部源，30 秒超时，失败自动重试
- **ETag 增量**: 带条件请求头，上游未变化时跳过更新，节省流量
- **格式兼容**: hosts 格式自动转 adblock 语法，异常格式跳过不中断
- **两级去重**: 精确匹配去重（同规则保留高优先级源版本）+ 子集去重（父域名覆盖子域名）
- **规则排序**: 例外/白名单规则 (`@@`) 前置，随后是拦截规则和元素隐藏规则
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
3. 并发下载 52 个上游源
4. 解析 → 标准化 → 合并 → 去重
5. 检测到变更后自动 `git commit` 并 `push`
6. 自动更新 README.md 统计数据

也可手动触发：`Actions → Update Filter List → Run workflow`

## 项目结构

```
├── main.py                     # 主入口
├── sources.yaml                # 上游源配置 (52 个)
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
