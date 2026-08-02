# Requirements Document

## Introduction

本项目是一个广告过滤规则聚合器，定期从多个主流上游源收集广告过滤规则，进行格式转换、合并和去重处理，最终输出兼容 Adblock Plus、uBlock Origin、AdGuard 等常见广告过滤应用程序的统一规则列表。项目通过 GitHub Actions 每 20 分钟自动运行，确保与上游同步，减少误杀。

## Glossary

- **上游规则源 (Upstream Source)**: 提供原始广告过滤规则的远程 URL 端点，由社区或组织维护
- **规则 (Rule)**: 一条广告过滤指令，定义需要拦截或放行的网络请求
- **过滤列表 (Filter List)**: 多条规则的有序集合，通常以 `.txt` 文件形式发布
- **Adblock 语法 (Adblock Syntax)**: 以 Adblock Plus 为代表的过滤规则语法，是广告过滤领域的事实标准格式
- **Hosts 语法 (Hosts Syntax)**: 以域名/IP 映射为基础的过滤规则语法，常用于 DNS 层过滤
- **去重 (Deduplication)**: 识别并移除语义相同的重复规则，按上游源优先级保留高优先级版本
- **源优先级 (Source Priority)**: 每个上游源分配一个数值优先级，数值越小优先级越高，去重时保留高优先级源的规则
- **误杀 (False Positive)**: 将合法内容错误拦截的情况

## Requirements

### Requirement 1: 上游规则源配置

**User Story:** AS 维护者, I want 灵活配置多个上游规则源，so that 可以根据需要增减规则来源

#### Acceptance Criteria

1. THE system SHALL support configuration of multiple upstream rule source URLs via a declarative configuration file
2. THE system SHALL allow each upstream source to specify its name, URL, and source type (adblock syntax or hosts syntax)
3. THE system SHALL validate each upstream source URL accessibility before processing
4. IF an upstream source fails to respond, THE system SHALL record the failure and continue processing remaining sources

### Requirement 2: 规则下载与同步

**User Story:** AS 维护者, I want 每 20 分钟自动从上游拉取最新规则，so that 输出列表能即时反映上游变化

#### Acceptance Criteria

1. WHEN the GitHub Actions workflow triggers, THE system SHALL download rules from all configured upstream sources
2. THE system SHALL set a timeout of 30 seconds for each upstream source download request
3. IF an upstream source download fails, THE system SHALL retry once after 5 seconds
4. THE system SHALL record the ETag or Last-Modified header from each upstream response to enable future conditional requests
5. THE system SHALL maintain a download history log containing timestamps, source names, HTTP status codes, and rule counts

### Requirement 3: 规则格式解析与转换

**User Story:** AS 维护者, I want 自动识别和转换不同格式的规则，so that 来自不同源的规则能统一处理

#### Acceptance Criteria

1. THE system SHALL parse adblock-syntax rules, including basic network filters, exception rules (starting with `@@`), hiding rules (starting with `##`), and header comments (starting with `!`)
2. THE system SHALL parse hosts-syntax rules and convert them to adblock-syntax equivalents
3. THE system SHALL strip metadata headers (lines starting with `!` or `[`) from rules during transformation, preserving only the effective rules
4. IF a rule is malformed or unparseable, THE system SHALL skip the rule and record the skip count per source
5. THE system SHALL normalize domain patterns in rules (e.g., removing `www.` prefix where appropriate)

### Requirement 4: 规则合并与去重

**User Story:** AS 用户, I want 多条上游源的规则合并为一份统一列表且无重复，so that 订阅一份列表即可覆盖多个源

#### Acceptance Criteria

1. THE system SHALL merge rules from all upstream sources into a single rule set
2. THE system SHALL identify and remove semantically identical rules, retaining only one copy
3. THE system SHALL detect subset rule conflicts where a broader rule already covers a more specific rule, and remove the redundant specific rule
4. THE system SHALL preserve exception rules (whitelist rules starting with `@@`) and place them before corresponding blocking rules in the output
5. THE system SHALL deduplicate using rule normalization that strips unnecessary whitespace and standardizes URL encoding before comparison
6. THE system SHALL maintain rule priority: exception rules take precedence over blocking rules, and rules from higher-priority sources take precedence over lower-priority sources when conflicts exist

### Requirement 5: 输出生成

**User Story:** AS 用户, I want 生成兼容主流广告过滤器的规则文件，so that 可以直接订阅使用

#### Acceptance Criteria

1. THE system SHALL generate a single output file in adblock-syntax format compatible with Adblock Plus, uBlock Origin, and AdGuard
2. THE system SHALL include a header block in the output file containing: project name, generation timestamp, rule source summary, and total rule count
3. THE system SHALL validate the output by ensuring all rules conform to the adblock syntax specification
4. THE system SHALL write the output file to a designated output directory, ready for publication via GitHub Pages or raw file access

### Requirement 6: GitHub Actions 自动化

**User Story:** AS 维护者, I want 在 GitHub 上全自动运行，so that 无需手动维护即可保持规则列表更新

#### Acceptance Criteria

1. THE system SHALL be configured as a GitHub Actions workflow that runs every 20 minutes using cron schedule
2. THE system SHALL detect if any upstream source has new content since the last run, and only regenerate output when changes are detected
3. WHEN new rules are generated, THE system SHALL automatically commit and push the updated output files to the repository
4. THE system SHALL prevent concurrent workflow runs to avoid race conditions
5. IF the workflow fails, THE system SHALL log detailed error information for debugging

### Requirement 7: 兼容性验证

**User Story:** AS 用户, I want 输出的规则文件被主流广告过滤器正确识别，so that 不会出现格式不兼容的问题

#### Acceptance Criteria

1. THE system SHALL validate that no output rule exceeds 4000 characters (uBlock Origin single-rule length limit)
2. THE system SHALL ensure all exception rules use correct `@@` prefix syntax
3. THE system SHALL verify that the generated filter list loads without syntax errors in Adblock Plus test environment
4. THE system SHALL include a `! Title:` and `! Expires:` metadata directive in the output header for compatibility with auto-refresh clients

### Requirement 8: 变更日志

**User Story:** AS 用户, I want 查看每次更新的变更记录，so that 了解规则列表的变化

#### Acceptance Criteria

1. WHEN output files are regenerated, THE system SHALL produce a changelog recording the delta: added rules count, removed rules count, and changed upstream sources
2. THE system SHALL retain changelog entries for the last 90 days
3. THE system SHALL include active source names, their individual rule counts, and their last successful update timestamps in the changelog

## Selected Upstream Sources

The system includes the following upstream filter sources by default:

| # | Source Name | Priority | Type | URL |
|---|-------------|----------|------|-----|
| 1 | EasyList | 1 | adblock | `https://easylist-downloads.adblockplus.org/easylist.txt` |
| 2 | EasyPrivacy | 2 | adblock | `https://easylist-downloads.adblockplus.org/easyprivacy.txt` |
| 3 | AdGuard Base | 3 | adblock | `https://raw.githubusercontent.com/AdguardTeam/FiltersRegistry/master/filters/filter_2_Base/filter.txt` |
| 4 | AdGuard DNS | 4 | adblock | `https://adguardteam.github.io/AdGuardSDNSFilter/Filters/filter.txt` |
| 5 | Peter Lowe's List | 5 | adblock | `https://pgl.yoyo.org/adservers/serverlist.php?hostformat=adblockplus&showintro=0&mimetype=plaintext` |
| 6 | Anti-AD | 6 | adblock | `https://raw.githubusercontent.com/privacy-protection-tools/anti-AD/master/anti-ad-easylist.txt` |
