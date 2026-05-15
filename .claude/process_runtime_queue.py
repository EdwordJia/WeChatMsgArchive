# -*- coding: utf-8 -*-
"""runtime_queue 桥接：输出 markdown 报告供 Claude 会话审批/启动."""

import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from runtime_starter import _load, list_pending

REPORT_FILE = Path(".claude/state/runtime_pending_report.md")


def render_report():
    state = _load()
    pending = state.get("pending", [])
    history = state.get("history", [])
    lines = []
    lines.append("# Runtime Queue Report")
    lines.append("")
    lines.append("- pending: " + str(len(pending)))
    lines.append("- history: " + str(len(history)))
    lines.append("")
    auto_ok = [p for p in pending if not p.get("require_approval")]
    need_approve = [p for p in pending if p.get("require_approval")]
    lines.append("## 自动可启动 (" + str(len(auto_ok)) + ")")
    lines.append("")
    for p in auto_ok:
        tid = p.get("task_id", "")
        proj = p.get("project", "")
        title = p.get("title", "")
        agent = p.get("agent", "")
        lines.append("- **" + tid + "** [" + proj + "] " + title + "  -> agent=" + agent)
    lines.append("")
    lines.append("## 待人审批 (" + str(len(need_approve)) + ")")
    lines.append("")
    for p in need_approve:
        tid = p.get("task_id", "")
        proj = p.get("project", "")
        title = p.get("title", "")
        agent = p.get("agent", "")
        reason = p.get("run_reason", "")
        lines.append("- [ ] **" + tid + "** [" + proj + "] " + title + "  -> agent=" + agent + "  reason=" + reason)
    lines.append("")
    lines.append("## 操作指引")
    lines.append("")
    lines.append("- 自动队列: Claude 会话可直接调 mcp__kanban-doc__start_runtime(project, task_id, executor=...)")
    lines.append("- 审批队列: 用户在此 md 勾选 [x] 后再启动")
    lines.append("- 启动后调 runtime_starter.mark_started(task_id, process_id)")
    return chr(10).join(lines)


def write_report():
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = render_report()
    REPORT_FILE.write_text(content, encoding="utf-8")
    return REPORT_FILE


def get_auto_startable():
    return [p for p in list_pending() if not p.get("require_approval") and p.get("status") == "queued"]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    fp = write_report()
    print("report ->", fp)
    print("auto-startable count:", len(get_auto_startable()))
