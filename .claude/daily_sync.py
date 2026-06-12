"""
每日对话流程入口

用户每天打开Claude Code后，运行此脚本快速恢复项目状态。

流程：
1. 状态恢复（< 30秒）
2. 同步kanban-doc数据
3. 分析新消息（微信/企业微信/飞书）
4. 生成每日摘要
5. 提供下一步建议
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 添加.claude目录到路径
claude_dir = Path(__file__).parent
sys.path.insert(0, str(claude_dir))

from state_manager import ProjectState, SessionContext, AgentType, AgentStatus
from agent_coordinator import AgentCoordinator, TaskType
from config import config


class DailySync:
    """每日同步流程"""

    def __init__(self):
        self.state = ProjectState()
        self.coordinator = AgentCoordinator()
        self.start_time = datetime.now()

    def run(self) -> str:
        """执行每日同步流程"""
        lines = []
        lines.append("=" * 60)
        lines.append("🌅 AI项目管理系统 - 每日同步")
        lines.append("=" * 60)
        lines.append(f"\n同步时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 步骤1: 恢复状态
        lines.append("📂 [1/5] 恢复项目状态...")
        restore_success = self._restore_state()
        if restore_success:
        lines.append("✅ 状态恢复成功")
        if self.state.last_sync_time:
            elapsed = self.start_time - self.state.last_sync_time
             lines.append(f"   距离上次同步: {self._format_duration(elapsed)}")
        else:
            lines.append("⚠️  未找到历史状态，这是首次运行")
          self._initialize_state()

        # 步骤2: 同步kanban-doc
        lines.append("\n📋 [2/5] 同步kanban-doc任务...")
        kanban_summary = self._sync_kanban()
        lines.append(kanban_summary)

      # 步骤3: 分析新消息
        lines.append("\n💬 [3/5] 分析客户聊天记录...")
        message_summary = self._analyze_messages()
        lines.append(message_summary)

        # 步骤4: 生成每日摘要
        lines.append("\n📊 [4/5] 生成项目摘要...")
        daily_summary = self.state.get_daily_summary()
        lines.append("✅ 摘要已生成")

        # 步骤5: 提供建议
        lines.append("\n💡 [5/5] 生成下一步建议...")
        suggestions = self._generate_suggestions()
        lines.append(suggestions)

        # 保存状态
      self.state.last_sync_time = datetime.now()
        self.state.save_snapshot()

      # 计算总耗时
        duration = (datetime.now() - self.start_time).total_seconds()
        lines.append(f"\n⏱️  总耗时: {duration:.2f}秒")
        lines.append("=" * 60)

        output = '\n'.join(lines)

        # 同时输出详细摘要到文件
        summary_file = Path(".claude/state/daily_summary.md")
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(output)
            f.write("\n\n" + "=" * 60 + "\n")
            f.write(daily_summary)

        return output

    def _restore_state(self) -> bool:
        """恢复状态"""
        return self.state.load_snapshot()

    def _initialize_state(self) -> None:
        """初始化状态（首次运行）"""
        self.state.current_session = SessionContext(
            session_id=f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            started_at=datetime.now(),
            last_sync_at=datetime.now(),
          current_focus=None,
            next_steps=[]
        )

      # 初始化Agent状态
        for agent in [AgentType.KIMI, AgentType.CODEX]:
            self.state.sync_agent_status(agent, AgentStatus.IDLE)

    def _sync_kanban(self) -> str:
        """同步kanban-doc数据"""
      try:
            # TODO: 集成kanban-doc MCP工具
            # 目前返回模拟数据
            return "⚠️  kanban-doc集成待实现（阶段0暂不包含）"
        except Exception as e:
          return f"❌ 同步失败: {e}"

    def _analyze_messages(self) -> str:
        """分析客户聊天记录"""
      try:
            # TODO: 集成微信/企业微信/飞书数据分析
            # 目前返回模拟数据
            lines = []
            lines.append("⚠️  消息分析待实现（阶段1-2）")
            lines.append("   - 微信: 已支持（需要运行解密）")
        lines.append("   - 企业微信: 待验证")
            lines.append("   - 飞书: 待开发")
          return '\n'.join(lines)
        except Exception as e:
            return f"❌ 分析失败: {e}"

    def _generate_suggestions(self) -> str:
        """生成下一步建议"""
        lines = []

        # 基于项目状态生成建议
        if not self.state.projects:
            lines.append("💡 建议:")
            lines.append("   1. 运行 kanban-doc 同步获取项目数据")
          lines.append("   2. 运行微信解密获取客户聊天记录")
        return '\n'.join(lines)

        # 检查待办任务
      high_priority_tasks = [
         task for task in self.state.pending_tasks
            if task.priority in ['critical', 'high']
        ]

      if high_priority_tasks:
            lines.append("🔥 高优先级任务:")
         for task in high_priority_tasks[:3]:
         lines.append(f"   - [{task.project}] {task.title}")
           if not task.assigned_to:
               # 建议分配Agent
                    task_type = self._infer_task_type(task.description)
                  suggested_agent = self.coordinator.assign_task(task_type, task.description)
             lines.append(f"     建议分配给: {suggested_agent.value}")

        # 检查Agent状态
        idle_agents = [
            agent for agent, status in self.state.agent_status.items()
            if status.status == AgentStatus.IDLE
        ]

      if idle_agents and high_priority_tasks:
            lines.append(f"\n💼 可用Agent: {', '.join([a.value for a in idle_agents])}")
            lines.append("   建议立即分配任务")

        if not lines:
            lines.append("✅ 所有任务进展顺利，暂无紧急事项")

        return '\n'.join(lines)

    def _infer_task_type(self, description: str) -> TaskType:
        """从任务描述推断任务类型"""
     desc_lower = description.lower()

        # 简单的关键词匹配
        if any(kw in desc_lower for kw in ['代码', '算法', '函数', '类', 'bug', 'code', 'algorithm']):
            return TaskType.CODE_GENERATION
        elif any(kw in desc_lower for kw in ['测试', 'test', '单元测试']):
          return TaskType.TESTING
        elif any(kw in desc_lower for kw in ['审查', 'review', '代码审查']):
            return TaskType.CODE_REVIEW
        elif any(kw in desc_lower for kw in ['文件', '数据', '文档', 'file', 'data', 'document']):
            return TaskType.FILE_OPERATION
        elif any(kw in desc_lower for kw in ['excel', 'csv', '表格', '清洗']):
            return TaskType.DATA_PROCESSING
        else:
            return TaskType.ANALYSIS

    def _format_duration(self, delta: timedelta) -> str:
        """格式化时间间隔"""
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 24:
            days = hours // 24
            return f"{days}天{hours % 24}小时"
     elif hours > 0:
            return f"{hours}小时{minutes}分钟"
        else:
            return f"{minutes}分钟"


def main():
    """主函数"""
    sync = DailySync()
    output = sync.run()
    print(output)

    # 提示用户查看详细摘要
    print("\n📄 详细摘要已保存到: .claude/state/daily_summary.md")


if __name__ == "__main__":
    main()
