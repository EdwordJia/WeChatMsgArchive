# {{display_name}} 的用户画像

> 档案编号: `{{wxid}}`  
> 生成时间: {{generated_at}}  
> 数据来源: 微信聊天记录分析

---

## 📊 核心指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 总发言数 | **{{total_messages}}** 条 | 统计周期内的消息总量 |
| 总字数 | **{{total_chars}}** 字 | 文本内容累计字数 |
| 活跃天数 | **{{active_days}}** 天 | 有发言记录的天数 |
| 首次出现 | {{first_seen}} | 最早发言时间 |
| 最近活跃 | {{last_seen}} | 最晚发言时间 |
| 平均消息长度 | **{{avg_message_length}}** 字/条 | 文本消息平均长度 |
| 参与群聊 | **{{groups_active_in}}** 个 | 活跃群聊数量 |

---

## 🏷️ 个性标签

{{#if tags}}
{{#each tags}}
- `{{_item}}`
{{/each}}
{{else}}
*暂无标签*
{{/if}}

### 一句话画像

> {{persona_summary}}

---

## ⏰ 活跃时段分析

### 24小时分布

| 时段 | 消息数 | 可视化 |
|------|--------|--------|
{{#each hourly_list}}
| {{hour}} | {{count}} | {{#if count}}{{ '█' * (count // max(hourly_list, key=lambda x: x['count'])['count'] // 5 + 1) if hourly_list else '' }}{{/if}} |
{{/each}}

### 工作日分布

| 星期 | 消息数 |
|------|--------|
{{#each weekday_list}}
| {{day}} | {{count}} |
{{/each}}

### 时间特征

- **工作生活比**: {{work_life_ratio}}（1.0 表示完全在工作时间发言）
- {{#if work_life_ratio > 0.6}}倾向于在工作时间交流，可能是工作伙伴或项目参与者。{{else}}{{#if work_life_ratio < 0.3}}倾向于在非工作时间交流，更偏向生活化社交。{{else}}工作与生活时间分布均衡。{{/if}}{{/if}}

---

## 💬 内容偏好

### 消息类型分布

| 类型 | 数量 | 占比 |
|------|------|------|
{{#each type_list}}
| {{name}} | {{count}} | {{percent}} |
{{/each}}

### 内容特征

- **最大单条消息**: {{max_message_length}} 字
- **链接分享次数**: {{url_share_count}} 次
- **文件分享次数**: {{file_share_count}} 次
- **图片分享次数**: {{image_share_count}} 次

---

## 👥 社交关系

### 最常互动对象（Top 5）

| 排名 | 对象 | 互动次数 |
|------|------|----------|
{{#each interact_list}}
| {{_index + 1}} | {{name}} | {{count}} |
{{/each}}

### 群聊参与

{{#if groups_joined}}
参与群聊列表：
{{#each groups_joined}}
- `{{_item}}`
{{/each}}
{{else}}
*未检测到群聊参与记录*
{{/if}}

---

## 📝 原始数据摘要

```json
{
  "wxid": "{{wxid}}",
  "display_name": "{{display_name}}",
  "total_messages": {{total_messages}},
  "active_days": {{active_days}},
  "tags": {{tags}}
}
```

---

*本档案由 WeChatMsgArchive 数据分析系统自动生成，仅供分析参考。*
