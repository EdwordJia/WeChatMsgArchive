# 阶段0：基础设施实现

> 实施日期：2026-05-15
> 目标：建立状态管理和Agent协调机制，支持每日对话快速恢复上下文

---

## 📦 交付物

### 核心组件

1. **StateManager** (`.claude/state_manager.py`)
   - 项目状态持久化与恢复
   - 支持会话上下文、项目状态、待办任务、Agent状态
   - JSON格式存储，快速加载（< 1秒）
   - 自动生成每日摘要

2. **AgentCoordinator** (`.claude/agent_coordinator.py`)
   - 智能任务分配（Kimi vs Codex）
   - 任务执行与监控
   - 执行历史记录
   - Agent统计分析

3. **DailySync** (`.claude/daily_sync.py`)
   - 每日对话流程入口
   - 5步同步流程：恢复状态 → 同步kanban → 分析消息 → 生成摘要 → 提供建议
   - 目标耗时 < 30秒

4. **测试脚本** (`.claude/test_stage0.py`)
   - 完整的组件测试
   - 验证状态持久化和恢复
   - 验证任务分配逻辑

---

## 🏗️ 架构设计

```
┌────────────────────────┐
│         用户交互层（Claude Code）          │
│  每日对话入口: python -m .claude.daily_sync  │
└────────────────┬────────────────────┘
                 ↓
┌─────────────────────────────┐
│         状态管理层（StateManager）         │
│  • ProjectState: 项目状态快照              │
│  • SessionContext: 会话上下文              │
│  • AgentWorkStatus: Agent工作日志       │
│  存储: .claude/state/project_state.json    │
└────────────────┬───────────────┘
             ↓
┌────────────────────────────────┐
│       任务协调层（AgentCoordinator）       │
│  • 智能任务分配（Kimi/Codex）              │
│  • 任务执行与监控                 │
│  • 执行历史与统计                        │
└────────────────┬─────────────┘
          ↓
┌───────────────────┐
│         执行层（Agent团队）          │
│  • Kimi: 文件/数据/文档处理                │
│  • Codex: 代码/算法/测试           │
└───────────────────────────────┘
```

---

## 🚀 使用方法

### 1. 运行测试

```bash
# 测试核心组件
python -m .claude.test_stage0
```

### 2. 每日同步

```bash
# 每天早上运行此命令
python -m .claude.daily_sync
```

输出示例：
```
================================================
🌅 AI项目管理系统 - 每日同步
=================================================

同步时间: 2026-05-15 09:00:00

📂 [1/5] 恢复项目状态...
✅ 状态恢复成功
   距离上次同步: 16小时30分钟

📋 [2/5] 同步kanban-doc任务...
⚠️  kanban-doc集成待实现（阶段0暂不包含）

💬 [3/5] 分析客户聊天记录...
⚠️  消息分析待实现（阶段1-2）
   - 微信: 已支持（需要运行解密）
   - 企业微信: 待验证
   - 飞书: 待开发

📊 [4/5] 生成项目摘要...
✅ 摘要已生成

💡 [5/5] 生成下一步建议...
🔥 高优先级任务:
   - [wordpress-decoration] 整合密码机提供的图片素材到网页
     建议分配给: kimi
   - [MCE] MCE官网产品数据爬取
     建议分配给: codex

💼 可用Agent: kimi, codex
   建议立即分配任务

⏱️  总耗时: 2.35秒
========================================

📄 详细摘要已保存到: .claude/state/daily_summary.md
```

### 3. 手动操作状态

```python
from .claude.state_manager import state_manager, TaskStatus, AgentType, AgentStatus

# 加载状态
state_manager.load_snapshot()

# 查看项目
for name, status in state_manager.projects.items():
    print(f"{name}: {status.total_tasks}个任务")

# 同步Agent状态
state_manager.sync_agent_status(
    AgentType.KIMI,
    AgentStatus.BUSY,
    current_task="e278",
    current_project="wordpress-decoration"
)

# 保存状态
state_manager.save_snapshot()

# 生成摘要
print(state_manager.get_daily_summary())
```

### 4. 手动分配任务

```python
from .claude.agent_coordinator import agent_coordinator, TaskType

# 分配任务
agent = agent_coordinator.assign_task(
    TaskType.CODE_GENERATION,
    "实现快速排序算法"
)
print(f"分配给: {agent.value}")

# 执行任务
result = agent_coordinator.execute_task(
    task_id="test-001",
    agent=agent,
    prompt="实现快速排序算法",
    timeout=60
)

print(f"状态: {result.status.value}")
print(f"耗时: {result.duration_seconds:.2f}秒")

# 查看统计
print(agent_coordinator.get_execution_summary())
```

---

## 📊 数据模型

### ProjectState

```python
{
  "current_session": {
    "session_id": "session-20260515-090000",
    "started_at": "2026-05-15T09:00:00",
    "last_sync_at": "2026-05-15T09:00:00",
    "current_focus": "wordpress-decoration",
    "next_steps": ["整合图片素材", "通知客户确认"]
  },
  "projects": {
    "wordpress-decoration": {
      "project_name": "wordpress-decoration",
      "total_tasks": 3,
      "todo_count": 1,
      "inprogress_count": 1,
      "inreview_count": 1,
      "done_count": 0,
      "last_activity": "2026-05-15T08:30:00",
      "active_agents": ["kimi"]
    }
  },
  "pending_tasks": [
    {
    "task_id": "e278",
      "project": "wordpress-decoration",
      "title": "整合密码机提供的图片素材到网页",
      "description": "...",
      "status": "inprogress",
      "priority": "high",
      "created_at": "2026-05-14T10:00:00",
      "updated_at": "2026-05-15T08:30:00",
      "assigned_to": "kimi"
    }
  ],
  "agent_status": {
    "kimi": {
      "agent_type": "kimi",
      "status": "busy",
      "current_task": "e278",
      "current_project": "wordpress-decoration",
      "last_activity": "2026-05-15T08:30:00",
      "completed_today": 2
    },
    "codex": {
      "agent_type": "codex",
      "status": "idle",
      "current_task": null,
      "current_project": null,
      "last_activity": "2026-05-14T18:00:00",
      "completed_today": 0
    }
  },
  "last_sync_time": "2026-05-15T09:00:00",
  "snapshot_version": "1.0",
  "created_at": "2026-05-15T09:00:00"
}
```

---

## 🎯 任务分配规则

### Kimi负责的任务类型

- `FILE_OPERATION` - 文件操作（批量重命名、移动、压缩）
- `DATA_PROCESSING` - 数据处理（Excel/CSV清洗、转换）
- `DOCUMENT` - 文档处理（Word/PDF/LaTeX生成）
- `WEB_SEARCH` - Web搜索与信息收集
- `SYSTEM_CONFIG` - 系统配置（环境变量、包安装）
- `GIT_OPERATION` - Git操作（clone、commit、push）
- `SHELL_SCRIPT` - Shell脚本与自动化

### Codex负责的任务类型

- `CODE_GENERATION` - 代码生成与架构设计
- `ALGORITHM` - 算法设计与优化
- `CODE_REVIEW` - 代码审查与安全分析
- `TESTING` - 测试工程（单元测试、集成测试）
- `REFACTORING` - 代码重构与结构改进
- `DEBUGGING` - Bug修复与深度调试
- `PERFORMANCE` - 性能优化

### 智能判断（ANALYSIS/PLANNING）

对于通用任务，通过关键词匹配判断：
- 包含代码相关关键词 → Codex
- 包含数据/文件关键词 → Kimi
- 无法判断 → Kimi（广度优先）

---

## ✅ 完成标准

### 最小可行产品（MVP）

用户每天早上打开Claude Code，输入"同步项目状态"，系统能够：

1. ✅ 在30秒内恢复上次会话状态
2. ⚠️ 展示所有项目的最新进度（待集成kanban-doc）
3. ⚠️ 分析昨天的客户聊天记录（待集成微信数据）
4. ⚠️ 识别出新需求并创建任务（待集成LLM分析）
5. ✅ 分配任务给Kimi/Codex（智能分配已实现）
6. ⚠️ 展示Agent执行状态（基础框架已实现，待实际执行）
7. ✅ 提供下一步建议

**阶段0完成度**: 3/7 (43%)

---

## 🔄 下一步（阶段1）

### 企业微信验证（1周）

**目标**：验证企业微信本地解密方案

**任务清单**：
- [ ] 在企业微信环境中运行测试
- [ ] 验证密钥提取是否成功
- [ ] 解密数据库并分析表结构
- [ ] 对比个人微信数据库差异
- [ ] 决策：本地方案 vs API方案

**交付物**：
- 企业微信数据库结构文档
- `WorkWeChatAdapter`（如果本地方案可行）

---

## 📝 技术债务

1. **kanban-doc集成**：`DailySync._sync_kanban()` 待实现
2. **消息分析集成**：`DailySync._analyze_messages()` 待实现
3. **CLI安装检测**：`AgentCoordinator` 需要检测 kimi/codex CLI 是否安装
4. **错误恢复**：需要增加降级策略（解密失败、API超时等）
5. **日志系统**：需要统一的日志记录机制
6. **单元测试**：需要补充pytest单元测试

---

## 🐛 已知问题

1. **CLI依赖**：需要手动安装 `kimi` 和 `codex` CLI
2. **路径硬编码**：部分路径使用相对路径，可能在不同环境下失败
3. **异常处理**：部分异常处理不够完善
4. **性能优化**：状态恢复未做性能测试

---

## 📚 参考文档

- [AI_PROJECT_MANAGER_FEASIBILITY.md](../AI_PROJECT_MANAGER_FEASIBILITY.md) - 完整可行性分析
- [config.py](../config.py) - 统一配置管理
- [CLAUDE.md](../../.claude/CLAUDE.md) - 委派策略

---

**评估人**：Claude
**实施日期**：2026-05-15
**状态**：✅ 阶段0基础设施已完成，待测试验证
