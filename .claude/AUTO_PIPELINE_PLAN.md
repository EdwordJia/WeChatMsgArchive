# 自动化Pipeline实现计划

## 目标

实现企业级自动化流程：**微信需求 → Kanban任务 → Agent执行**

```
输入：微信群消息
  ↓
自动识别需求（LLM）
  ↓
自动创建kanban任务
  ↓
自动分配agent（Kimi/Codex）
  ↓
自动执行
  ↓
输出：任务完成，汇报结果
```

---

## 当前问题

### 问题1：子代理数据不同步

**原因**：子代理使用独立context，看不到主会话的最新状态

**解决方案**：
1. 在调用子代理时，明确传递"查询最新数据"的指令
2. 要求子代理先执行 `wechat-decrypt-db` skill刷新数据库
3. 直接查询MSG1.db（最新消息在这里），不查索引库

**示例**：
```python
Agent(
    subagent_type="kimi-secretary",
    prompt="""
    1. 先执行 wechat-decrypt-db skill 刷新数据库
    2. 直接查询 MSG1.db（不要查索引库）
    3. 查询时间范围：2026-05-14 00:00:00 至今
    4. 群ID：50241909905@chatroom
    """
)
```

### 问题2：输入→输出链路需要人工干预

**原因**：当前流程是半自动的，需要用户不断提示

**解决方案**：构建完整的自动化Pipeline

---

## 实现方案

### 架构设计

```
┌───────────────────────────────┐
│         触发器（3种方式）                │
│  1. 定时触发（CronCreate，每小时）       │
│  2. 实时触发（watchdog监听数据库变化）     │
│  3. 手动触发（用户说"同步需求"）           │
└────────────┬──────────────┘
            ↓
┌────────────────────────┐
│      AutoPipeline（自动化流程）           │
│  [1/5] 获取最新消息               │
│    → wechat-decrypt-db skill            │
│    → 查询MSG1.db                     │
│  [2/5] 识别需求                      │
│    → llm_requirement_analyzer.py        │
│    → Anthropic API语义分析               │
│  [3/5] 创建kanban任务             │
│    → mcp__kanban-doc__create_task       │
│  [4/5] 分配agent                      │
│    → ProjectManager.assign_task_to_agent│
│  [5/5] 启动执行                        │
│    → mcp__kanban-doc__start_runtime     │
└──────────────┬────────────────────────┘
           ↓
┌──────────────────────┐
│         执行层（Agent团队）                │
│  Kimi: 文件/数据/文档处理               │
│  Codex: 代码/算法/测试                │
└────────────────────┘
```

### 核心组件

#### 1. AutoPipeline（`.claude/auto_pipeline.py`）

**职责**：协调整个自动化流程

**核心方法**：
- `run(mode)` - 运行Pipeline
- `_fetch_latest_messages()` - 获取最新消息
- `_identify_requirements()` - 识别需求
- `_create_kanban_tasks()` - 创建任务
- `_assign_agents()` - 分配agent
- `_start_executions()` - 启动执行

#### 2. 触发器

**方式1：定时触发**（推荐）
```python
# 使用CronCreate，每小时检查一次
CronCreate(
    cron="7 * * * *",  # 每小时第7分钟（避开:00和:30）
    prompt="运行自动化Pipeline：python .claude/auto_pipeline.py",
    recurring=True
)
```

**方式2：实时触发**
```python
# 使用watchdog监听MSG1.db文件变化
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class WeChatDBHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if 'MSG1.db' in event.src_path:
            auto_pipeline.run(mode="realtime")
```

**方式3：手动触发**
```python
# 用户说"同步需求"时触发
auto_pipeline.run(mode="manual")
```

#### 3. 需求识别（LLM）

**使用现有的 `llm_requirement_analyzer.py`**：

```python
from llm_requirement_analyzer import RequirementAnalyzer

analyzer = RequirementAnalyzer()
requirements = analyzer.analyze_messages(messages)

# 返回格式：
# [
#   {
#     'type': 'bug_fix',  # bug修复、新功能、性能优化等
#     'priority': 'high',  # critical、high、medium、low
#     'description': 'Qt 5.14.2兼容性问题',
#   'project': 'linux-qt-jr',  # 自动映射到项目
#     'tags': ['qt', 'compatibility', 'urgent']
#   }
# ]
```

#### 4. 项目映射规则

**根据关键词自动映射到项目**：

| 关键词 | 项目 |
|--------|---|
| Qt、界面、UI | linux-qt-jr |
| WordPress、网站、图片 | wordpress-decoration |
| MCE、爬虫、数据 | MCE |
| 播放器、歌词、音乐 | syc-player |
| 表情包、肖战 | xiaozhan-emoji-generator |

#### 5. Agent分配规则

**使用 `ProjectManager.assign_task_to_agent()`**：

```python
# 根据任务描述自动判断
agent = manager.assign_task_to_agent(
    "Qt 5.14.2兼容性问题，缺少某函数"
)
# → Codex（代码工程师）

agent = manager.assign_task_to_agent(
    "批量处理Word文档，提取关键信息"
)
# → Kimi（全栈执行官）
```

---

## 实现步骤

### 阶段1：核心功能（1周）

**任务清单**：
- [x] 创建AutoPipeline框架（已完成）
- [ ] 实现 `_fetch_latest_messages()`
  - 调用wechat-decrypt-db skill
  - 查询MSG1.db
  - 过滤目标群
- [ ] 实现 `_identify_requirements()`
  - 集成llm_requirement_analyzer.py
  - 调用Anthropic API
  - 提取需求信息
- [ ] 实现 `_create_kanban_tasks()`
  - 调用mcp__kanban-doc__create_task
  - 映射需求到项目
  - 设置优先级和标签
- [ ] 实现 `_assign_agents()`
  - 使用ProjectManager.assign_task_to_agent
  - 返回任务到agent的映射
- [ ] 实现 `_start_executions()`
  - 调用mcp__kanban-doc__start_runtime
  - 启动agent执行
  - 返回执行ID

### 阶段2：触发器（3天）

**任务清单**：
- [ ] 实现定时触发（CronCreate）
- [ ] 实现实时触发（watchdog）
- [ ] 实现手动触发（用户命令）

### 阶段3：监控与汇报（3天）

**任务清单**：
- [ ] 监控agent执行状态
- [ ] 生成执行报告
- [ ] 异常处理和重试
- [ ] 向用户汇报结果

### 阶段4：优化与测试（1周）

**任务清单**：
- [ ] 性能优化（减少API调用）
- [ ] 准确率测试（需求识别）
- [ ] 端到端测试
- [ ] 文档和示例

---

## 使用示例

### 场景1：手动触发

```python
# 用户说："同步需求"
from auto_pipeline import auto_pipeline

output = auto_pipeline.run(mode="manual")
print(output)

# 输出：
# 🤖 自动化Pipeline
# ================
# 📱 [1/5] 获取微信群最新消息... ✅ 获取到 15 条新消息
# 🔍 [2/5] 识别需求... ✅ 识别到 3 个需求
#   需求 1: Qt兼容性问题（高优先级）
#   需求 2: UI显示异常（中优先级）
#   需求 3: 后续合作讨论（低优先级）
# 📋 [3/5] 创建kanban-doc任务... ✅ 创建了 3 个任务
# 🎯 [4/5] 分配任务给agent... ✅ 分配了 3 个任务
#   - task-001 → Codex
#   - task-002 → Codex
#   - task-003 → Kimi
# 🚀 [5/5] 启动agent执行... ✅ 启动了 3 个执行
# ✅ Pipeline执行完成
```

### 场景2：定时触发

```python
# 设置每小时自动检查
CronCreate(
    cron="7 * * * *",
    prompt="python .claude/auto_pipeline.py",
    recurring=True
)

# 每小时第7分钟自动运行：
# - 获取最新消息
# - 识别需求
# - 创建任务
# - 分配agent
# - 启动执行
```

### 场景3：实时触发

```python
# 监听MSG1.db文件变化
from watchdog.observers import Observer

observer = Observer()
observer.schedule(WeChatDBHandler(), path="数据库目录", recursive=False)
observer.start()

# 当MSG1.db有新消息时：
# - 自动触发Pipeline
# - 实时识别需求
# - 立即创建任务
# - 快速响应客户
```

---

## 预期效果

### 用户体验

**之前**：
```
客户发消息 → 你看到 → 你告诉我 → 我分析 → 我建议 → 你确认 → 我创建任务
（需要5-10分钟，需要你不断提示）
```

**之后**：
```
客户发消息 → 自动识别 → 自动创建任务 → 自动分配agent → 自动执行
（1-2分钟，完全自动化）

你只需要：
- 每天早上看一眼执行报告
- 批准或拒绝某些任务
- 对接客户（汇报进度）
```

### 企业级特性

1. **实时响应**：客户发消息后1-2分钟内自动创建任务
2. **智能识别**：LLM自动识别需求类型、优先级、项目
3. **自动分配**：根据任务类型自动选择Kimi或Codex
4. **监控汇报**：自动生成执行报告，异常时通知
5. **可追溯**：所有操作记录到日志，可审计

---

## 下一步

### 立即行动

1. **测试Kimi的最新查询**（正在进行）
   - 验证wechat-decrypt-db skill是否正常
   - 验证MSG1.db查询是否返回5月14日消息

2. **实现AutoPipeline核心功能**
   - 先实现 `_fetch_latest_messages()`
   - 再实现 `_identify_requirements()`
   - 最后实现 `_create_kanban_tasks()`

3. **端到端测试**
   - 手动触发一次完整流程
   - 验证需求识别准确率
   - 验证任务创建是否正确

### 需要你的决策

1. **触发方式**：
   - 定时触发（每小时）？
   - 实时触发（监听数据库）？
   - 还是两者结合？

2. **需求识别阈值**：
   - 所有消息都识别？
   - 还是只识别明确的需求（问题、催促、新功能）？

3. **自动执行范围**：
   - 所有任务都自动执行？
   - 还是高优先级任务需要你批准？

---

**评估人**：Claude
**创建日期**：2026-05-15
**状态**：✅ 框架已创建，待实现核心功能
