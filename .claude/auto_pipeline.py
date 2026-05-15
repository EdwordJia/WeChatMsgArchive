# -*- coding: utf-8 -*-
"""
AutoPipeline: WeChat requirements to Kanban tasks to Agent execution
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
claude_dir = Path(__file__).parent
sys.path.insert(0, str(claude_dir))

from state_manager import ProjectState
from project_manager import ProjectManager


class AutoPipeline:
    def __init__(self):
        self.state = ProjectState()
        self.manager = ProjectManager()
        self.log_file = Path(".claude/state/auto_pipeline.log")

    def run(self, mode: str = "manual") -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("AutoPipeline")
        lines.append("=" * 60)
        lines.append(f"Mode: {mode}, Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        messages = self._fetch_latest_messages()
        lines.append(f"[1/5] Messages: {len(messages)}")

        requirements = self._identify_requirements(messages)
        lines.append(f"[2/5] Requirements: {len(requirements)}")

        created_tasks = self._create_kanban_tasks(requirements)
        lines.append(f"[3/5] Tasks created: {len(created_tasks)}")

        assignments = self._assign_agents(created_tasks)
        lines.append(f"[4/5] Agents assigned: {len(assignments)}")

        executions = self._start_executions(assignments)
        lines.append(f"[5/5] Executions started: {len(executions)}")
        self._save_log({
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "messages_count": len(messages),
            "requirements_count": len(requirements),
            "tasks_created": len(created_tasks),
            "agents_assigned": len(assignments),
            "executions_started": len(executions),
        })

        lines.append("=" * 60)
        return "\n".join(lines)

    def _fetch_latest_messages(self) -> List[Dict]:
        """
        获取微信群最新消息

        组合思维：调用现有的wechat-data MCP工具
        """
        try:
            # TODO: 调用wechat-data MCP获取最近24小时的群消息
            # 示例：mcp__wechat_data__query_recent_messages(hours=24)
            # 暂时返回空列表，等待MCP集成
            return []
        except Exception as e:
            print(f"Failed to fetch messages: {e}")
            return []

    def _identify_requirements(self, messages: List[Dict]) -> List[Dict]:
        if not messages:
            return []
        try:
            from llm_requirement_analyzer import LLMRequirementAnalyzer

            analyzer = LLMRequirementAnalyzer()
            results = analyzer.batch_analyze(messages, threshold=0.7)
            requirements = []
            for result in results:
                req = {
                    "type": result["type"],
                    "priority": result["priority"],
                    "title": result["title"],
                    "description": result["description"],
                    "tags": result["tags"],
                    "confidence": result["confidence"],
                    "source_message": result.get("source_message", {}),
                }
                requirements.append(req)
            return requirements
        except Exception as e:
            print(f"LLM analysis failed: {e}")
            return []

    def _create_kanban_tasks(self, requirements: List[Dict]) -> List[str]:
        """
        将需求转换为看板任务

        组合思维：返回待创建的任务信息，由Claude会话执行MCP调用
        """
        if not requirements:
            return []
        self.pending_tasks = []
        project_mapping = {
            "linux-qt-jr": ["qt", "ui"],
            "wordpress-decoration": ["wordpress"],
            "MCE": ["mce"],
            "syc-player": ["player"],
        }
        created_tasks = []
        for idx, req in enumerate(requirements, start=1):
            try:
                project = self._map_requirement_to_project(req, project_mapping)
                if project:
                    temp_id = f"pending-{idx}"
                    task_info = {
                        'temp_id': temp_id,
                        'project': project,
                        'title': req['title'],
                        'body': req['description'],
                        'priority': req['priority'],
                        'tags': req['tags']
                    }
                    self.pending_tasks.append(task_info)
                    created_tasks.append(temp_id)
            except Exception:
                continue
        return created_tasks

    def _map_requirement_to_project(self, req: Dict, project_mapping: Dict) -> Optional[str]:
        text = (req.get("title", "") + " " + req.get("description", "")).lower()
        for project, keywords in project_mapping.items():
            if any(kw in text for kw in keywords):
                return project
        return "WeChatMsgArchive"

    def _assign_agents(self, task_ids: List[str]) -> Dict[str, str]:
        if not task_ids:
            return {}
        assignments = {}
        for task_id in task_ids:
            try:
                task_desc = f"Task {task_id}"
                recommendation = self.manager.assign_task_to_agent(task_desc)
                if "Codex" in recommendation:
                    agent = "codex"
                elif "Kimi" in recommendation:
                    agent = "kimi"
                else:
                    agent = "kimi"
                assignments[task_id] = agent
            except Exception:
                assignments[task_id] = "kimi"
        return assignments

    def _start_executions(self, assignments: Dict[str, str]) -> List[str]:
        """
        启动Agent执行分配的任务

        组合思维：返回待启动的执行信息，由Claude会话执行MCP调用
        """
        if not assignments:
            return []
        self.pending_executions = []
        executions = []
        for idx, (task_id, agent_name) in enumerate(assignments.items(), start=1):
            try:
                temp_id = f"exec-{idx}"
                execution_info = {
                    'temp_id': temp_id,
                    'task_id': task_id,
                    'agent': agent_name
                }
                self.pending_executions.append(execution_info)
                executions.append(temp_id)
            except Exception:
                continue
        return executions

    def _save_log(self, log_data: Dict):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_data, ensure_ascii=False) + "\n")


auto_pipeline = AutoPipeline()

if __name__ == "__main__":
    pipeline = AutoPipeline()
    output = pipeline.run(mode="manual")
    print(output)
