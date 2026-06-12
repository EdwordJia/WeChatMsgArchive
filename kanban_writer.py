# -*- coding: utf-8 -*-
"""Write kanban-doc tasks directly to disk (Stage 3 plan C)."""

import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

try:
    from config_loader import get_kanban_config
    _kanban_root = Path(get_kanban_config().get("root", "D:/develoment_home/project_home/videKanban/kanban-doc/.kanban"))
except Exception:
    _kanban_root = Path(r"D:/develoment_home/project_home/videKanban/kanban-doc/.kanban")

KANBAN_ROOT = _kanban_root


def _slugify(title, max_len=60):
    tmp = re.sub(r"[^\w\u4e00-\u9fff]+", "-", title.lower())
    tmp = tmp.strip("-")[:max_len]
    return tmp or "task"


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def write_task(project, title, body, priority="medium", tags=None, status="todo"):
    tags = tags or []
    tid = secrets.token_hex(2)
    slug = _slugify(title)
    fname = tid + "-" + slug + ".md"
    project_dir = KANBAN_ROOT / "projects" / project / "tasks"
    project_dir.mkdir(parents=True, exist_ok=True)
    fpath = project_dir / fname
    now = _now_iso()
    fm = [
        "---",
        "id: " + tid,
        'title: "' + title.replace(chr(10), " ").replace('"', '\\"') + '"',
        "status: " + status,
        "priority: " + priority,
    ]
    if tags:
        fm.append("tags:")
        for t in tags:
            fm.append("- " + str(t))
    fm.extend(["created_at: " + now, "updated_at: " + now, "---", ""])
    content = chr(10).join(fm) + chr(10) + body.rstrip() + chr(10)
    fpath.write_text(content, encoding="utf-8")
    return tid, str(fpath)


def list_recent_tasks(project, limit=10):
    project_dir = KANBAN_ROOT / "projects" / project / "tasks"
    if not project_dir.exists():
        return []
    files = sorted(project_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [f.name for f in files[:limit]]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    body = "## Test" + chr(10) + "AutoPipeline self-test task, safe to delete."
    tid, fpath = write_task(
        "WeChatMsgArchive",
        "AutoPipeline self-test task",
        body,
        priority="low",
        tags=["self-test", "auto-pipeline"],
    )
    print("wrote:", tid, fpath)
    recent = list_recent_tasks("WeChatMsgArchive")
    print("recent:", recent[:5])
