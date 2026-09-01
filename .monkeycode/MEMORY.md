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
