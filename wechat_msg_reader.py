# -*- coding: utf-8 -*-
"""WeChat msg reader v2."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


def load_nick_cache(p):
    cache = {}
    if not p.exists():
        return cache
    try:
        cur = sqlite3.connect(str(p)).cursor()
        cur.execute("SELECT UserName, NickName, Remark FROM Contact")
        for u, n, r in cur.fetchall():
            cache[u] = r or n or u
    except Exception as e:
        print("nick fail:", e)
    return cache


def query_one_db(p, cutoff, flt, nicks):
    out = []
    try:
        try:
            import sys as _sys
            _claude_dir = str(Path(__file__).parent / ".claude")
            if _claude_dir not in _sys.path:
                _sys.path.insert(0, _claude_dir)
            from wechat_attachment_parser import parse_attachments
        except Exception:
            parse_attachments = None
        db_dir = str(p.parent.parent)
        cur = sqlite3.connect(str(p)).cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='MSG'")
        if not cur.fetchone():
            return out
        sql = "SELECT CreateTime, StrContent, StrTalker, Type, IsSender, BytesExtra FROM MSG WHERE CreateTime > ? ORDER BY CreateTime DESC LIMIT 500"
        cur.execute(sql, (cutoff,))
        for ct, raw, tk, mt, snd, bx in cur.fetchall():
            if flt and tk not in flt:
                continue
            wxid = ""
            body = raw or ""
            sep = ":" + chr(10)
            if snd == 0 and sep in body[:120]:
                head, _, rest = body.partition(sep)
                if head.startswith("wxid_") or len(head) <= 32:
                    wxid = head
                    body = rest
            if not wxid and snd == 0 and bx:
                import re as _re
                _chunks = _re.findall(rb"[\w@\-\.]{6,40}", bx[:300])
                for _c in _chunks:
                    s = _c.decode("utf-8", errors="ignore")
                    if s.startswith("wxid_") or s.endswith("@openim") or s.endswith("@chatroom"):
                        wxid = s
                        break
            if snd == 1:
                sname = "ME"
            elif wxid:
                sname = nicks.get(wxid, wxid)
            else:
                sname = "GROUP"
            attachments = parse_attachments(mt, body, tk, db_dir) if parse_attachments else []
            out.append({
                "content": body,
                "sender": sname,
                "sender_wxid": wxid,
                "time": datetime.fromtimestamp(ct).strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": ct,
                "chatroom": tk,
                "chatroom_name": nicks.get(tk, tk),
                "type": mt,
                "is_sender": snd,
                "attachments": attachments,
            })
    except Exception as e:
        print("query", p.name, "fail:", e)
    return out


def fetch_recent_messages(hours=24, chatroom_filter=None, db_dir="output/decrypted_db"):
    base = Path(db_dir)
    cutoff = int((datetime.now() - timedelta(hours=hours)).timestamp())
    nicks = load_nick_cache(base / "MicroMsg.db")
    collected = []
    for p in sorted((base / "Multi").glob("MSG*.db")):
        collected.extend(query_one_db(p, cutoff, chatroom_filter, nicks))
    seen = set()
    dedup = []
    for m in collected:
        k = (m["timestamp"], m["chatroom"], m["content"][:50])
        if k in seen:
            continue
        seen.add(k)
        dedup.append(m)
    dedup.sort(key=lambda x: x["timestamp"], reverse=True)
    return dedup


def get_chatroom_list(db_dir="output/decrypted_db"):
    p = Path(db_dir) / "MicroMsg.db"
    rooms = []
    if not p.exists():
        return rooms
    try:
        cur = sqlite3.connect(str(p)).cursor()
        cur.execute("SELECT UserName, NickName FROM Contact WHERE UserName LIKE '%@chatroom'")
        data = cur.fetchall()
        for u, n in data:
            cur.execute("SELECT UserNameList FROM ChatRoom WHERE ChatRoomName=?", (u,))
            cr = cur.fetchone()
            cnt = len(cr[0].split("^G")) if cr and cr[0] else 0
            rooms.append({"chatroom_id": u, "name": n or "no-name", "member_count": cnt})
    except Exception as e:
        print("chatroom fail:", e)
    rooms.sort(key=lambda r: r["member_count"], reverse=True)
    return rooms


class WeChatMessageFetcher:
    def __init__(self, db_dir="output/decrypted_db"):
        self.db_dir = db_dir
    def fetch_recent_messages(self, hours=24, chatroom_filter=None):
        return fetch_recent_messages(hours, chatroom_filter, self.db_dir)
    def get_chatroom_list(self):
        return get_chatroom_list(self.db_dir)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    rooms = get_chatroom_list()
    print("chatrooms:", len(rooms))
    for r in rooms[:5]:
        print(" ", r["chatroom_id"], "|", r["name"], "| members=", r["member_count"])
    msgs = fetch_recent_messages(hours=24*30)
    print("recent (30d):", len(msgs))
    for m in msgs[:8]:
        print(" ", m["time"], m["chatroom_name"][:14], m["sender"][:12], m["content"][:60])
