# 项目与话题追踪档案

> 生成时间: {{generated_at}}  
> 话题总数: **{{total_projects}}** 个  
> 🟡 进行中: {{ongoing_count}} | 🟢 已完成: {{completed_count}} | 🔴 已停滞: {{stalled_count}}

---

## 📋 话题总览

| 状态 | 话题名 | 时间跨度 | 活跃天数 | 消息数 | 参与人数 |
|------|--------|----------|----------|--------|----------|
{{#each project_list}}
| {{status}} | {{topic_name}} | {{start_time}} ~ {{end_time}} | {{active_days}} | {{message_count}} | {{participant_count}} |
{{/each}}

---

{{#each project_list}}

## {{topic_name}}

**状态**: {{status}}  
**ID**: `{{topic_id}}`  
**关键词**: {{keywords}}  
**时间范围**: {{start_time}} ~ {{end_time}}（共 {{active_days}} 天）  
**消息总量**: {{message_count}} 条  
**参与人数**: {{participant_count}} 人

### 参与者贡献

| 成员 | 发言数 | 贡献度 |
|------|--------|--------|
{{#each participants}}
| {{name}} | {{count}} | {{#if count > 10}}高{{else}}{{#if count > 3}}中{{else}}低{{/if}}{{/if}} |
{{/each}}

### 关键消息摘录

{{#each key_messages}}
> **{{sender}}** @ {{talker}} {{time}}  
> {{content}}
>
{{/each}}

### 进展分析

{{#if status == '🟡 进行中'}}
该话题近期仍有讨论，建议持续关注后续进展。
{{/if}}
{{#if status == '🟢 已完成'}}
该话题已出现完成迹象（如"搞定"、"上线"等关键词），可归档。
{{/if}}
{{#if status == '🔴 已停滞'}}
该话题超过30天无新消息，可能已中断或转线下推进。
{{/if}}

---

{{/each}}

## 📊 统计分析

### 话题状态分布

```
进行中  {{ongoing_count}}  {{ '██████████' if ongoing_count > 0 else '' }}
已完成  {{completed_count}}  {{ '██████████' if completed_count > 0 else '' }}
已停滞  {{stalled_count}}  {{ '██████████' if stalled_count > 0 else '' }}
```

### 高参与度话题

按消息数排序，最活跃的 Top 5 话题：

{{#each project_list}}
{{#if _index < 5}}
1. **{{topic_name}}** — {{message_count}} 条消息，{{participant_count}} 人参与
{{/if}}
{{/each}}

### 长期追踪话题

按活跃天数排序，持续时间最长的 Top 5 话题：

{{#each project_list}}
{{#if _index < 5}}
1. **{{topic_name}}** — 持续 {{active_days}} 天
{{/if}}
{{/each}}

---

## 🔧 追踪配置说明

本档案中的话题通过以下方式自动发现：

1. **关键词匹配**: 预定义项目关键词库（开发、设计、会议、交付、学习等）
2. **突发检测**: 单日单群消息量 > 50 条时，提取高频词组作为话题
3. **状态推断**:
   - `ongoing` — 近期有持续讨论
   - `completed` — 近期出现完成关键词
   - `stalled` — 超过30天无新消息

### 自定义关键词

如需追踪特定业务话题，可在 `PROJECT_KEYWORDS` 配置中添加关键词：

```python
PROJECT_KEYWORDS = {
    '你的话题名': ['关键词1', '关键词2', '关键词3'],
}
```

---

*本档案由 WeChatMsgArchive 数据分析系统自动生成。*
