# -*- coding: utf-8 -*-
"""Auto MCP invocation bridge.

DEPRECATED: runtime tags/decide_approval 已迁移到 pipeline.yaml + config_loader.py
此文件保留 invocation plan 渲染功能，并提供 AutoPipeline 直接调用 kanban-doc MCP 的轻量客户端。
"""

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent))

from start_approved_runtimes import mark_started, build_invocations

PLAN_FILE = Path(".claude/state/mcp_invocation_plan.md")
ALERT_FILE = Path(".claude/state/auto_pipeline_alerts.log")


class McpToolError(RuntimeError):
    pass


def _runtime_config():
    try:
        from config_loader import get_runtime_config

        return get_runtime_config()
    except Exception:
        return {}


def _kanban_root():
    try:
        from config_loader import get_kanban_config

        return get_kanban_config().get("root", "D:/develoment_home/project_home/videKanban/kanban-doc/.kanban")
    except Exception:
        return "D:/develoment_home/project_home/videKanban/kanban-doc/.kanban"


def _alert(stage, payload, error):
    ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "payload": payload,
        "error": str(error),
    }
    with open(ALERT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _jsonrpc(tool_name, arguments, request_id=None):
    return {
        "jsonrpc": "2.0",
        "id": request_id or int(time.time() * 1000),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }


def _extract_tool_text(response):
    if response.get("error"):
        raise McpToolError(response["error"].get("message") or response["error"])
    content = (response.get("result") or {}).get("content") or []
    if not content:
        return ""
    return "\n".join(str(item.get("text", "")) for item in content if item.get("type") == "text")


def _call_http(tool_name, arguments):
    cfg = _runtime_config()
    url = cfg.get("mcp_http_url", "http://127.0.0.1:19876/mcp")
    data = json.dumps(_jsonrpc(tool_name, arguments), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=float(cfg.get("mcp_http_timeout", 10))) as resp:
        return _extract_tool_text(json.loads(resp.read().decode("utf-8")))


def _stdio_exe_candidates():
    cfg = _runtime_config()
    candidates = []
    for key in ("mcp_stdio_exe", "mcp_stdio_fallback_exe"):
        value = cfg.get(key)
        if value:
            candidates.append(Path(value))
    candidates.extend([
        Path("D:/develoment_home/project_home/videKanban/kanban-doc/target/release/kanban-store.exe"),
        Path("D:/develoment_home/project_home/videKanban/kanban-doc/target/debug/kanban-store.exe"),
    ])
    seen = set()
    result = []
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _call_stdio(tool_name, arguments):
    payload = json.dumps(_jsonrpc(tool_name, arguments), ensure_ascii=False) + "\n"
    kanban_root = arguments.get("kanban_root") or _kanban_root()
    last_error = None
    for exe in _stdio_exe_candidates():
        if not exe.exists():
            continue
        cmd = [str(exe), "--mcp", "--kanban-dir", kanban_root]
        try:
            proc = subprocess.run(
                cmd,
                input=payload,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=float(_runtime_config().get("mcp_stdio_timeout", 30)),
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or f"kanban-store exited {proc.returncode}")
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line.startswith("{"):
                    return _extract_tool_text(json.loads(line))
            raise RuntimeError(proc.stdout.strip() or "empty MCP stdio response")
        except McpToolError:
            raise
        except Exception as exc:
            last_error = exc
    raise RuntimeError(last_error or "kanban-store executable not found")


def call_mcp_tool(tool_name, arguments, stage=None, retries=None):
    cfg = _runtime_config()
    max_retries = int(cfg.get("mcp_retries", 2) if retries is None else retries)
    payload = {"tool": tool_name, "arguments": arguments}
    last_error = None
    for attempt in range(max_retries + 1):
        callers = [_call_http, _call_stdio] if cfg.get("mcp_prefer_http") else [_call_stdio, _call_http]
        for caller in callers:
            try:
                return caller(tool_name, arguments)
            except McpToolError as exc:
                last_error = exc
                break
            except Exception as exc:
                last_error = exc
        if attempt < max_retries:
            time.sleep(0.5 * (attempt + 1))
    _alert(stage or tool_name, payload, last_error)
    raise last_error


def create_task_via_mcp(project, title, body, priority="medium", tags=None):
    args = {
        "kanban_root": _kanban_root(),
        "project": project,
        "title": title,
        "body": body,
        "priority": priority,
        "tags": tags or [],
    }
    text = call_mcp_tool("create_task", args, stage="create_task")
    match = re.search(r"Created task\s+([0-9a-fA-F]+)\s+in project", text)
    if not match:
        raise RuntimeError("Cannot parse created task id from MCP response: " + text)
    return match.group(1), text


def create_workspace_via_mcp(task_id, project, title=""):
    cfg = _runtime_config()
    args = {
        "kanban_root": _kanban_root(),
        "project": project,
        "task_id": task_id,
    }
    if title:
        args["title"] = title
    if cfg.get("base_branch"):
        args["base_branch"] = cfg["base_branch"]
    return call_mcp_tool("create_workspace", args, stage="create_workspace")


def start_runtime_via_mcp(task_id, project, title="", agent="codex", require_approval=True, run_reason="auto-pipeline"):
    cli = "codex" if agent == "codex" else "kimi"
    executor = "CODEX" if agent == "codex" else "KIMI"
    workspace_result = create_workspace_via_mcp(task_id, project, title=title)
    args = {
        "kanban_root": _kanban_root(),
        "project": project,
        "task_id": task_id,
        "executor": executor,
        "cli": cli,
        "task": title or f"Execute task {task_id}",
        "run_reason": run_reason,
        "require_approval": require_approval,
    }
    text = call_mcp_tool("start_runtime", args, stage="start_runtime")
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = {"raw": text}
    process = parsed.get("process") if isinstance(parsed, dict) else None
    return {
        "task_id": task_id,
        "project": project,
        "agent": agent,
        "require_approval": require_approval,
        "run_reason": run_reason,
        "process_id": process.get("id") if isinstance(process, dict) else None,
        "workspace_result": workspace_result,
        "mcp_result": parsed,
        "status": "started",
    }


def render_invocation_plan():
    invs = build_invocations()
    auto_invs = [i for i in invs if i.get("source") == "auto"]
    manual_invs = [i for i in invs if i.get("source") == "manual"]
    lines = []
    lines.append("# 自动化 MCP 调用计划")
    lines.append("")
    lines.append("生成时间: " + datetime.now().isoformat())
    lines.append("待调用: " + str(len(invs)))
    lines.append("")
    lines.append("## 自动启动 (" + str(len(auto_invs)) + ")")
    for i in auto_invs:
        tid = i.get("task_id", "")
        proj = i.get("project", "")
        title = i.get("title", "")[:40]
        lines.append("- " + tid + " | " + proj + " | " + title)
    lines.append("")
    lines.append("## 用户已勾选 (" + str(len(manual_invs)) + ")")
    for i in manual_invs:
        tid = i.get("task_id", "")
        proj = i.get("project", "")
        title = i.get("title", "")[:40]
        lines.append("- " + tid + " | " + proj + " | " + title)
    lines.append("")
    lines.append("## Claude 调用模板")
    lines.append("")
    lines.append("对每条 source=auto 或勾选的 source=manual 项调用:")
    lines.append("- mcp__kanban-doc__create_workspace(project, task_id)")
    lines.append("- mcp__kanban-doc__start_runtime(project, task=task_id, task_id=task_id, executor='CLAUDE_CODE', run_reason='auto-pipeline', require_approval=False)")
    lines.append("- auto_invoke_mcp.mark_invoked(task_id, process_id)")
    return chr(10).join(lines)


def mark_invoked(task_id, process_id=None):
    return mark_started(task_id, process_id)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLAN_FILE.write_text(render_invocation_plan(), encoding="utf-8")
    print("plan ->", PLAN_FILE)
