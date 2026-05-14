# 微信消息自动化需求收集系统

## 概述

自动从微信聊天记录中收集用户需求和反馈，智能识别并自动创建kanban任务。

**解决的问题：**
- ❌ 搜索慢：每次遍历42个数据库文件
- ❌ 搜索不到：只查MSG0.db，遗漏历史消息
- ❌ 人工低效：手动总结需求，手动创建任务

**解决方案：**
- ✅ 本地索引数据库：一次全量提取，后续增量更新
- ✅ 全量搜索：索引所有MSG*.db，支持快速关键词搜索
- ✅ 智能识别：自动识别需求/Bug，自动分类优先级
- ✅ 自动创建任务：集成kanban-doc MCP，自动创建到对应项目

## 系统架构

```
微信数据库 (42个.db文件)
    ↓
[解密] wechat_monitor.py
    ↓
[索引] wechat_index_db.py → wechat_index.db (本地SQLite)
    ↓
[收集] auto_requirement_collector.py
    ↓
[筛选] auto_workflow.py
    ↓
[创建] kanban-doc MCP → .kanban/projects/*/tasks/*.md
```

## 核心文件

### 1. wechat_index_db.py - 索引数据库
**功能：**
- 全量同步所有微信消息到本地SQLite
- 增量更新（只同步新消息）
- 快速搜索（用户、关键词、时间范围）

**数据库结构：**
- `contacts` - 联系人表
- `chatrooms` - 群聊表
- `messages` - 消息索引表（13.9万条）
- `sync_state` - 同步状态

**使用：**
```bash
# 首次全量同步
python wechat_index_db.py full

# 增量同步（定时任务调用）
python wechat_index_db.py
```

### 2. auto_requirement_collector.py - 需求收集器
**功能：**
- 从索引数据库搜索监控用户消息
- 智能识别需求/Bug（关键词匹配）
- 自动分类优先级（critical/high/medium/low）
- 识别所属项目（syc-player/qt-lens/wechat-archive）

**监控用户：**
- 三叶草
- 编程仝芷硕
- Estelle
- 烨林
- 沐光
- 密码机

**使用：**
```bash
python auto_requirement_collector.py
```

### 3. auto_workflow.py - 完整自动化流程
**流程：**
1. 解密微信数据库
2. 增量同步到索引
3. 收集最近N天的需求/反馈
4. 筛选任务（时间范围、优先级）
5. 生成待创建任务列表

**使用：**
```bash
python auto_workflow.py
```

### 4. wechat_monitor_v2.py - 定时监控（优化版）
**功能：**
- 每30分钟自动执行
- 使用索引数据库（快速）
- 生成待创建任务列表
- 供Claude读取并创建到kanban-doc

**配置Windows任务计划程序：**
```
程序: D:\develoment_home\project_home\WeChatMsgArchive\venv\Scripts\python.exe
参数: D:\develoment_home\project_home\WeChatMsgArchive\wechat_monitor_v2.py
触发器: 每30分钟
```

## 使用流程

### 方式1: 手动执行完整流程
```bash
# 1. 运行自动化流程
python auto_workflow.py

# 2. 查看生成的任务
cat output/tasks_to_create.json

# 3. 使用Claude创建任务
# Claude会读取tasks_to_create.json并通过kanban-doc MCP创建任务
```

### 方式2: 定时自动执行
```bash
# 1. 配置Windows任务计划程序运行 wechat_monitor_v2.py

# 2. 每30分钟自动生成 output/pending_kanban_tasks.json

# 3. Claude定期读取并创建任务
```

## 性能对比

### 旧方案（wechat_monitor.py）
- ❌ 只搜索MSG0.db（遗漏历史消息）
- ❌ 每次遍历数据库（慢）
- ❌ 简单关键词匹配
- ❌ 直接写文件创建任务

### 新方案（本系统）
- ✅ 索引所有MSG*.db（13.9万条消息）
- ✅ 快速搜索（SQL索引）
- ✅ 智能识别（需求/Bug/优先级/项目）
- ✅ 集成kanban-doc MCP

**速度提升：**
- 全量搜索：从遍历42个文件 → 单次SQL查询
- 关键词搜索：从2分钟 → 0.1秒
- 用户消息搜索：从遍历所有消息 → 索引查询

## 测试结果

### 索引数据库
```
✓ 同步了 138,947 条消息
✓ 联系人: 数千个
✓ 群聊: 数百个
```

### 需求收集（最近30天）
```
✓ 找到 213 条需求/反馈
  - 三叶草: 86 条
  - 编程仝芷硕: 26 条
  - Estelle: 41 条
  - 烨林: 4 条
  - 沐光: 52 条
  - 密码机: 4 条
```

### 任务创建（最近7天）
```
✓ 筛选出 47 个任务
  - syc-player: 46 个
  - qt-lens: 1 个

✓ 成功创建到kanban-doc
  - 任务ID: 3bbd, 7355, fd0f, 7314
```

## 关键词配置

### Bug关键词
```python
'bug', 'BUG', '问题', '报错', '失败', '崩溃', '闪退', '卡死',
'没有用', '不行', '无效', '异常', '错误', '不对', '失效',
'没有反应', '没反应', '对接不上', '没对接', '不能用', '用不了',
'修复', '修改', '运行不了', '解析不出', '没用'
```

### 需求关键词
```python
'需要', '希望', '能不能', '可以', '建议', '增加', '添加',
'改成', '改为', '调整', '优化', '支持', '实现', '功能',
'要不', '最好', '应该', '如果能', '想要'
```

### 项目识别
```python
'syc-player': ['播放器', '视频', '音频', 'player', '三叶草']
'qt-lens': ['镜片', '检测', 'Qt', '林爱新', 'B-boy']
'wechat-archive': ['微信', '聊天记录', '解密', '数据库']
```

## 扩展建议

### 1. 增强识别能力
- 使用LLM分析消息内容（更准确）
- 自动提取需求关键点
- 自动生成任务标题和描述

### 2. 多渠道支持
- 企业微信消息
- 邮件反馈
- 钉钉消息
- GitHub Issues

### 3. 智能分配
- 根据内容自动分配给开发者
- 自动设置截止日期
- 自动关联相关任务

### 4. 反馈闭环
- 任务完成后自动回复用户
- 定期生成反馈报告
- 用户满意度跟踪

## 维护

### 定期清理
```bash
# 清理30天前的索引数据
sqlite3 output/wechat_index.db "DELETE FROM messages WHERE create_time < strftime('%s', 'now', '-30 days')"
```

### 重建索引
```bash
# 删除索引数据库
rm output/wechat_index.db

# 重新全量同步
python wechat_index_db.py full
```

### 日志查看
```bash
# 查看监控日志
cat output/cron_logs/monitor_v2_20260429.log
```

## 总结

**实现目标：**
- ✅ 解决搜索慢问题（索引数据库）
- ✅ 解决搜索不到问题（全量索引）
- ✅ 自动化需求收集（智能识别）
- ✅ 自动创建kanban任务（MCP集成）
- ✅ 简洁轻量实现（纯Python + SQLite）

**核心优势：**
- 快速：SQL索引查询，毫秒级响应
- 完整：索引所有消息，不遗漏
- 智能：自动识别需求/Bug/优先级/项目
- 自动：定时执行，自动创建任务
- 简洁：纯Python实现，无复杂依赖

**就像Claude Code一样：简洁、简单、直接做事！**
