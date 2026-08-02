# Adblock Filter Aggregator

汇集多个广告过滤规则源，自动转换、合并、去重，每 20 分钟更新，兼容 Adblock Plus / uBlock Origin / AdGuard。

## 快速使用

将以下链接订阅到你的广告过滤器中：

```
https://raw.githubusercontent.com/wansheng8/GZ/main/dist/filter.txt
```

| 参数 | 值 |
|------|-----|
| 当前规则数 | ~275,000 条 |
| 更新频率 | 每 20 分钟 |
| 兼容性 | Adblock Plus / uBlock Origin / AdGuard |

## 上游规则源

| 优先级 | 源 | 说明 |
|--------|-----|------|
| 1 | EasyList | 国际网页广告过滤，社区主导维护 |
| 2 | EasyPrivacy | 跟踪器/隐私保护 |
| 3 | AdGuard Base | AdGuard 基础广告过滤 |
| 4 | AdGuard DNS | DNS 层级广告域名过滤 |
| 5 | Peter Lowe's List | 知名广告服务器域名列表 |
| 6 | Anti-AD | 中文社区广告过滤 |

## 处理流程

```
sources.yaml → 并发下载 → 格式解析 → 标准化 → 精确去重 → 子集去重 → filter.txt
```

- 多源 `aiohttp` 并发下载，带 ETag 条件请求（无变化跳过更新）
- Hosts 格式自动转换为 Adblock 语法
- 去重策略：按优先级精确去重 + 子域名/子路径冗余规则消除
- 例外/白名单规则自动前置

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python3 main.py

# 测试
python3 -m pytest tests/ -v
```

## 自定义上游源

编辑 `sources.yaml`，按需增减：

```yaml
sources:
  - name: MySource
    url: https://example.com/filter.txt
    priority: 7        # 数值越小优先级越高
    enabled: true

settings:
  request_timeout: 30  # 下载超时（秒）
  retry_delay: 5       # 重试间隔（秒）
```

## 自动化

GitHub Actions 每 20 分钟自动触发，检测上游变更后自动提交更新。支持手动触发（Actions → Update Filter List → Run workflow）。

## 项目结构

```
├── main.py                     # 主入口
├── sources.yaml                # 上游源配置
├── requirements.txt            # Python 依赖
├── src/
│   ├── config.py               # 配置加载
│   ├── downloader.py           # 异步下载器
│   ├── parser.py               # 规则解析器
│   ├── normalizer.py           # 规则标准化
│   ├── merger.py               # 合并去重
│   └── generator.py            # 输出生成
├── tests/                      # 单元测试 + 集成测试
├── dist/filter.txt             # 输出的过滤列表
├── dist/changelog.md           # 变更日志
└── .github/workflows/update.yml # CI 工作流
```

## License

MIT
