# 阶段0：单会话AI项目管理系统

> **核心理念**：用户只开一个Claude Code会话，Claude作为项目经理自动处理一切

---

## 🎯 用户场景

```
你（老板）────→ Claude（项目经理，当前会话）
                ↓
                自动处理：
            1. 监听客户消息（微信/企业微信/飞书）
                2. 识别需求 → 创建kanban任务
              3. 分配给Kimi/Codex → 在当前会话中调用
                4. 监控执行 → 汇报结果

             你只需要：
                - 每天说"同步状态"
      - 做决策（批准/拒绝方案）
                - 对接客户
```

---

## 🏗️ 架构设计

### 为什么删除了AgentCoordinator？

**原因**：kanban-doc已经有完整的agent调度功能，不需要重复造轮子。

kanban-doc提供的功能：
- `call_agent` - 调用单个agent
- `call_agents_parallel` - 并行调用多个agent
- `start_runtime` - 启动runtime执行
- `get_runtime` - 监控执行状态
- `list_runtime_processes` - 查看所有执行进程

### 新架构

```
┌──────────────────────────────────────┐
│      用户 - 只开一个会话                      │
│   "同步状态" / "看看进度" / "批准这个方案"          │
└─────────────┬────────────────────────────┘
                ↓
┌──────────────────────────────┐
│    Claude（项目经理 - 当前会话中）              │
│  1. 每日同步：拉取kanban任务 + 分析客户消息       │
│  2. 需求识别：从聊天记录中提取需求 → 创建任务     │
│  3. 任务分配：判断任务类型 → 调用Kimi/Codex      │
│  4. 执行监控：在当前会话中跟踪agent状态           │
│  5. 结果汇报：整理agent输出 → 向用户汇报         │
└──────┬──────────┬───────────┬────────────┘
       ↓              ↓            ↓
┌──────────┐  ┌────────────┐  ┌──────────────┐
│StateManager│ │kanban-doc  │  │多平台数据源   │
│(会话快照)  │ │(任务+agent)│  │(微信/企微/飞书)│
└──────────┘  └────────────┘  └────────────┘
                  ↓
          ┌─────┴─────┐
          ↓           ↓
         ┌────────┐  ┌────────┐
      │  Kimi  │  │ Codex  │
         │(通过MCP)│  │(通过MCP)│
         └────────┘  └────────┘
```

---

## 📦 核心组件

### 1. ProjectManager（`.claude/project_manager.py`）

**职责**：在当前会话中管理所有项目和agent

**核心方法**：

```python
# 每日同步（6步流程）
manager.daily_sync()

# 智能分配任务
manager.assign_task_to_agent("批量处理Word文档")
# → 返回建议的agent和调用方式

# 获取下一步建议
manager.get_next_steps()
# → 返回待办事项列表
```

### 2. StateManager（`.claude/state_manager.py`）

**职责**：会话状态持久化，支持快速恢复上下文

**数据模型**：
- `SessionContext` - 会话上下文
- `ProjectStatus` - 项目状态快照
- `Task` - 任务模型
- `AgentWorkStatus` - Agent工作日志

**存储位置**：`.claude/state/project_state.json`

---

## 🚀 使用方法

### 方式1：在Claude会话中直接对话

```
你: 同步一下项目状态

Claude:
📂 恢复会话状态... ✅
📋 同步kanban-doc任务...
   发现3个高优先级任务：
   - [wordpress-decoration] 整合图片素材
   - [MCE] 爬虫性能优化
   - [syc-player] 修复播放问题

💡 建议：
   1. 整合图片素材 → 分配给Kimi
   2. 爬虫性能优化 → 分配给Codex

你要我现在就分配任务吗？
```

### 方式2：运行Python脚本

```bash
./venv/Scripts/python .claude/project_manager.py
```

---

## 🎯 在当前会话中调用Kimi/Codex

### 方式1：用Agent tool（推荐）

```python
# Claude在当前会话中调用
Agent(
    subagent_type="kimi-secretary",
    prompt="批量处理100个Word文档",
    description="文档处理任务"
)

Agent(
    subagent_type="codex-secretary",
    prompt="优化爬虫性能，降低内存占用",
    description="性能优化任务"
)
```

### 方式2：用kanban-doc MCP

```python
# 通过kanban-doc的runtime
mcp__kanban-doc__start_runtime(
    project="wordpress-decoration",
    task_id="e278",
    cli="kimi",
    task="整合图片素材到网页"
)

# 监控执行状态
mcp__kanban-doc__get_runtime(
    project="wordpress-decoration",
    process_id="runtime-001"
)
```

### 方式3：用Skill tool

```python
# 直接调用技能
Skill(skill="kimi", args="批量处理文档")
Skill(skill="codex", args="优化爬虫性能")
```

---

## 📊 任务分配规则

ProjectManager会根据任务描述自动判断应该调用哪个agent：

| 关键词 | Agent | 原因 |
|--------|-------|------|
| 文件、数据、文档、Excel、PDF | Kimi | 广度优先，擅长文件处理 |
| 代码、算法、测试、性能、bug | Codex | 深度优先，擅长代码工程 |
| 批量、清洗、转换、搜索 | Kimi | 数据处理和自动化 |
| 重构、审查、优化、调试 | Codex | 代码质量和性能 |

**示例**：

```python
manager.assign_task_to_agent("批量处理100个Word文档")
# → 建议分配给: Kimi

manager.assign_task_to_agent("优化爬虫性能，降低内存占用")
# → 建议分配给: Codex
```

---

## 🔄 每日工作流

### 早上（9:00）

```
你: 同步状态

Claude:
📂 恢复会话状态... ✅ 距离上次同步16小时
📋 同步kanban-doc... 发现2个新任务
💬 分析客户消息... 发现3条新需求
🔍 识别需求... 自动创建任务到kanban
🎯 分配任务...
   - [wordpress-decoration] 整合图片 → Kimi
   - [MCE] 性能优化 → Codex
📊 生成摘要... 已保存到 .claude/state/daily_summary.md

💡 下一步建议：
   1. 批准Kimi执行"整合图片"任务
   2. 批准Codex执行"性能优化"任务
```

### 中午（12:00）

```
你: 看看进度

Claude:
📊 当前状态：
   - Kimi: 正在执行"整合图片"（进度60%）
   - Codex: 已完成"性能优化"，等待审查

🔍 Codex的优化方案：
   - 使用连接池减少数据库连接开销
   - 异步爬取提升并发性能
   - 内存占用降低40%

你要我让Kimi继续，还是先审查Codex的方案？
```

### 晚上（18:00）

```
你: 今天完成了什么

Claude:
✅ 今日完成：
   1. [wordpress-decoration] 整合图片素材 - Kimi完成
   2. [MCE] 爬虫性能优化 - Codex完成
   3. [syc-player] 修复播放问题 - Codex完成

📊 统计：
   - Kimi: 完成1个任务，耗时2.5小时
   - Codex: 完成2个任务，耗时3.8小时

💬 新消息：
   - 密码机（wordpress客户）: 确认图片效果满意
   - 烨林（MCE客户）: 询问爬虫何时交付

💡 明日计划：
   1. 通知烨林爬虫已优化完成
   2. 部署wordpress网站给密码机验收
```

---

## ✅ 完成标准

### 阶段0（当前）

- [x] StateManager - 会话状态持久化
- [x] ProjectManager - 单会话管理框架
- [x] 任务分配规则 - 智能判断Kimi/Codex
- [ ] kanban-doc集成 - 拉取任务和启动runtime
- [ ] 多平台数据源 - 微信/企业微信/飞书

**完成度**：3/5（60%）

### 阶段1（企业微信验证，1周）

- [ ] 验证企业微信本地解密
- [ ] 实现WorkWeChatAdapter
- [ ] 集成到ProjectManager

### 阶段2（飞书集成，2周）

- [ ] 申请飞书企业自建应用
- [ ] 实现FeishuAdapter
- [ ] 集成到ProjectManager

### 阶段3（智能需求识别，1周）

- [ ] 集成LLM语义分析
- [ ] 自动创建kanban任务
- [ ] 测试准确率

---

## 🎬 快速开始

### 1. 测试ProjectManager

```bash
cd .claude
../venv/Scripts/python project_manager.py
```

### 2. 在Claude会话中使用

```
你: 帮我同步项目状态

Claude会自动：
1. 调用 project_manager.daily_sync()
2. 使用kanban-doc MCP拉取任务
3. 使用wechat-data MCP分析消息
4. 生成摘要并提供建议
```

### 3. 分配任务给agent

```
你: 有个任务需要批量处理Word文档

Claude会：
1. 调用 project_manager.assign_task_to_agent()
2. 判断应该用Kimi
3. 在当前会话中调用Agent tool
4. 监控执行并汇报结果
```
---

## 📝 技术债务

1. **kanban-doc集成**：`ProjectManager.daily_sync()` 需要调用MCP工具
2. **消息分析集成**：需要调用wechat-data/wxwork/feishu MCP
3. **LLM需求识别**：需要集成`llm_requirement_analyzer.py`
4. **自动化触发**：可以用CronCreate定时触发同步
5. **错误恢复**：需要增加降级策略

---

## 🐛 已知问题

1. **Python语法问题**：`.claude/state_manager.py` 有缩进和中文标点问题，需要修复
2. **MCP工具调用**：需要在Claude会话中手动调用，暂未自动化
3. **Agent CLI依赖**：需要确保kimi和codex CLI已安装

---

## 🔄 下一步

1. **修复语法**：清理`.claude/state_manager.py`的缩进问题
2. **集成kanban-doc**：在`ProjectManager.daily_sync()`中调用MCP工具
3. **测试单会话管理**：验证在当前会话中调用Kimi/Codex
4. **进入阶段1**：企业微信本地解密验证

---

**设计理念**：
- ❌ 不要重复造轮子（删除AgentCoordinator）
- ✅ 直接用kanban-doc的runtime功能
- ✅ 在当前会话中管理所有agent
- ✅ 用户只需要对话，不需要切换会话

**评估人**：Claude
**实施日期**：2026-05-15
**状态**：✅ 架构重构完成，待集成测试
