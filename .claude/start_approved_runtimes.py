# -*- coding: utf-8 -*-
"""Stage 6 桥接：扫描 runtime_pending_report.md 中已勾选 [x] 的条目，
产出可执行的 MCP 调用清单（JSON 形式），让 Claude 会话遍历调用 start_runtime。"""

import json, re, sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from runtime_starter import _load, _save, list_pending

REPORT_FILE = Path(".claude/state/runtime_pending_report.md")
INVOCATION_FILE = Path(".claude/state/start_runtime_invocations.json")


def parse_approved(report_text):
    """Find lines like '- [x] **TASKID** [PROJECT] ...' and return list of task_ids."""
    pat = re.compile(r"^- \[x\]\s+\*\*([0-9a-f]{4,8})\*\*", re.MULTILINE | re.IGNORECASE)
    return list({m.group(1) for m in pat.finditer(report_text)})


def build_invocations():
    """Build invocation list combining: auto-startable + user-approved."""
    pending = list_pending()
    auto_ok = [p for p in pending if not p.get("require_approval") and p.get("status") == "queued"]
    approved_ids = []
    if REPORT_FILE.exists():
        try:
            approved_ids = parse_approved(REPORT_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            print("parse approved fail:", exc)
    manual_ok = [p for p in pending if p.get("task_id") in approved_ids and p.get("status") == "queued"]
    invocations = []
    for src_kind, group in (("auto", auto_ok), ("manual", manual_ok)):
        for p in group:
            invocations.append({
                "source": src_kind,
                "project": p.get("project"),
                "task_id": p.get("task_id"),
                "title": p.get("title"),
                "agent": p.get("agent", "kimi"),
                "executor": "CLAUDE_CODE",
                "run_reason": p.get("run_reason", "auto-pipeline"),
            })
    return invocations


def write_invocations():
    invs = build_invocations()
    INVOCATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    INVOCATION_FILE.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(),
        "count": len(invs),
        "invocations": invs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return invs


def mark_started(task_id, process_id=None):
    """Move pending entry to history and mark started."""
    state = _load()
    pending = state.get("pending", [])
    remaining = []
    moved = None
    for e in pending:
        if e.get("task_id") == task_id:
            e["status"] = "started"
            e["started_at"] = datetime.now().isoformat()
            if process_id:
                e["process_id"] = process_id
            state.setdefault("history", []).append(e)
            moved = e
        else:
            remaining.append(e)
    state["pending"] = remaining
    _save(state)
    return moved


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    invs = write_invocations()
    print("invocations -> .claude/state/start_runtime_invocations.json")
    print("count:", len(invs))
    for i in invs:
        print(" ", i["source"], i["project"], i["task_id"], i["title"][:40])
