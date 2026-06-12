# -*- coding: utf-8 -*-
"""
AutoPipeline: WeChat requirements to Kanban tasks to Agent execution
"""

import json
import re
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
try:
    from wechat_attachment_parser import summarize_attachments, get_reference_image_paths
except ImportError:
    summarize_attachments = lambda a: ""
    get_reference_image_paths = lambda a: []


_BAD_TITLE_TOKENS = ("<?xml", "<msg", "<img", "[无文本", "GROUP:", "ME:", "cdnthumburl", "aeskey=", "[附件/多模态证据]")


def _text_lines(text: str) -> List[str]:
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or "[无文本内容]" in line:
            continue
        lower = line.lower()
        if lower.startswith("<?xml") or lower.startswith("<msg"):
            continue
        if any(token in lower for token in ("<img ", "<voicemsg", "<appmsg", "cdnthumburl=", "aeskey=")):
            continue
        # 保留附件描述行
        cleaned = re.sub(r"^[-*]\s+", "", line).strip()
        if cleaned.startswith(("[图片]", "[语音]", "[视频]", "[文件]", "[链接]", "[小程序]", "[合并转发聊天记录]", "[表情包]", "[系统消息]")):
            lines.append(cleaned)
            continue
        line = re.sub(r"^\[[^\]]+\]\s*[^:：]{1,40}[:：]\s*", "", line).strip()
        line = re.sub(r"^#+\s*", "", line).strip()
        line = re.sub(r"^[-*]\s+", "", line).strip()
        if line in ("背景", "背景/问题", "客户原话", "客户原话/上下文", "验收标准", "原始证据摘要", "来源") or "[附件/多模态证据]" in line:
            continue
        if line:
            lines.append(line)
    return lines


def _is_bad_title(title: str) -> bool:
    if not title or len(title.strip()) < 4:
        return True
    return any(token.lower() in title.lower() for token in _BAD_TITLE_TOKENS)


def _fallback_title(req: Dict) -> str:
    candidates = []
    candidates.extend(_text_lines(req.get("description", "")))
    thread = req.get("source_thread") or {}
    candidates.extend(_text_lines(thread.get("content", "")))
    msg = req.get("source_message") or {}
    candidates.extend(_text_lines(msg.get("content", "")))
    for line in candidates:
        # 去掉附件描述前缀（如 [语音] 8.3秒 转文字: ...）
        title = re.sub(r"^\[(图片|语音|视频|文件|链接|小程序|合并转发聊天记录|表情包|系统消息)\][^:：]*[：:]\s*", "", line).strip()
        # 去掉前缀后如果只剩文件路径，跳过
        title = title.rstrip("]")
        if re.search(r'[\\/][^\\/]+\.(png|jpg|jpeg|gif|webp|psd|pdf|doc|docx|xls|xlsx)$', title, re.IGNORECASE):
            continue
        title = re.sub(r"[。！？!?].*$", "", title).strip(" ，,。]")
        title = re.sub(r"@\S+\s*", "", title).strip()
        if len(title) > 50:
            title = title[:50].rstrip("，,。]")
        if not _is_bad_title(title):
            return title
    return ""


def _build_task_body(req: Dict, title: str, src_msg: Dict, src_thread: Dict, channel: str) -> str:
    desc = (req.get("description") or "").strip()
    customer_lines = _text_lines(src_thread.get("content") or src_msg.get("content") or "")
    evidence = src_thread.get("evidence_summary") or []
    src_time = src_thread.get("start_time") or src_msg.get("time", "")
    src_end_time = src_thread.get("end_time") or src_time
    src_room = src_msg.get("chatroom_name") or src_thread.get("chatroom_name") or channel or ""
    src_sender = src_msg.get("sender") or src_thread.get("sender") or ""
    msg_count = src_thread.get("message_count", req.get("message_count", 1))

    # 提取附件信息
    attachments = src_msg.get("attachments") or src_thread.get("attachments") or []
    has_attachments = bool(attachments)
    attachment_summary = summarize_attachments(attachments) if has_attachments else ""
    ref_images = get_reference_image_paths(attachments) if has_attachments else []

    # 判断 desc 是否已经是结构化的 markdown（LLM 模式返回的 description 自带标题）
    desc_has_headers = desc and "## " in desc

    lines = ["## 背景/问题"]
    if desc_has_headers:
        lines.append(desc)
    else:
        lines.append(desc or title)

    if not desc_has_headers:
        lines.extend(["", "## 客户原话/上下文"])
        if customer_lines:
            lines.extend(["- " + line for line in customer_lines[:10]])
        elif has_attachments:
            lines.append("- （该消息仅包含附件，无文本内容）")
        else:
            lines.append("- 无可用文本原话；仅保留附件证据，未自动创建任务。")
        lines.extend([
            "",
            "## 验收标准",
            "- 相关页面或流程符合客户反馈描述",
            "- 修复/调整后用客户提到的场景复测通过",
        ])

    lines.extend(["", "## 原始证据摘要"])
    if evidence:
        lines.extend(["- " + str(item) for item in evidence[:10]])
    if attachment_summary:
        lines.extend(["", "### 附件/多模态证据", attachment_summary])
    if ref_images:
        lines.extend(["", "### 参考图片路径"] + [f"- {p}" for p in ref_images])
    if not evidence and not attachment_summary:
        lines.append("- 无附件/无文本证据")
    lines.extend([
        "",
        "## 来源",
        "- 时间: " + str(src_time) + " ~ " + str(src_end_time),
        "- 群/联系人: " + str(src_room),
        "- 发送人: " + str(src_sender),
        "- 线程消息数: " + str(msg_count),
    ])
    return "\n".join(lines)


class AutoPipeline:
    def __init__(self):
        self.state = ProjectState()
        self.manager = ProjectManager()
        self.log_file = Path(".claude/state/auto_pipeline.log")
        self.pending_tasks = []
        self.pending_executions = []
        self._analysis_failed = False

    def _sync_wechat_if_needed(self, max_age_hours: float = 2.0) -> str:
        """检查数据库时效性，如需同步则自动触发解密和增量同步。"""
        from pathlib import Path
        import sqlite3
        import subprocess

        db_dir = Path("output/decrypted_db")
        if not db_dir.exists():
            return "no_db_dir"

        # 获取 decrypted_db 中最新消息时间
        newest_ts = 0
        for p in sorted((db_dir / "Multi").glob("MSG*.db")):
            try:
                cur = sqlite3.connect(str(p)).cursor()
                cur.execute("SELECT MAX(CreateTime) FROM MSG")
                ts = cur.fetchone()[0] or 0
                if ts > newest_ts:
                    newest_ts = ts
            except Exception:
                pass

        if newest_ts == 0:
            return "no_msgs_in_db"

        age_hours = (datetime.now().timestamp() - newest_ts) / 3600
        if age_hours < max_age_hours:
            return f"fresh ({age_hours:.1f}h)"

        # 需要同步，检查微信进程
        try:
            import psutil
            wechat_running = any(p.name() == "WeChat.exe" for p in psutil.process_iter(["name"]))
        except Exception:
            wechat_running = False

        if not wechat_running:
            return f"stale ({age_hours:.1f}h) WeChat.exe not running — start WeChat to sync"

        # 检测 venv 中的 python 路径
        venv_python = None
        for candidate in (
            project_root / "venv" / "Scripts" / "python.exe",
            project_root / "venv" / "bin" / "python",
        ):
            if candidate.exists():
                venv_python = str(candidate)
                break
        py_exe = venv_python or sys.executable

        # 执行解密
        print(f"[sync] DB stale ({age_hours:.1f}h), WeChat running, starting decrypt...")
        try:
            result = subprocess.run(
                [py_exe, "decrypt_single.py"],
                capture_output=True, text=True, timeout=300, cwd=str(project_root),
            )
            if result.returncode != 0:
                return f"decrypt_failed: {result.stderr[:200]}"
            print(f"[sync] decrypt done")
        except Exception as e:
            return f"decrypt_error: {e}"

        # 执行增量同步（索引数据库）
        try:
            result = subprocess.run(
                [py_exe, "incremental_sync.py"],
                capture_output=True, text=True, timeout=300, cwd=str(project_root),
            )
            if result.returncode != 0:
                print(f"[sync] incremental_sync warning: {result.stderr[:200]}")
            else:
                print(f"[sync] incremental_sync done")
        except Exception as e:
            print(f"[sync] incremental_sync skipped: {e}")

        return f"synced (was {age_hours:.1f}h stale)"

    def run(self, mode: str = "manual") -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("AutoPipeline")
        lines.append("=" * 60)
        lines.append(f"Mode: {mode}, Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        sync_status = self._sync_wechat_if_needed()
        lines.append(f"[0/5] Sync: {sync_status}")

        messages = self._fetch_latest_messages()
        lines.append(f"[1/5] Messages: {len(messages)}")

        threads = self._build_threads(messages)
        lines.append(f"[1.5/5] Threads: {len(threads)}")

        requirements = self._identify_requirements(threads)
        lines.append(f"[2/5] Requirements: {len(requirements)}")

        if not self._analysis_failed:
            try:
                from dedup_state import mark_non_requirement_messages_seen

                mark_non_requirement_messages_seen(messages, requirements)
            except Exception as exc:
                print("dedup non-requirement mark_seen failed:", exc)

        created_tasks = self._create_kanban_tasks(requirements)
        lines.append(f"[3/5] Tasks ready: {len(created_tasks)}")

        retry_tasks = self._load_retryable_runtime_tasks(created_tasks)
        lines.append(f"[3.5/5] Runtime retries: {len(retry_tasks)}")

        executable_tasks = list(dict.fromkeys(created_tasks + retry_tasks))
        assignments = self._assign_agents(executable_tasks)
        lines.append(f"[4/5] Agents assigned: {len(assignments)}")

        executions = self._start_executions(assignments)
        lines.append(f"[5/5] Executions started: {len(executions)}")

        self._save_log({
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "messages_count": len(messages),
            "threads_count": len(threads),
            "requirements_count": len(requirements),
            "tasks_ready": len(created_tasks),
            "runtime_retries": len(retry_tasks),
            "agents_assigned": len(assignments),
            "executions_started": len(executions),
        })

        lines.append("=" * 60)
        return "\n".join(lines)

    def _fetch_latest_messages(self):
        """Stage 1: fetch + skip ME + sender whitelist + dedup."""
        self._fetched_unseen = []
        try:
            from config_loader import get_business_channels, is_sender_allowed, get_message_fetch_config
            whitelist = get_business_channels()
            fetch_cfg = get_message_fetch_config()
        except ImportError:
            whitelist = None
            fetch_cfg = {"hours": 720, "skip_self": True}
        try:
            msgs = fetch_recent_messages(hours=fetch_cfg.get("hours", 720), chatroom_filter=whitelist)
            try:
                from config_loader import get_threading_config
                threading_enabled = get_threading_config().get("enabled", False)
            except Exception:
                threading_enabled = False
            if fetch_cfg.get("skip_self", True) and not threading_enabled:
                msgs = [m for m in msgs if m.get("is_sender") != 1]
            try:
                before2 = len(msgs)
                msgs = [m for m in msgs if m.get("is_sender") == 1 or is_sender_allowed(m.get("chatroom"), m.get("sender_wxid", ""))]
                print("[sender_filter] " + str(before2) + " -> " + str(len(msgs)))
            except Exception:
                pass
        except Exception as exc:
            print("fetch failed:", exc)
            return []
        try:
            from dedup_state import filter_unseen
            before = len(msgs)
            msgs = filter_unseen(msgs)
            self._fetched_unseen = msgs
            print("[dedup] " + str(before) + " total -> " + str(len(msgs)) + " unseen")
        except Exception as exc:
            print("dedup filter skipped:", exc)
            self._fetched_unseen = msgs
        return msgs

    def _build_threads(self, messages: List[Dict]) -> List[Dict]:
        try:
            from config_loader import get_threading_config
            cfg = get_threading_config()
            if not cfg.get("enabled", False):
                return messages
            from message_threader import build_threads
            threads = build_threads(
                messages,
                window_minutes=cfg.get("window_minutes", 30),
                max_thread_size=cfg.get("max_thread_size", 10),
                max_thread_chars=cfg.get("max_thread_chars", 6000),
            )
            print("[threading] " + str(len(messages)) + " messages -> " + str(len(threads)) + " threads")
            return threads
        except Exception as exc:
            print("threading skipped:", exc)
            return messages

    def _identify_requirements(self, messages: List[Dict]) -> List[Dict]:
        self._analysis_failed = False
        if not messages:
            return []
        try:
            from llm_requirement_analyzer import LLMRequirementAnalyzer
            from config_loader import get_llm_config

            llm_cfg = get_llm_config()
            threshold = llm_cfg.get("threshold", 0.5)

            analyzer = LLMRequirementAnalyzer()
            # 将附件描述嵌入消息/线程内容，让LLM分析器能利用多模态证据
            enriched_messages = []
            for msg in messages:
                msg_copy = dict(msg)
                attachments = msg.get("attachments", [])
                # 如果线程包含嵌套消息，也收集其附件
                nested = msg.get("messages")
                if nested:
                    for m in nested:
                        m_atts = m.get("attachments", [])
                        if m_atts:
                            attachments.extend(m_atts)
                if attachments:
                    att_summary = summarize_attachments(attachments)
                    if att_summary:
                        original_content = msg_copy.get("content") or ""
                        msg_copy["content"] = original_content + "\n\n[附件/多模态证据]\n" + att_summary
                enriched_messages.append(msg_copy)

            if messages and messages[0].get("messages") is not None:
                results = analyzer.batch_analyze_threads(enriched_messages, threshold=threshold)
            else:
                results = analyzer.batch_analyze(enriched_messages, threshold=threshold)
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
                    "source_thread": result.get("source_thread", {}),
                    "message_count": result.get("message_count", 1),
                }
                requirements.append(req)
            return requirements
        except Exception as e:
            self._analysis_failed = True
            print(f"LLM analysis failed: {e}")
            return []

    def _create_kanban_tasks(self, requirements):
        """Stage 3: write task .md files directly to .kanban (plan C)."""
        self.pending_tasks = []
        if not requirements:
            return []
        try:
            from auto_invoke_mcp import create_task_via_mcp
        except Exception:
            create_task_via_mcp = None
        try:
            from kanban_writer import write_task
        except ImportError:
            write_task = None
        try:
            from config_loader import (
                channel_to_project as _channel_to_project,
                get_keyword_mapping,
            )
        except ImportError:
            _channel_to_project = lambda _: None
            get_keyword_mapping = lambda: {}
        try:
            from dedup_state import (
                get_requirement_record,
                mark_requirement_failed,
                mark_requirement_messages_seen,
                mark_requirement_task,
            )
        except Exception:
            get_requirement_record = lambda _: None
            mark_requirement_failed = lambda *_, **__: None
            mark_requirement_messages_seen = lambda _: None
            mark_requirement_task = lambda *_, **__: None

        project_mapping = get_keyword_mapping()
        created = []
        for idx, req in enumerate(requirements, start=1):
            src_msg = req.get("source_message") or {}
            src_thread = req.get("source_thread") or {}
            channel = src_msg.get("chatroom") or src_thread.get("chatroom") or src_msg.get("sender_wxid")
            project = _channel_to_project(channel) if channel else None
            if not project:
                project = self._map_requirement_to_project(req, project_mapping)
            if not project:
                continue

            title = (req.get("title") or "").strip()[:120]
            if _is_bad_title(title):
                title = _fallback_title(req)
            if _is_bad_title(title):
                print("skip unusable auto-task title #" + str(idx) + ": " + str(req.get("title", ""))[:80])
                mark_requirement_messages_seen(req)
                continue
            src_time = src_thread.get("start_time") or src_msg.get("time", "")
            src_end_time = src_thread.get("end_time") or src_time
            src_room = src_msg.get("chatroom_name") or src_thread.get("chatroom_name") or channel or ""
            src_sender = src_msg.get("sender") or src_thread.get("sender") or ""
            msg_count = src_thread.get("message_count", 1)
            body = _build_task_body(req, title, src_msg, src_thread, channel)
            if "无可用文本原话；仅保留附件证据，未自动创建任务。" in body:
                print("skip auto-task #" + str(idx) + " (no text and no attachments): " + title)
                mark_requirement_messages_seen(req)
                continue
            tags = list(req.get("tags") or []) + ["auto-pipeline"]
            priority = req.get("priority", "medium")

            existing = get_requirement_record(req)
            if existing and existing.get("task_id") and existing.get("task_status") != "failed":
                tid = existing["task_id"]
                self.pending_tasks.append({
                    "task_id": tid,
                    "project": existing.get("project", project),
                    "title": existing.get("title", title),
                    "tags": existing.get("tags", tags),
                    "priority": existing.get("priority", priority),
                    "agent": existing.get("agent"),
                    "resumed": True,
                })
                mark_requirement_messages_seen(req)
                created.append(tid)
                continue

            task_created = False
            last_error = None
            if create_task_via_mcp is not None:
                try:
                    tid, mcp_result = create_task_via_mcp(project, title, body, priority=priority, tags=tags)
                    self.pending_tasks.append({"task_id": tid, "project": project, "title": title, "mcp_result": mcp_result, "tags": tags, "priority": priority})
                    mark_requirement_task(req, project, tid, title=title, priority=priority, tags=tags, metadata={"mcp_result": mcp_result})
                    mark_requirement_messages_seen(req)
                    created.append(tid)
                    task_created = True
                except Exception as exc:
                    last_error = exc
                    print("mcp create_task failed, fallback to local writer:", exc)
            if task_created:
                continue
            if write_task is not None:
                try:
                    tid, fpath = write_task(project, title, body, priority=priority, tags=tags)
                    self.pending_tasks.append({"task_id": tid, "project": project, "title": title, "file": fpath, "tags": tags, "priority": priority, "fallback": "kanban_writer"})
                    mark_requirement_task(req, project, tid, title=title, priority=priority, tags=tags, metadata={"file": fpath, "fallback": "kanban_writer"})
                    mark_requirement_messages_seen(req)
                    created.append(tid)
                    task_created = True
                except Exception as exc:
                    last_error = exc
                    print("local write_task failed:", exc)
            if task_created:
                continue
            if last_error is None:
                last_error = RuntimeError("no task writer available")
            mark_requirement_failed(req, "create_task", last_error, retryable=True)
            print("create_task fail #" + str(idx) + ":", last_error)
        return created

    def _load_retryable_runtime_tasks(self, known_task_ids=None):
        known = set(known_task_ids or [])
        existing_meta_ids = {t.get("task_id", t.get("temp_id")) for t in self.pending_tasks}
        retry_tasks = []
        try:
            from dedup_state import list_runtime_retryable
        except Exception:
            return []
        for record in list_runtime_retryable():
            task_id = record.get("task_id")
            if not task_id or task_id in existing_meta_ids:
                continue
            runtime = record.get("runtime") or {}
            self.pending_tasks.append({
                "task_id": task_id,
                "project": record.get("project", "WeChatMsgArchive"),
                "title": record.get("title", ""),
                "tags": record.get("tags") or [],
                "priority": record.get("priority", "medium"),
                "agent": record.get("agent") or runtime.get("agent"),
                "retryable": True,
            })
            existing_meta_ids.add(task_id)
            if task_id not in known:
                retry_tasks.append(task_id)
        return retry_tasks

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
        task_meta = {t.get("task_id", t.get("temp_id")): t for t in (self.pending_tasks or [])}
        for task_id in task_ids:
            meta = task_meta.get(task_id, {})
            if meta.get("agent"):
                assignments[task_id] = meta["agent"]
                continue
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

    def _start_executions(self, assignments):
        """Stage 5: queue runtime executions (require_approval=true by default)."""
        self.pending_executions = []
        if not assignments:
            return []
        try:
            from auto_invoke_mcp import start_runtime_via_mcp
        except Exception:
            start_runtime_via_mcp = None
        try:
            from runtime_starter import queue_runtime
        except ImportError:
            queue_runtime = None
        try:
            from dedup_state import mark_runtime_status
        except Exception:
            mark_runtime_status = lambda *_, **__: None

        task_meta = {t.get("task_id", t.get("temp_id")): t for t in (self.pending_tasks or [])}
        started = []
        for task_id, agent_name in assignments.items():
            meta = task_meta.get(task_id, {})
            project = meta.get("project", "WeChatMsgArchive")
            title = meta.get("title", "")
            tags = meta.get("tags") or []
            try:
                from config_loader import decide_approval
                need_approval = decide_approval(tags)
            except Exception:
                need_approval = True

            runtime_error = None
            if start_runtime_via_mcp is not None:
                try:
                    entry = start_runtime_via_mcp(task_id=task_id, project=project, title=title, agent=agent_name, require_approval=need_approval, run_reason="auto-pipeline")
                    self.pending_executions.append(entry)
                    mark_runtime_status(task_id, "started", execution=entry, retryable=False)
                    started.append(task_id)
                    continue
                except Exception as exc:
                    runtime_error = exc
                    print("mcp start_runtime failed, fallback to queue:", exc)
            if queue_runtime is not None:
                try:
                    entry = queue_runtime(task_id=task_id, project=project, title=title, agent=agent_name, require_approval=need_approval, run_reason="auto-pipeline")
                    self.pending_executions.append(entry)
                    mark_runtime_status(task_id, "queued", execution=entry, retryable=False)
                    started.append(task_id)
                    continue
                except Exception as exc:
                    runtime_error = exc
                    print("queue_runtime fail:", exc)
            if runtime_error is None:
                runtime_error = RuntimeError("no runtime starter available")
            mark_runtime_status(task_id, "failed", error=runtime_error, retryable=True)
        return started

    def _save_log(self, log_data: Dict):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_data, ensure_ascii=False) + "\n")


auto_pipeline = AutoPipeline()

if __name__ == "__main__":
    pipeline = AutoPipeline()
    output = pipeline.run(mode="manual")
    print(output)
