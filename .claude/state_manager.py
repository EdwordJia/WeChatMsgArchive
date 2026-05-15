"""
项目状态管理器

负责持久化和恢复项目状态，支持每日对话快速恢复上下文。

核心功能：
- 项目状态快照（当前会话、项目进度、待办任务、Agent状态）
- 状态持久化到 JSON 文件
- 快速恢复机制（< 30秒）
- 每日摘要生成
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class TaskStatus(Enum):
    """任务状态"""
    TODO = "todo"
    IN_PROGRESS = "inprogress"
    IN_REVIEW = "inreview"
    DONE = "done"
    CANCELLED = "cancelled"


class AgentType(Enum):
    """Agent类型"""
    KIMI = "kimi"
    CODEX = "codex"
    CLAUDE = "claude"


class AgentStatus(Enum):
    """Agent工作状态"""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"


@dataclass
class Task:
    """任务模型"""
    task_id: str
    project: str
    title: str
    description: str
    status: TaskStatus
    priority: str
    created_at: datetime
    updated_at: datetime
    assigned_to: Optional[AgentType] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        if self.assigned_to:
            data['assigned_to'] = self.assigned_to.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        data['status'] = TaskStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if data.get('assigned_to'):
            data['assigned_to'] = AgentType(data['assigned_to'])
        return cls(**data)


@dataclass
class ProjectStatus:
    """项目状态"""
    project_name: str
    total_tasks: int
    todo_count: int
    inprogress_count: int
    inreview_count: int
    done_count: int
    last_activity: datetime
    active_agents: List[AgentType]

    def to_dict(self) -> dict:
        data = asdict(self)
        data['last_activity'] = self.last_activity.isoformat()
        data['active_agents'] = [agent.value for agent in self.active_agents]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'ProjectStatus':
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        data['active_agents'] = [AgentType(agent) for agent in data['active_agents']]
        return cls(**data)


@dataclass
class AgentWorkStatus:
    """Agent工作状态"""
    agent_type: AgentType
    status: AgentStatus
    current_task: Optional[str]  # task_id
    current_project: Optional[str]
    last_activity: datetime
    completed_today: int

    def to_dict(self) -> dict:
        data = asdict(self)
        data['agent_type'] = self.agent_type.value
        data['status'] = self.status.value
        data['last_activity'] = self.last_activity.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'AgentWorkStatus':
        data['agent_type'] = AgentType(data['agent_type'])
        data['status'] = AgentStatus(data['status'])
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        return cls(**data)


@dataclass
class SessionContext:
    """会话上下文"""
    session_id: str
    started_at: datetime
    last_sync_at: datetime
    current_focus: Optional[str]  # 当前关注的项目或任务
    next_steps: List[str]  # 下一步计划

    def to_dict(self) -> dict:
        data = asdict(self)
        data['started_at'] = self.started_at.isoformat()
        data['last_sync_at'] = self.last_sync_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'SessionContext':
        data['started_at'] = datetime.fromisoformat(data['started_at'])
        data['last_sync_at'] = datetime.fromisoformat(data['last_sync_at'])
        return cls(**data)


class ProjectState:
    """项目状态管理"""

    def __init__(self, state_dir: Path = None):
        self.state_dir = state_dir or Path(".claude/state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "project_state.json"

        # 状态数据
        self.current_session: Optional[SessionContext] = None
        self.projects: Dict[str, ProjectStatus] = {}
        self.pending_tasks: List[Task] = []
        self.agent_status: Dict[AgentType, AgentWorkStatus] = {}
        self.last_sync_time: Optional[datetime] = None

    def save_snapshot(self) -> None:
        """保存状态快照到文件"""
        snapshot = {
            'current_session': self.current_session.to_dict() if self.current_session else None,
            'projects': {name: status.to_dict() for name, status in self.projects.items()},
            'pending_tasks': [task.to_dict() for task in self.pending_tasks],
            'agent_status': {agent.value: status.to_dict() for agent, status in self.agent_status.items()},
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'snapshot_version': '1.0',
            'created_at': datetime.now().isoformat()
        }

        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

    def load_snapshot(self) -> bool:
        """从文件恢复状态"""
        if not self.state_file.exists():
            return False

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)

            # 恢复会话上下文
            if snapshot.get('current_session'):
                self.current_session = SessionContext.from_dict(snapshot['current_session'])

            # 恢复项目状态
            self.projects = {
                name: ProjectStatus.from_dict(data)
                for name, data in snapshot.get('projects', {}).items()
            }

            # 恢复待办任务
            self.pending_tasks = [
                Task.from_dict(data)
                for data in snapshot.get('pending_tasks', [])
            ]

            # 恢复Agent状态
            self.agent_status = {
                AgentType(agent): AgentWorkStatus.from_dict(data)
                for agent, data in snapshot.get('agent_status', {}).items()
            }

            # 恢复同步时间
            if snapshot.get('last_sync_time'):
                self.last_sync_time = datetime.fromisoformat(snapshot['last_sync_time'])

            return True
        except Exception as e:
            print(f"恢复状态失败: {e}")
            return False

    def get_daily_summary(self) -> str:
        """生成每日摘要（供Claude快速读取）"""
        lines = []
        lines.append("# 项目状态每日摘要")
        lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if self.last_sync_time:
            lines.append(f"上次同步: {self.last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 会话上下文
        if self.current_session:
            lines.append(f"\n## 当前会话")
            lines.append(f"- 会话ID: {self.current_session.session_id}")
            lines.append(f"- 开始时间: {self.current_session.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
            if self.current_session.current_focus:
                lines.append(f"- 当前关注: {self.current_session.current_focus}")
            if self.current_session.next_steps:
                lines.append(f"- 下一步计划:")
                for step in self.current_session.next_steps:
                    lines.append(f"  - {step}")

        # 项目概览
        lines.append(f"\n## 项目概览 ({len(self.projects)}个项目)")
        for name, status in self.projects.items():
            lines.append(f"\n### {name}")
            lines.append(f"- 总任务数: {status.total_tasks}")
            lines.append(f"- 待办: {status.todo_count} | 进行中: {status.inprogress_count} | 审查中: {status.inreview_count} | 已完成: {status.done_count}")
            lines.append(f"- 最后活动: {status.last_activity.strftime('%Y-%m-%d %H:%M:%S')}")
            if status.active_agents:
                agents = ', '.join([agent.value for agent in status.active_agents])
                lines.append(f"- 活跃Agent: {agents}")

        # 待办任务
        if self.pending_tasks:
            lines.append(f"\n## 待办任务 ({len(self.pending_tasks)}个)")
            for task in self.pending_tasks[:10]:  # 只显示前10个
                lines.append(f"\n### [{task.project}] {task.title}")
                lines.append(f"- 任务ID: {task.task_id}")
                lines.append(f"- 状态: {task.status.value} | 优先级: {task.priority}")
                if task.assigned_to:
                    lines.append(f"- 分配给: {task.assigned_to.value}")
                lines.append(f"- 描述: {task.description[:100]}...")

        # Agent状态
        lines.append(f"\n## Agent状态")
        for agent_type, status in self.agent_status.items():
            lines.append(f"\n### {agent_type.value}")
            lines.append(f"- 状态: {status.status.value}")
            if status.current_task:
                lines.append(f"- 当前任务: {status.current_task} ({status.current_project})")
            lines.append(f"- 今日完成: {status.completed_today}个任务")
            lines.append(f"- 最后活动: {status.last_activity.strftime('%Y-%m-%d %H:%M:%S')}")

        return '\n'.join(lines)

    def update_from_kanban(self, kanban_data: dict) -> None:
        """从kanban-doc数据更新状态"""
        # 这个方法将在集成kanban-doc时实现
        pass

    def sync_agent_status(self, agent_type: AgentType, status: AgentStatus,
                          current_task: Optional[str] = None,
                          current_project: Optional[str] = None) -> None:
        """同步Agent状态"""
        if agent_type not in self.agent_status:
            self.agent_status[agent_type] = AgentWorkStatus(
                agent_type=agent_type,
                status=status,
                current_task=current_task,
                current_project=current_project,
                last_activity=datetime.now(),
                completed_today=0
            )
        else:
            agent = self.agent_status[agent_type]
            agent.status = status
            agent.current_task = current_task
            agent.current_project = current_project
            agent.last_activity = datetime.now()


# 全局实例
state_manager = ProjectState()


if __name__ == "__main__":
    # 测试代码
    manager = ProjectState()

    # 创建测试会话
    manager.current_session = SessionContext(
        session_id="test-session-001",
        started_at=datetime.now(),
        last_sync_at=datetime.now(),
        current_focus="wordpress-decoration",
        next_steps=["整合密码机图片素材", "通知密码机确认效果"]
    )

    # 创建测试项目状态
    manager.projects["wordpress-decoration"] = ProjectStatus(
        project_name="wordpress-decoration",
        total_tasks=2,
        todo_count=0,
        inprogress_count=1,
        inreview_count=1,
        done_count=0,
        last_activity=datetime.now(),
        active_agents=[AgentType.KIMI]
    )

    # 创建测试任务
    manager.pending_tasks.append(Task(
        task_id="e278",
        project="wordpress-decoration",
        title="整合密码机提供的图片素材到网页",
        description="将密码机提供的图片素材整合到WordPress装修网页中",
        status=TaskStatus.IN_PROGRESS,
        priority="high",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        assigned_to=AgentType.KIMI
    ))

    # 创建测试Agent状态
    manager.sync_agent_status(
        AgentType.KIMI,
        AgentStatus.BUSY,
        current_task="e278",
        current_project="wordpress-decoration"
    )

    manager.sync_agent_status(
        AgentType.CODEX,
        AgentStatus.IDLE
    )

    # 保存快照
    manager.save_snapshot()
    print("✅ 状态快照已保存")

    # 生成每日摘要
    summary = manager.get_daily_summary()
    print("\n" + summary)

    # 测试恢复
    manager2 = ProjectState()
    if manager2.load_snapshot():
        print("\n✅ 状态恢复成功")
        print(f"恢复的项目数: {len(manager2.projects)}")
        print(f"恢复的任务数: {len(manager2.pending_tasks)}")
        print(f"恢复的Agent数: {len(manager2.agent_status)}")
    else:
        print("\n❌ 状态恢复失败")
