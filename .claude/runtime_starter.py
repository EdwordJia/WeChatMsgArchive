# -*- coding: utf-8 -*-
"""Stage 5: queue runtime executions for newly-created kanban tasks.

Mode: writes a JSON queue file that a downstream Claude session reads and
invokes mcp__kanban-doc__start_runtime against. Default require_approval=true so
agent only runs after human approval (enterprise safety)."""

import json
from pathlib import Path
from datetime import datetime

QUEUE_FILE = Path(".claude/state/runtime_queue.json")


def _load():
    if not QUEUE_FILE.exists():
        return {"pending": [], "history": []}
    try:
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"pending": [], "history": []}


def _save(state):
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def queue_runtime(task_id, project, title, agent="codex", require_approval=True, run_reason="auto-pipeline"):
    """Queue a runtime execution for downstream MCP invocation."""
    state = _load()
    entry = {
        "task_id": task_id,
        "project": project,
        "title": title,
        "agent": agent,
        "require_approval": require_approval,
        "run_reason": run_reason,
        "queued_at": datetime.now().isoformat(),
        "status": "queued",
    }
    state.setdefault("pending", []).append(entry)
    _save(state)
    return entry


def list_pending():
    return _load().get("pending", [])


def mark_started(task_id, process_id=None):
    state = _load()
    pending = state.get("pending", [])
    remaining = []
    for e in pending:
        if e.get("task_id") == task_id:
            e["status"] = "started"
            e["started_at"] = datetime.now().isoformat()
            if process_id:
                e["process_id"] = process_id
            state.setdefault("history", []).append(e)
        else:
            remaining.append(e)
    state["pending"] = remaining
    _save(state)


def stats():
    state = _load()
    return {"pending": len(state.get("pending", [])), "history": len(state.get("history", []))}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("runtime queue stats:", stats())
    print("pending:", list_pending())
