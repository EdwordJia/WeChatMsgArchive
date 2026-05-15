# -*- coding: utf-8 -*-
"""Message-level dedup state for AutoPipeline."""

import json
from pathlib import Path
from datetime import datetime

STATE_FILE = Path(".claude/state/processed_messages.json")
MAX_TRACKED = 5000  # cap to avoid unbounded growth


def _load():
    if not STATE_FILE.exists():
        return {"seen": [], "_meta": {"created": datetime.now().isoformat()}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print("dedup state load fail:", exc)
        return {"seen": [], "_meta": {"created": datetime.now().isoformat()}}


def _save(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # cap size
    if len(state.get("seen", [])) > MAX_TRACKED:
        state["seen"] = state["seen"][-MAX_TRACKED:]
    state.setdefault("_meta", {})["last_save"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(msg):
    """Stable per-message identity: (timestamp, chatroom, content[:50])."""
    return str(msg.get("timestamp")) + "|" + str(msg.get("chatroom")) + "|" + (msg.get("content") or "")[:50]


def filter_unseen(messages):
    """Return only messages not seen before; do NOT mark seen yet."""
    state = _load()
    seen = set(state.get("seen", []))
    return [m for m in messages if _key(m) not in seen]


def mark_seen(messages):
    """Add messages to seen set + persist."""
    state = _load()
    seen = set(state.get("seen", []))
    for m in messages:
        seen.add(_key(m))
    state["seen"] = sorted(seen)
    _save(state)


def stats():
    state = _load()
    return {"total": len(state.get("seen", [])), "meta": state.get("_meta", {})}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("dedup stats:", stats())
