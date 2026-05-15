# -*- coding: utf-8 -*-
"""
AI项目管理器 - 单会话管理所有agent

用户场景：
- 用户只开一个Claude Code会话
- Claude作为项目经理，自动处理一切：
  1. 监听客户消息（微信/企业微信/飞书）
  2. 识别需求 → 创建kanban任务
  3. 分配给Kimi/Codex → 在当前会话中调用
  4. 监控执行 → 汇报结果
  5. 用户只需要做决策

核心设计：
- 不再搞AgentCoordinator（重复造轮子）
- 直接用kanban-doc MCP的runtime功能
- 在当前会话中通过Agent tool调用Kimi/Codex
- StateManager只管会话快照，不管agent调度
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 添加.claude目录到路径
claude_dir = Path(__file__).parent
sys.path.insert(0, str(claude_dir))

from state_manager import ProjectState, SessionContext


class ProjectManager:
    """
    AI项目管理器

    在当前Claude Code会话中管理所有项目和agent。
    用户只需要跟Claude对话，Claude自动处理一切。
    """

    def __init__(self):
        self.state = ProjectState()
        self.current_session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def daily_sync(self) -> str:
        """
        每日同步流程

        步骤：
        1. 恢复上次会话状态
        2. 从kanban-doc拉取最新任务
        3. 分析客户聊天记录（微信/企业微信/飞书）
        4. 识别新需求 → 创建任务
        5. 分配任务给Kimi/Codex
   6. 生成每日摘要
        """
        lines = []
        lines.append("=" * 60)
        lines.append("🌅 每日项目同步")
        lines.append("=" * 60)
        lines.append(f"\n同步时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 步骤1: 恢复状态
        lines.append("📂 [1/6] 恢复会话状态...")
     if self.state.load_snapshot():
         lines.append("✅ 状态恢复成功")
            if self.state.last_sync_time:
                elapsed = datetime.now() - self.state.last_sync_time
                hours = int(elapsed.total_seconds() // 3600)
              minutes = int((elapsed.total_seconds() % 3600) // 60)
                lines.append(f"   距离上次同步: {hours}小时{minutes}分钟")
        else:
       lines.append("⚠️  首次运行，初始化新会话")
         self._initialize_session()

        # 步骤2: 同步kanban-doc
        lines.append("\n📋 [2/6] 同步kanban-doc任务...")
        lines.append("   → 使用 mcp__kanban-doc__list_projects")
        lines.append("   → 使用 mcp__kanban-doc__list_available")
        lines.append("   ⚠️  需要在Claude会话中调用MCP工具")

      # 步骤3: 分析客户消息
        lines.append("\n💬 [3/6] 分析客户聊天记录...")
        lines.append("   → 微信: 使用wechat-data MCP")
        lines.append("   → 企业微信: 待验证（阶段1）")
        lines.append("   → 飞书: 待开发（阶段2）")
        lines.append("   ⚠️  需要在Claude会话中调用MCP工具")

        # 步骤4: 识别需求
        lines.append("\n🔍 [4/6] 识别新需求...")
        lines.append("   → 使用LLM语义分析（llm_requirement_analyzer.py）")
        lines.append("   → 自动创建kanban任务")
        lines.append("   ⚠️  待集成（阶段3）")

   # 步骤5: 分配任务
      lines.append("\n🎯 [5/6] 分配任务给agent...")
        lines.append("   → 文件/数据/文档类 → 调用Kimi（Agent tool）")
    lines.append("   → 代码/算法/测试类 → 调用Codex（Agent tool）")
        lines.append("   → 使用 mcp__kanban-doc__start_runtime 启动执行")
        lines.append("   ⚠️  需要在Claude会话中调用Agent tool")

        # 步骤6: 生成摘要
        lines.append("\n📊 [6/6] 生成每日摘要...")
        summary = self.state.get_daily_summary()
        summary_file = Path(".claude/state/daily_summary.md")
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        lines.append(f"✅ 摘要已保存到: {summary_file}")

        # 保存状态
        self.state.last_sync_time = datetime.now()
        self.state.save_snapshot()

        lines.append("\n" + "=" * 60)
        lines.append("✅ 同步完成")
        lines.append("=" * 60)

        return '\n'.join(lines)

    def _initialize_session(self):
        """初始化新会话"""
        self.state.current_session = SessionContext(
          session_id=self.current_session_id,
            started_at=datetime.now(),
            last_sync_at=datetime.now(),
            current_focus=None,
            next_steps=[]
        )

    def assign_task_to_agent(self, task_description: str) -> str:
        """
        智能分配任务给agent

        根据任务描述判断应该调用Kimi还是Codex。
      返回建议的agent类型和调用方式。

        Args:
            task_description: 任务描述

        Returns:
            建议的agent和调用方式
        """
        desc_lower = task_description.lower()

        # Kimi关键词
        kimi_keywords = [
            '文件', '数据', '文档', '表格', 'excel', 'csv', 'pdf', 'word',
            'file', 'data', 'document', '批量', '清洗', '转换', '搜索',
            'web', '配置', 'git', 'shell', '脚本'
        ]

        # Codex关键词
        codex_keywords = [
         '代码', '算法', '函数', '类', '测试', 'bug', '性能', '优化',
            'code', 'algorithm', 'function', 'class', 'test', 'debug',
            '重构', '审查', 'review', 'refactor'
        ]

        kimi_score = sum(1 for kw in kimi_keywords if kw in desc_lower)
        codex_score = sum(1 for kw in codex_keywords if kw in desc_lower)
        if codex_score > kimi_score:
            return """
建议分配给: Codex（代码工程师）

调用方式（在Claude会话中）：
```python
Agent(
    subagent_type="codex-secretary",
    prompt="{task_description}",
    description="代码任务"
)
```

或使用kanban-doc runtime：
```python
mcp__kanban-doc__start_runtime(
    project="项目名",
    task_id="任务ID",
    cli="codex",
    task="{task_description}"
)
```
""".format(task_description=task_description)
        else:
            return """
建议分配给: Kimi（全栈执行官）

调用方式（在Claude会话中）：
```python
Agent(
    subagent_type="kimi-secretary",
    prompt="{task_description}",
    description="执行任务"
)
```

或使用kanban-doc runtime：
```python
mcp__kanban-doc__start_runtime(
    project="项目名",
    task_id="任务ID",
    cli="kimi",
    task="{task_description}"
)
```
"".format(task_description=task_description)

    def get_next_steps(self) -> List[str]:
      """
        生成下一步建议

        基于当前项目状态，建议用户接下来应该做什么。
      """
      suggestions = []

        # 检查是否有高优先级任务
        if self.state.pending_tasks:
            high_priority = [t for t in self.state.pending_tasks if t.priority in ['critical', 'high']]
            if high_priority:
                suggestions.append(f"🔥 有{len(high_priority)}个高优先级任务待处理")
                for task in high_priority[:3]:
                    suggestions.append(f"   - [{task.project}] {task.title}")

        # 检查是否需要同步数据
        if self.state.last_sync_time:
            elapsed = datetime.now() - self.state.last_sync_time
            if elapsed.total_seconds() > 86400:  # 超过24小时
           suggestions.append("⏰ 距离上次同步超过24小时，建议运行每日同步")

        if not suggestions:
       suggestions.append("✅ 所有任务进展顺利，暂无紧急事项")

        return suggestions


# 全局实例
project_manager = ProjectManager()


if __name__ == "__main__":
    # 测试代码
    manager = ProjectManager()

    print("=" * 60)
    print("测试：每日同步")
    print("=" * 60)
    output = manager.daily_sync()
    print(output)

    print("\n" + "=" * 60)
    print("测试：任务分配")
    print("=" * 60)

    test_tasks = [
        "批量处理100个Word文档，提取关键信息",
        "优化MCE爬虫的性能，降低内存占用",
        "分析Excel数据，生成可视化报表",
        "实现快速排序算法，要求时间复杂度O(nlogn)",
    ]

    for task in test_tasks:
        print(f"\n任务: {task}")
        print(manager.assign_task_to_agent(task))

    print("\n" + "=" * 60)
    print("测试：下一步建议")
    print("=" * 60)
    suggestions = manager.get_next_steps()
    for suggestion in suggestions:
        print(suggestion)
