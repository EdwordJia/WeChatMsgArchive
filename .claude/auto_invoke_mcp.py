# -*- coding: utf-8 -*-
"""Auto MCP invocation bridge."""

import json
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent))
from start_approved_runtimes import mark_started, build_invocations

PLAN_FILE = Path(".claude/state/mcp_invocation_plan.md")


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
