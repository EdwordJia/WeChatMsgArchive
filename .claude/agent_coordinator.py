"""
Agent协调器

负责任务分发、执行监控和结果验证。

核心功能：
- 根据任务类型智能分配Agent（Kimi/Codex）
- 通过kanban-doc runtime执行任务
- 监控任务执行状态
- 结果验证与反馈
"""

import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from enum import Enum
from dataclasses import dataclass


class AgentType(Enum):
    """Agent类型"""
    KIMI = "kimi"
    CODEX = "codex"
    CLAUDE = "claude"


class TaskType(Enum):
    """任务类型"""
    # Kimi擅长的任务
    FILE_OPERATION = "file"  # 文件操作
    DATA_PROCESSING = "data"  # 数据处理
    DOCUMENT = "document"  # 文档处理
    WEB_SEARCH = "web_search"  # Web搜索
    SYSTEM_CONFIG = "system"  # 系统配置
    GIT_OPERATION = "git"  # Git操作
    SHELL_SCRIPT = "shell"  # Shell脚本

    # Codex擅长的任务
    CODE_GENERATION = "code"  # 代码生成
    ALGORITHM = "algorithm"  # 算法设计
    CODE_REVIEW = "review"  # 代码审查
    TESTING = "test"  # 测试工程
    REFACTORING = "refactor"  # 代码重构
    DEBUGGING = "debug"  # Bug修复
    PERFORMANCE = "performance"  # 性能优化

    # 通用任务
    ANALYSIS = "analysis"  # 分析任务
    PLANNING = "planning"  # 规划任务


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ExecutionResult:
    """执行结果"""
    task_id: str
    agent: AgentType
    status: ExecutionStatus
    output: str
    error: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]

    def to_dict(self) -> dict:
        return {
        'task_id': self.task_id,
            'agent': self.agent.value,
            'status': self.status.value,
            'output': self.output,
            'error': self.error,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        'duration_seconds': self.duration_seconds
        }


class AgentCoordinator:
    """Agent协调器"""

    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or Path(".claude/state/agent_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 任务类型到Agent的映射规则
        self.task_agent_mapping = {
            # Kimi负责的任务
            TaskType.FILE_OPERATION: AgentType.KIMI,
            TaskType.DATA_PROCESSING: AgentType.KIMI,
            TaskType.DOCUMENT: AgentType.KIMI,
          TaskType.WEB_SEARCH: AgentType.KIMI,
          TaskType.SYSTEM_CONFIG: AgentType.KIMI,
            TaskType.GIT_OPERATION: AgentType.KIMI,
            TaskType.SHELL_SCRIPT: AgentType.KIMI,

            # Codex负责的任务
            TaskType.CODE_GENERATION: AgentType.CODEX,
            TaskType.ALGORITHM: AgentType.CODEX,
            TaskType.CODE_REVIEW: AgentType.CODEX,
            TaskType.TESTING: AgentType.CODEX,
          TaskType.REFACTORING: AgentType.CODEX,
            TaskType.DEBUGGING: AgentType.CODEX,
         TaskType.PERFORMANCE: AgentType.CODEX,
        }

        # 执行历史
        self.execution_history: List[ExecutionResult] = []

    def assign_task(self, task_type: TaskType, task_description: str = "") -> AgentType:
        """
        根据任务类型分配Agent

        Args:
            task_type: 任务类型
            task_description: 任务描述（用于智能判断）

        Returns:
            分配的Agent类型
        """
        # 基于规则的分配
        if task_type in self.task_agent_mapping:
            return self.task_agent_mapping[task_type]

        # 通用任务需要根据描述智能判断
        if task_type in [TaskType.ANALYSIS, TaskType.PLANNING]:
            # 简单的关键词匹配
      code_keywords = ['代码', '算法', '函数', '类', '测试', 'bug', 'code', 'algorithm', 'function', 'class', 'test']
            data_keywords = ['文件', '数据', '文档', '表格', 'excel', 'csv', 'pdf', 'word', 'file', 'data', 'document']

            desc_lower = task_description.lower()

            code_score = sum(1 for kw in code_keywords if kw in desc_lower)
          data_score = sum(1 for kw in data_keywords if kw in desc_lower)

            if code_score > data_score:
             return AgentType.CODEX
        elif data_score > code_score:
            return AgentType.KIMI
            else:
                # 默认分配给Kimi（广度优先）
              return AgentType.KIMI

        # 默认分配给Claude自己处理
        return AgentType.CLAUDE

    def execute_task(self, task_id: str, agent: AgentType, prompt: str,
                     project: str = None, timeout: int = 300) -> ExecutionResult:
        """
        执行任务

        Args:
            task_id: 任务ID
        agent: 执行的Agent
            prompt: 任务提示词
            project: 项目名称（用于kanban-doc）
            timeout: 超时时间（秒）

        Returns:
            执行结果
        """
        started_at = datetime.now()
        result = ExecutionResult(
            task_id=task_id,
            agent=agent,
            status=ExecutionStatus.RUNNING,
            output="",
        error=None,
            started_at=started_at,
            completed_at=None,
            duration_seconds=None
        )

        try:
            if agent == AgentType.KIMI:
                output, error = self._execute_kimi(prompt, timeout)
            elif agent == AgentType.CODEX:
                output, error = self._execute_codex(prompt, timeout)
            else:
                output = "任务由Claude主Agent处理"
             error = None

          completed_at = datetime.now()
       duration = (completed_at - started_at).total_seconds()

            result.status = ExecutionStatus.SUCCESS if not error else ExecutionStatus.FAILED
            result.output = output
            result.error = error
            result.completed_at = completed_at
        result.duration_seconds = duration

        except subprocess.TimeoutExpired:
          result.status = ExecutionStatus.TIMEOUT
            result.error = f"任务执行超时（{timeout}秒）"
            result.completed_at = datetime.now()
            result.duration_seconds = timeout

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
          result.completed_at = datetime.now()
            result.duration_seconds = (datetime.now() - started_at).total_seconds()

        # 记录执行历史
        self.execution_history.append(result)
        self._log_execution(result)

        return result

    def _execute_kimi(self, prompt: str, timeout: int) -> tuple[str, Optional[str]]:
        """执行Kimi任务"""
      try:
       # 调用Kimi CLI
            cmd = ["kimi", prompt]
            process = subprocess.run(
                cmd,
              capture_output=True,
              text=True,
                timeout=timeout,
                encoding='utf-8'
          )

            if process.returncode == 0:
              return process.stdout, None
            else:
                return process.stdout, process.stderr

        except FileNotFoundError:
            return "", "Kimi CLI未安装或不在PATH中"
        except Exception as e:
            return "", str(e)

    def _execute_codex(self, prompt: str, timeout: int) -> tuple[str, Optional[str]]:
        """执行Codex任务"""
        try:
            # 调用Codex CLI
         cmd = ["codex", prompt]
          process = subprocess.run(
                cmd,
              capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8'
            )

            if process.returncode == 0:
                return process.stdout, None
            else:
                return process.stdout, process.stderr

        except FileNotFoundError:
        return "", "Codex CLI未安装或不在PATH中"
        except Exception as e:
            return "", str(e)

    def monitor_execution(self, task_id: str) -> Optional[ExecutionResult]:
        """
        监控任务执行状态

        Args:
            task_id: 任务ID

      Returns:
            执行结果（如果找到）
        """
        for result in reversed(self.execution_history):
            if result.task_id == task_id:
             return result
        return None

    def get_agent_statistics(self, agent: AgentType) -> Dict:
        """
        获取Agent统计信息

        Args:
            agent: Agent类型

        Returns:
            统计信息字典
        """
        agent_results = [r for r in self.execution_history if r.agent == agent]

     if not agent_results:
        return {
           'total_tasks': 0,
                'success_count': 0,
         'failed_count': 0,
            'timeout_count': 0,
                'success_rate': 0.0,
                'avg_duration': 0.0
          }

      success_count = sum(1 for r in agent_results if r.status == ExecutionStatus.SUCCESS)
        failed_count = sum(1 for r in agent_results if r.status == ExecutionStatus.FAILED)
        timeout_count = sum(1 for r in agent_results if r.status == ExecutionStatus.TIMEOUT)

        durations = [r.duration_seconds for r in agent_results if r.duration_seconds is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

      return {
        'total_tasks': len(agent_results),
            'success_count': success_count,
            'failed_count': failed_count,
            'timeout_count': timeout_count,
            'success_rate': success_count / len(agent_results) if agent_results else 0.0,
            'avg_duration': avg_duration
        }

    def _log_execution(self, result: ExecutionResult) -> None:
      """记录执行日志"""
        log_file = self.log_dir / f"{result.agent.value}_executions.jsonl"

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result.to_dict(), ensure_ascii=False) + '\n')

    def get_execution_summary(self) -> str:
        """获取执行摘要"""
        lines = []
      lines.append("# Agent执行摘要")
        lines.append(f"\n总执行次数: {len(self.execution_history)}")

        for agent in AgentType:
            stats = self.get_agent_statistics(agent)
        if stats['total_tasks'] > 0:
                lines.append(f"\n## {agent.value}")
                lines.append(f"- 总任务数: {stats['total_tasks']}")
              lines.append(f"- 成功: {stats['success_count']} | 失败: {stats['failed_count']} | 超时: {stats['timeout_count']}")
             lines.append(f"- 成功率: {stats['success_rate']:.1%}")
                lines.append(f"- 平均耗时: {stats['avg_duration']:.2f}秒")

        return '\n'.join(lines)


# 全局实例
agent_coordinator = AgentCoordinator()


if __name__ == "__main__":
    # 测试代码
    coordinator = AgentCoordinator()

    # 测试任务分配
    print("=== 测试任务分配 ===")
    test_cases = [
        (TaskType.FILE_OPERATION, "批量重命名文件"),
        (TaskType.CODE_GENERATION, "实现快速排序算法"),
        (TaskType.DATA_PROCESSING, "清洗Excel数据"),
        (TaskType.CODE_REVIEW, "审查代码安全性"),
        (TaskType.ANALYSIS, "分析代码性能瓶颈"),
        (TaskType.ANALYSIS, "分析Excel数据趋势"),
    ]

    for task_type, description in test_cases:
        agent = coordinator.assign_task(task_type, description)
        print(f"{task_type.value} - {description} → {agent.value}")

    # 测试任务执行（模拟）
    print("\n=== 测试任务执行 ===")
    result = coordinator.execute_task(
        task_id="test-001",
        agent=AgentType.KIMI,
        prompt="列出当前目录的文件",
        timeout=10
    )
    print(f"任务状态: {result.status.value}")
    print(f"执行耗时: {result.duration_seconds:.2f}秒")
    if result.error:
        print(f"错误信息: {result.error}")

    # 测试统计信息
    print("\n=== Agent统计信息 ===")
    print(coordinator.get_execution_summary())
