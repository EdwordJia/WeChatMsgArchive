# -*- coding: utf-8 -*-
"""Message and requirement state for AutoPipeline idempotency."""

import hashlib
import json
from pathlib import Path
from datetime import datetime

try:
    from config_loader import get_dedup_config
    _dedup_cfg = get_dedup_config()
    STATE_FILE = Path(_dedup_cfg.get("state_file", ".claude/state/processed_messages.json"))
    MAX_TRACKED = _dedup_cfg.get("max_tracked", 5000)
except Exception:
    STATE_FILE = Path(".claude/state/processed_messages.json")
    MAX_TRACKED = 5000


def _now():
    return datetime.now().isoformat()


def _empty_state():
    return {"seen": [], "requirements": {}, "_meta": {"created": _now()}}


def _load():
    if not STATE_FILE.exists():
        return _empty_state()
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print("dedup state load fail:", exc)
        return _empty_state()
    state.setdefault("seen", [])
    state.setdefault("requirements", {})
    state.setdefault("_meta", {"created": _now()})
    return state


def _save(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    seen = list(state.get("seen", []))
    if len(seen) > MAX_TRACKED:
        state["seen"] = seen[-MAX_TRACKED:]
    requirements = state.get("requirements", {})
    if len(requirements) > MAX_TRACKED:
        kept = sorted(
            requirements.items(),
            key=lambda item: item[1].get("updated_at") or item[1].get("created_at") or "",
        )[-MAX_TRACKED:]
        state["requirements"] = dict(kept)
    state.setdefault("_meta", {})["last_save"] = _now()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(msg):
    return str(msg.get("timestamp")) + "|" + str(msg.get("chatroom")) + "|" + (msg.get("content") or "")[:50]


def message_key(msg):
    return _key(msg)


def source_messages_for_requirement(req):
    thread = req.get("source_thread") or {}
    messages = thread.get("messages") or []
    if messages:
        return messages
    msg = req.get("source_message") or {}
    return [msg] if msg else []


def source_message_keys(req):
    return [message_key(msg) for msg in source_messages_for_requirement(req)]


def requirement_key(req):
    keys = source_message_keys(req)
    if keys:
        basis = "|".join(keys)
    else:
        basis = str(req.get("title", "")) + "|" + str(req.get("description", ""))[:500]
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def filter_unseen(messages):
    state = _load()
    seen = set(state.get("seen", []))
    return [m for m in messages if _key(m) not in seen]


def mark_seen(messages):
    state = _load()
    seen = set(state.get("seen", []))
    for m in messages:
        seen.add(_key(m))
    state["seen"] = sorted(seen)
    _save(state)


def mark_requirement_messages_seen(req):
    mark_seen(source_messages_for_requirement(req))


def mark_non_requirement_messages_seen(messages, requirements):
    requirement_message_keys = set()
    for req in requirements:
        requirement_message_keys.update(source_message_keys(req))
    mark_seen([msg for msg in messages if message_key(msg) not in requirement_message_keys])


def _record_for_requirement(state, req):
    key = requirement_key(req)
    records = state.setdefault("requirements", {})
    record = records.get(key)
    if record is None:
        record = {
            "key": key,
            "created_at": _now(),
            "source_message_keys": source_message_keys(req),
        }
        records[key] = record
    record["updated_at"] = _now()
    record["title"] = req.get("title") or record.get("title") or ""
    record["priority"] = req.get("priority") or record.get("priority") or "medium"
    record["tags"] = list(req.get("tags") or record.get("tags") or [])
    return record


def get_requirement_record(req_or_key):
    state = _load()
    key = req_or_key if isinstance(req_or_key, str) else requirement_key(req_or_key)
    record = state.get("requirements", {}).get(key)
    return dict(record) if record else None


def get_requirement_by_task_id(task_id):
    state = _load()
    for record in state.get("requirements", {}).values():
        if record.get("task_id") == task_id:
            return dict(record)
    return None


def mark_requirement_task(req, project, task_id, title="", priority="medium", tags=None, metadata=None):
    state = _load()
    record = _record_for_requirement(state, req)
    record.update({
        "status": "task_created",
        "task_status": "created",
        "runtime_status": record.get("runtime_status") or "pending",
        "project": project,
        "task_id": task_id,
        "title": title or record.get("title") or "",
        "priority": priority or record.get("priority") or "medium",
        "tags": list(tags or record.get("tags") or []),
        "retryable": True,
        "last_error": None,
    })
    if metadata:
        record.setdefault("metadata", {}).update(metadata)
    _save(state)
    return dict(record)


def mark_requirement_failed(req, stage, error, retryable=True):
    state = _load()
    record = _record_for_requirement(state, req)
    if stage in ("create_task", "task"):
        record["status"] = "task_failed"
        record["task_status"] = "failed"
    elif stage in ("runtime", "start_runtime"):
        record["status"] = "runtime_failed"
        record["runtime_status"] = "failed"
    else:
        record["status"] = stage + "_failed"
    record["retryable"] = retryable
    record["last_error"] = str(error)
    record["last_error_stage"] = stage
    record["failed_at"] = _now()
    _save(state)
    return dict(record)


def mark_runtime_status(task_id, status, execution=None, error=None, retryable=True):
    state = _load()
    records = state.setdefault("requirements", {})
    record = None
    for candidate in records.values():
        if candidate.get("task_id") == task_id:
            record = candidate
            break
    if record is None:
        key = "task:" + str(task_id)
        record = records.setdefault(key, {"key": key, "task_id": task_id, "created_at": _now()})
    record["updated_at"] = _now()
    record["runtime_status"] = status
    record["status"] = "runtime_" + status
    if execution:
        record["runtime"] = execution
        process_id = execution.get("process_id") or execution.get("process") or execution.get("id")
        if process_id:
            record["process_id"] = process_id
    if error is not None:
        record["last_error"] = str(error)
        record["last_error_stage"] = "runtime"
        record["failed_at"] = _now()
    else:
        record["last_error"] = None
    record["retryable"] = retryable if status == "failed" else False
    _save(state)
    return dict(record)


def list_runtime_retryable():
    state = _load()
    records = []
    for record in state.get("requirements", {}).values():
        if not record.get("task_id"):
            continue
        if record.get("task_status") == "failed":
            continue
        runtime_status = record.get("runtime_status") or "pending"
        if runtime_status in ("pending", "failed") and record.get("retryable", True):
            records.append(dict(record))
    return records


def stats():
    state = _load()
    requirements = state.get("requirements", {})
    retryable = [r for r in requirements.values() if r.get("retryable")]
    return {
        "total": len(state.get("seen", [])),
        "requirements": len(requirements),
        "retryable": len(retryable),
        "meta": state.get("_meta", {}),
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("dedup stats:", stats())
