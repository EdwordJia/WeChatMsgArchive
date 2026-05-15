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
try:
    from wechat_msg_reader import fetch_recent_messages  # v2: correct MSG table
except ImportError:
    from wechat_message_fetcher import fetch_recent_messages  # legacy fallback


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

    def _fetch_latest_messages(self):
        """Stage 1: fetch business-channel messages, skip ME-sent."""
        try:
            from business_channels import get_business_channels
            whitelist = get_business_channels()
        except ImportError:
            whitelist = None
        try:
            msgs = fetch_recent_messages(hours=24*30, chatroom_filter=whitelist)
            msgs = [m for m in msgs if m.get("is_sender") != 1]
            return msgs
        except Exception as exc:
            print("fetch failed:", exc)
            return []
    def _identify_requirements(self, messages: List[Dict]) -> List[Dict]:
        if not messages:
            return []
        try:
            from llm_requirement_analyzer import LLMRequirementAnalyzer

            analyzer = LLMRequirementAnalyzer()
            results = analyzer.batch_analyze(messages, threshold=0.5)
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

    def _create_kanban_tasks(self, requirements):
        """Stage 3: write task .md files directly to .kanban (plan C)."""
        if not requirements:
            return []
        self.pending_tasks = []
        try:
            from kanban_writer import write_task
        except ImportError:
            write_task = None
        try:
            from business_channels import channel_to_project
        except ImportError:
            channel_to_project = lambda _: None
        project_mapping = {
            "linux-qt-jr": ["qt", "ui", "linux", "ubuntu"],
            "wordpress-decoration": ["wordpress", "网站", "图片", "装修"],
            "MCE": ["mce", "medchemexpress", "爬虫"],
            "syc-player": ["player", "歌词", "音乐", "播放器"],
            "ai-zs": ["法律", "文书", "合同", "起诉", "律师", "公章", "诉讼", "案件", "ocr", "户籍", "原告", "被告", "委托书", "案由", "条款"],
            "xiaozhan-emoji-generator": ["表情包", "肖战"],
            "travel-sentiment-analysis": ["旅游", "评论", "情感", "携程", "微博"],
        }
        created = []
        for idx, req in enumerate(requirements, start=1):
            try:
                src_msg = req.get("source_message") or {}
                channel = src_msg.get("chatroom") or src_msg.get("sender_wxid")
                project = channel_to_project(channel) if channel else None
                if not project:
                    project = self._map_requirement_to_project(req, project_mapping)
                if not project:
                    continue
                title = (req.get("title") or "no-title")[:120]
                desc = req.get("description", "")
                src_time = src_msg.get("time", "")
                src_room = src_msg.get("chatroom_name") or channel or ""
                src_sender = src_msg.get("sender", "")
                body = desc + chr(10) + chr(10) + "## 来源" + chr(10) + "- 时间: " + str(src_time) + chr(10) + "- 群/联系人: " + str(src_room) + chr(10) + "- 发送人: " + str(src_sender)
                tags = list(req.get("tags") or []) + ["auto-pipeline"]
                priority = req.get("priority", "medium")
                if write_task is not None:
                    tid, fpath = write_task(project, title, body, priority=priority, tags=tags)
                    self.pending_tasks.append({"task_id": tid, "project": project, "title": title, "file": fpath})
                    created.append(tid)
                else:
                    self.pending_tasks.append({"temp_id": "pending-" + str(idx), "project": project, "title": title, "body": body, "priority": priority, "tags": tags})
                    created.append("pending-" + str(idx))
            except Exception as exc:
                print("create_task fail #" + str(idx) + ":", exc)
                continue
        return created

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
